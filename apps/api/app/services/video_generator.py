"""Video Generator Service — fal.ai for all video generation.

Selects the right sub-endpoint (`t2v` / `i2v`) from the model registry based on
inputs. Dispatches through `FalService`:
  * webhook mode (inside a workflow task) → `{status: "pending_fal", request_id}`
  * sync mode (local dev / ad-hoc)        → fetches + uploads to S3, returns final url
"""

from __future__ import annotations

import asyncio
import base64
import json
import random
import re
import shutil
import time
from pathlib import Path
from typing import Any, List, Optional

import httpx


_VIDEO_EXT_RE = re.compile(r"\.(mp4|webm|mov|m4v|mkv)(\?|$)", re.IGNORECASE)


def _is_video_url(url: str) -> bool:
    return bool(isinstance(url, str) and _VIDEO_EXT_RE.search(url))

from app.core.config import settings
from app.core.dependencies import get_storage_service
from app.core.model_registry import (
    get_model_by_endpoint_id,
    get_model_by_id,
    get_model_by_name,
    resolve_endpoint_id,
)
from app.services.fal_service import FalService

_DEFAULT_VIDEO_ENDPOINT = "fal-ai/kling-video/v3/standard/text-to-video"
_VIDEO_DEBUG_PREFIX = "__FAL_VIDEO_DEBUG_PAYLOAD_B64__"


def _adapt_args_for_kling_v3(
    endpoint_id: str,
    args: dict,
    *,
    element_images: Optional[List[str]] = None,
    element_videos: Optional[List[str]] = None,
    element_voices: Optional[List[str]] = None,
    capability_hint: Optional[str] = None,
) -> dict:
    """Reshape generic video args to match the Kling v3 schema.

    Kling v3 (both Pro and Standard) uses different field names than what
    `build_video_args` produces, and i2v rejects `resolution` / `aspect_ratio`
    entirely. Without this adapter the call returns 422 even on a correct URL.

    Schema reference (fal docs, 2026-04):
      * `image-to-video` (i2v / reference): requires `start_image_url`.
        Optional `prompt`, `multi_prompt`, `duration` (3-15), `generate_audio`,
        `end_image_url`, `shot_type`, `negative_prompt`, `cfg_scale`. NO
        `aspect_ratio`, NO `resolution`. The dedicated *elements* mode also
        runs on `image-to-video` but consumes `elements` exclusively (no
        `start_image_url`, no `end_image_url`).
      * `text-to-video`: `prompt`, `multi_prompt`, `duration`, `generate_audio`,
        `shot_type`, `aspect_ratio` (16:9 / 9:16 / 1:1), `negative_prompt`,
        `cfg_scale`. NO `resolution`, NO `image_url`, NO `elements`.
      * `motion-control`: `image_url` + `video_url` REQUIRED. Different shape.

    Elements take this combo shape:
        {"frontal_image_url": "...", "reference_image_urls": ["..."]}  # image set
        {"video_url": "..."}                                              # video element
        {"audio_url": "..."}                                              # audio element
    """
    if "/kling-video/v3/" not in (endpoint_id or ""):
        return args

    is_i2v = "image-to-video" in endpoint_id
    is_t2v = "text-to-video" in endpoint_id
    is_motion = "motion-control" in endpoint_id
    is_elements_capability = (capability_hint or "").lower() == "elements"

    # `enable_audio` (used by older Kling v1.6 endpoints) → `generate_audio` for v3.
    if "enable_audio" in args:
        args["generate_audio"] = args.pop("enable_audio")

    # Resolution is not in the Kling v3 schema for any sub-endpoint.
    args.pop("resolution", None)

    if is_i2v:
        # Rename / drop fields not in the i2v schema.
        if "image_url" in args:
            # v3 i2v only knows `start_image_url`. Move OR drop, never both.
            if "start_image_url" not in args:
                args["start_image_url"] = args.pop("image_url")
            else:
                args.pop("image_url", None)
        args.pop("tail_image_url", None)         # not in v3 i2v schema
        args.pop("aspect_ratio", None)            # determined by start_image_url

        if is_elements_capability:
            # ── Pure ELEMENTS mode ────────────────────────────────────────
            # The fal endpoint still validates `start_image_url` at the top
            # level, so for image-elements we set it to the frontal image. The
            # actual character/reference/audio conditioning lives in the
            # `elements` array.
            args.pop("start_image_url", None)
            args.pop("end_image_url", None)
            args.pop("image_url", None)

            # Dedup, preserve order; keep images / videos separate.
            seen: set[str] = set()
            unique_imgs: list[str] = []
            for u in element_images or []:
                if isinstance(u, str) and u and u not in seen and not _is_video_url(u):
                    seen.add(u)
                    unique_imgs.append(u)

            seen_v: set[str] = set()
            unique_vids: list[str] = []
            for u in (element_videos or []) + [u for u in (element_images or []) if _is_video_url(str(u))]:
                if isinstance(u, str) and u and u not in seen_v:
                    seen_v.add(u)
                    unique_vids.append(u)

            seen_a: set[str] = set()
            unique_audios: list[str] = []
            # `audio_url` may have been pre-populated by the caller as a
            # generic single-audio fallback for non-element-voices flows.
            single_audio = args.pop("audio_url", None)
            if isinstance(single_audio, str) and single_audio:
                if single_audio not in seen_a:
                    seen_a.add(single_audio)
                    unique_audios.append(single_audio)
            for u in element_voices or []:
                if isinstance(u, str) and u and u not in seen_a:
                    seen_a.add(u)
                    unique_audios.append(u)

            elements_payload: list[dict] = []

            # Image set. Fal expects the frontal image to also be present in
            # `reference_image_urls`; preserve connection order after that:
            #   N=1 -> frontal, references=[frontal]
            #   N>=2 -> frontal, references=[frontal, second, third]
            if unique_imgs:
                image_element: dict[str, Any]
                if len(unique_imgs) == 1:
                    image_element = {
                        "frontal_image_url": unique_imgs[0],
                        "reference_image_urls": [unique_imgs[0]],
                    }
                else:
                    image_element = {
                        "frontal_image_url": unique_imgs[0],
                        "reference_image_urls": unique_imgs,
                    }
                if unique_audios:
                    image_element["audio_url"] = unique_audios[0]
                    args["generate_audio"] = False
                args["start_image_url"] = unique_imgs[0]
                elements_payload.append(image_element)

            for v in unique_vids:
                elements_payload.append({"video_url": v})

            if elements_payload:
                args["elements"] = elements_payload
            else:
                args.pop("elements", None)
        else:
            # ── i2v / reference / non-elements paths ──────────────────────
            # Reshape elements to match Kling v3's strict schema:
            #   image set : {"frontal_image_url": str, "reference_image_urls": [str, ...≥1]}
            #   video     : {"video_url": str}
            # An element with frontal_image_url AND empty/missing reference_image_urls
            # is REJECTED by fal:
            #   "Either frontal_image_url and reference_image_urls or video_url
            #    must be provided."
            if element_images and "elements" in args:
                seen: set[str] = set()
                unique_urls: list[str] = []
                for url in element_images:
                    if isinstance(url, str) and url and url not in seen:
                        seen.add(url)
                        unique_urls.append(url)
                images = [u for u in unique_urls if not _is_video_url(u)]
                videos = [u for u in unique_urls if _is_video_url(u)]

                elements_payload: list[dict] = []
                for v in videos:
                    elements_payload.append({"video_url": v})

                has_explicit_start = "start_image_url" in args
                if has_explicit_start:
                    if len(images) >= 2:
                        elements_payload.append({
                            "frontal_image_url": images[0],
                            "reference_image_urls": images[1:],
                        })
                    elif len(images) == 1:
                        if "end_image_url" not in args:
                            args["end_image_url"] = images[0]
                else:
                    if len(images) >= 1:
                        args["start_image_url"] = images[0]
                        rest = images[1:]
                        if len(rest) >= 2:
                            elements_payload.append({
                                "frontal_image_url": rest[0],
                                "reference_image_urls": rest[1:],
                            })
                        elif len(rest) == 1:
                            if "end_image_url" not in args:
                                args["end_image_url"] = rest[0]

                if elements_payload:
                    args["elements"] = elements_payload
                else:
                    args.pop("elements", None)

        # Duration is a string-coercible enum; both `int` and `str` work but
        # being explicit avoids future surprises.
        if "duration" in args:
            args["duration"] = str(args["duration"])

    if is_t2v:
        # No image inputs / elements on t2v.
        for k in ("image_url", "start_image_url", "end_image_url",
                 "tail_image_url", "elements"):
            args.pop(k, None)
        if "duration" in args:
            args["duration"] = str(args["duration"])

    if is_motion:
        # Motion-control uses `image_url` + `video_url` directly (NOT
        # `start_image_url`). Schema accepts: prompt, image_url, video_url,
        # character_orientation, keep_original_sound, elements. Strip
        # everything else.
        for k in ("resolution", "aspect_ratio", "duration", "generate_audio",
                 "enable_audio", "start_image_url", "tail_image_url",
                 "end_image_url", "negative_prompt"):
            args.pop(k, None)

    return args


def _adapt_args_for_seedance_2(endpoint_id: str, args: dict) -> dict:
    """Reshape args for ByteDance Seedance 2.0 / 2.0 Fast endpoints.

    Seedance 2.0 uses:
      * t2v: prompt, resolution, duration, aspect_ratio, generate_audio
      * i2v: same + image_url, optional end_image_url
      * reference: same + image_urls, video_urls, audio_urls

    Supported values:
      resolution: 480p / 720p
      duration: auto or "4"..."15"
      aspect_ratio: auto / 21:9 / 16:9 / 4:3 / 1:1 / 3:4 / 9:16
    """
    if "bytedance/seedance-2.0" not in (endpoint_id or ""):
        return args

    if "enable_audio" in args:
        args["generate_audio"] = args.pop("enable_audio")

    resolution = str(args.get("resolution") or "720p")
    if resolution not in {"480p", "720p"}:
        resolution = "720p"
    args["resolution"] = resolution

    raw_duration = args.get("duration", "auto")
    if isinstance(raw_duration, str):
        normalized_duration = raw_duration.replace("s", "").strip().lower()
    else:
        normalized_duration = str(raw_duration)
    if normalized_duration != "auto":
        try:
            duration_int = int(normalized_duration)
            normalized_duration = str(min(15, max(4, duration_int)))
        except (TypeError, ValueError):
            normalized_duration = "auto"
    args["duration"] = normalized_duration

    aspect_ratio = str(args.get("aspect_ratio") or "auto")
    if aspect_ratio not in {"auto", "21:9", "16:9", "4:3", "1:1", "3:4", "9:16"}:
        aspect_ratio = "auto"
    args["aspect_ratio"] = aspect_ratio

    is_reference = "reference-to-video" in endpoint_id
    is_t2v = "text-to-video" in endpoint_id
    is_i2v = "image-to-video" in endpoint_id

    if is_reference:
        # Reference endpoint uses plural field names only.
        image_urls = args.pop("image_urls", None)
        if not image_urls and args.get("image_url"):
            image_urls = [args.pop("image_url")]
        else:
            args.pop("image_url", None)
        video_urls = args.pop("video_urls", None)
        if not video_urls and args.get("video_url"):
            video_urls = [args.pop("video_url")]
        else:
            args.pop("video_url", None)
        audio_urls = args.pop("audio_urls", None)
        if not audio_urls and args.get("audio_url"):
            audio_urls = [args.pop("audio_url")]
        else:
            args.pop("audio_url", None)

        args.pop("end_image_url", None)
        args.pop("tail_image_url", None)
        args.pop("elements", None)
        args.pop("element_videos", None)

        if image_urls:
            args["image_urls"] = [u for u in image_urls[:9] if isinstance(u, str) and u]
        if video_urls:
            args["video_urls"] = [u for u in video_urls[:3] if isinstance(u, str) and u]
        if audio_urls:
            # Seedance requires at least one image or video if audio is present.
            if image_urls or video_urls:
                args["audio_urls"] = [u for u in audio_urls[:3] if isinstance(u, str) and u]
        return args

    if is_t2v:
        for key in ("image_url", "end_image_url", "tail_image_url", "image_urls",
                    "video_url", "video_urls", "audio_url", "audio_urls",
                    "elements", "element_videos"):
            args.pop(key, None)

    if is_i2v:
        # i2v uses singular image_url and optional end_image_url.
        for key in ("image_urls", "video_url", "video_urls", "audio_url", "audio_urls",
                    "elements", "element_videos"):
            args.pop(key, None)
        args.pop("tail_image_url", None)

    return args
_LIPSYNC_ENDPOINT = "fal-ai/kling-video/lipsync/audio-to-video"


class VideoGenerator:
    """Generate video clips via fal.ai endpoints."""

    def __init__(self) -> None:
        self.use_mock = settings.use_mock_veo
        self.storage = get_storage_service()
        self.fal = FalService()
        self.output_dir = Path("static/videos")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        if self.use_mock:
            print("[VideoGenerator] MOCK mode")
        else:
            print("[VideoGenerator] PRODUCTION mode — fal.ai")

    # ------------------------------------------------------------------ Mock
    def _get_mock_video(self) -> Optional[Path]:
        videos = list(self.output_dir.glob("*.mp4"))
        return random.choice(videos) if videos else None

    async def _mock_generate(self, prompt: str, duration: int = 8) -> dict:
        print(f"[VideoGenerator] MOCK: {prompt[:80]}")
        await asyncio.sleep(random.uniform(5, 10))
        mock_source = self._get_mock_video()
        if mock_source:
            filename = f"generated_{int(time.time())}.mp4"
            new_path = self.output_dir / filename
            shutil.copy(mock_source, new_path)
            return {
                "success": True,
                "video_url": f"{settings.api_base_url}/static/videos/{filename}",
                "duration": duration, "model": "mock", "mock": True,
            }
        return {"success": False, "error": "No mock videos available.", "mock": True}

    # ------------------------------------------------------------------ Utils
    async def _fetch_and_upload(self, url: str) -> Optional[str]:
        if not url:
            return None
        print(f"[VideoGenerator] uploading fal video → S3: {url[:80]}")
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=300.0)
            if response.status_code == 200:
                filename = f"generated_video_{int(time.time())}.mp4"
                return await self.storage.upload_file(response.content, filename, "video/mp4")
            print(f"[VideoGenerator] fetch failed ({response.status_code})")
        except Exception as e:
            print(f"[VideoGenerator] upload failed: {e}")
        return url

    def _resolve_endpoint(self, model_name: Optional[str], *, capability: str) -> tuple[str, dict]:
        endpoint_id = resolve_endpoint_id(
            model_name, _DEFAULT_VIDEO_ENDPOINT, model_type="video", capability=capability,
        )
        entry = get_model_by_endpoint_id(endpoint_id) or get_model_by_id(model_name or "") or {}
        return endpoint_id, entry

    def _resolve_lipsync_endpoint(self, lipsync_model_name: Optional[str]) -> tuple[str, dict]:
        endpoint_id = resolve_endpoint_id(
            lipsync_model_name,
            _LIPSYNC_ENDPOINT,
            model_type="video",
            capability="lipsync",
        )
        entry = (
            get_model_by_endpoint_id(endpoint_id)
            or get_model_by_id(lipsync_model_name or "")
            or get_model_by_name(lipsync_model_name or "")
            or {}
        )
        return endpoint_id, entry

    def _resolve_avatar_endpoint(self, avatar_model_name: Optional[str]) -> tuple[str, dict]:
        endpoint_id = resolve_endpoint_id(
            avatar_model_name,
            "fal-ai/kling-video/ai-avatar/v2/standard",
            model_type="video",
            capability="avatar",
        )
        entry = (
            get_model_by_endpoint_id(endpoint_id)
            or get_model_by_id(avatar_model_name or "")
            or get_model_by_name(avatar_model_name or "")
            or {}
        )
        return endpoint_id, entry

    # ------------------------------------------------------------------ Public
    async def generate_clip(
        self,
        prompt: str,
        duration: int = 5,
        use_fast_model: bool = False,
        resolution: str = "720p",
        aspect_ratio: str = "16:9",
        negative_prompt: Optional[str] = None,
        model_name: Optional[str] = None,
        audio_url: Optional[str] = None,
        lipsync_model_name: Optional[str] = None,
        generate_audio: bool = False,
        reference_images: Optional[List[str]] = None,
        element_images: Optional[List[str]] = None,
        element_videos: Optional[List[str]] = None,
        element_voices: Optional[List[str]] = None,
        reference_video: Optional[str] = None,
        motion_image: Optional[str] = None,
        motion_video: Optional[str] = None,
        character_orientation: str = "image",
    ) -> dict:
        if self.use_mock:
            return await self._mock_generate(f"[t2v] {prompt}", duration)

        # Pick the most-specific capability endpoint available for this call.
        # Motion-control wins when both inputs are present — it's a hybrid
        # i2v+v2v mode and uses a dedicated endpoint per Kling docs.
        if motion_image and motion_video:
            desired_capability = "motion"
        elif reference_video:
            desired_capability = "v2v"
        elif element_images or element_videos or element_voices:
            desired_capability = "elements"
        elif reference_images:
            desired_capability = "reference"
        else:
            desired_capability = "t2v"

        endpoint_id, entry = self._resolve_endpoint(model_name, capability=desired_capability)
        # If the model doesn't expose the desired capability endpoint, fall back to t2v.
        if desired_capability != "t2v" and endpoint_id == _DEFAULT_VIDEO_ENDPOINT:
            endpoint_id, entry = self._resolve_endpoint(model_name, capability="t2v")

        args = FalService.build_video_args(
            prompt=prompt,
            duration=duration,
            resolution=resolution,
            aspect_ratio=aspect_ratio,
            generate_audio=generate_audio,
            negative_prompt=negative_prompt,
        )
        if reference_images:
            args["image_url"] = reference_images[0]
        if reference_video:
            args["video_url"] = reference_video
        if element_images:
            # Pass through as `[{image_url}]` placeholders. The Kling v3
            # adapter rewrites them to the proper shape (frontal_image_url
            # for images, video_url for clips) and promotes the first image
            # to `start_image_url` if no separate start image is connected.
            # Other models that take `elements` as `[{image_url}]` keep this
            # shape unchanged.
            args["elements"] = [{"image_url": url} for url in element_images]
        if element_videos:
            args["element_videos"] = element_videos
        # In dedicated elements mode, audio (single OR per-voice) becomes an
        # element entry sent to fal — NOT a post-generation lipsync chain.
        # We stash it on the args dict so the Kling v3 adapter can pull it
        # into the elements payload, and we suppress `audio_url` for the
        # downstream lipsync chain to avoid double-application.
        elements_audio_consumed = False
        if desired_capability == "elements" and (audio_url or element_voices):
            if audio_url:
                args["audio_url"] = audio_url
            elements_audio_consumed = True
        if desired_capability == "motion":
            # Motion-control schema (per Kling v3 docs):
            #   prompt, image_url (req), video_url (req),
            #   character_orientation (image|video, req),
            #   keep_original_sound (bool, default true),
            #   elements (optional, max 1, facial — only when orientation=video).
            # Duration is *not* a parameter — Kling derives it from
            # character_orientation (10s max for image, 30s max for video).
            args["image_url"] = motion_image
            args["video_url"] = motion_video
            args["character_orientation"] = (
                character_orientation if character_orientation in ("image", "video") else "image"
            )
            for k in ("aspect_ratio", "resolution", "enable_audio", "duration", "negative_prompt"):
                args.pop(k, None)
            # Audio: `keep_original_sound` is the only audio knob on
            # motion-control. Default true; flip off only when the caller
            # explicitly set generate_audio=False.
            args["keep_original_sound"] = True if generate_audio is None else bool(generate_audio)

        # Per-endpoint schema fixups (Kling v3 uses different field names; see
        # adapter docstring). Adapter is a no-op for non-Kling-v3 endpoints.
        args = _adapt_args_for_kling_v3(
            endpoint_id,
            args,
            element_images=element_images,
            element_videos=element_videos,
            element_voices=element_voices,
            capability_hint=desired_capability,
        )
        args = _adapt_args_for_seedance_2(endpoint_id, args)

        # Drop audio_url from the lipsync chain when fal already consumes it
        # natively as part of the elements payload.
        finalize_audio_url = None if elements_audio_consumed else audio_url

        return await self._dispatch_and_finalize(
            capability=desired_capability, endpoint_id=endpoint_id, args=args, entry=entry,
            model_name_used=model_name, audio_url=finalize_audio_url,
            lipsync_model_name=lipsync_model_name,
            meta={
                "duration": duration,
                "resolution": resolution,
                "aspect_ratio": aspect_ratio,
                "elements_audio_consumed": elements_audio_consumed,
            },
        )

    async def generate_from_image(
        self,
        prompt: str,
        image_path: str,
        duration: int = 5,
        resolution: str = "720p",
        aspect_ratio: str = "16:9",
        model_name: Optional[str] = None,
        audio_url: Optional[str] = None,
        lipsync_model_name: Optional[str] = None,
        end_image_url: Optional[str] = None,
        generate_audio: bool = False,
    ) -> dict:
        if self.use_mock:
            return await self._mock_generate(f"[i2v] {prompt}", duration)

        endpoint_id, entry = self._resolve_endpoint(model_name, capability="i2v")
        args = FalService.build_video_args(
            prompt=prompt,
            duration=duration,
            resolution=resolution,
            aspect_ratio=aspect_ratio,
            image_url=image_path,
            end_image_url=end_image_url,
            generate_audio=generate_audio,
        )
        args = _adapt_args_for_kling_v3(endpoint_id, args)
        args = _adapt_args_for_seedance_2(endpoint_id, args)
        return await self._dispatch_and_finalize(
            capability="i2v", endpoint_id=endpoint_id, args=args, entry=entry,
            model_name_used=model_name, audio_url=audio_url, lipsync_model_name=lipsync_model_name,
            meta={"duration": duration, "resolution": resolution, "aspect_ratio": aspect_ratio},
        )

    async def generate_with_reference_images(
        self, prompt: str, reference_images: List[str], duration: int = 5,
        resolution: str = "720p", aspect_ratio: str = "16:9",
        model_name: Optional[str] = None, generate_audio: bool = False,
        reference_videos: Optional[List[str]] = None,
        reference_audios: Optional[List[str]] = None,
    ) -> dict:
        reference_videos = reference_videos or []
        reference_audios = reference_audios or []

        endpoint_id, entry = self._resolve_endpoint(model_name, capability="reference")
        if "bytedance/seedance-2.0" in endpoint_id:
            if reference_audios and not reference_images and not reference_videos:
                return {
                    "success": False,
                    "error": "Seedance reference audio requires at least one reference image or video.",
                }
            args = FalService.build_video_args(
                prompt=prompt,
                duration=duration,
                resolution=resolution,
                aspect_ratio=aspect_ratio,
                generate_audio=generate_audio,
            )
            if reference_images:
                args["image_urls"] = reference_images
            if reference_videos:
                args["video_urls"] = reference_videos
            if reference_audios:
                args["audio_urls"] = reference_audios
            args = _adapt_args_for_seedance_2(endpoint_id, args)
            return await self._dispatch_and_finalize(
                capability="reference",
                endpoint_id=endpoint_id,
                args=args,
                entry=entry,
                model_name_used=model_name,
                audio_url=None,
                lipsync_model_name=None,
                meta={"duration": duration, "resolution": resolution, "aspect_ratio": aspect_ratio},
            )

        if not reference_images:
            return {"success": False, "error": "Selected model requires at least one reference image."}
        return await self.generate_clip(
            prompt=prompt, duration=duration, resolution=resolution,
            aspect_ratio=aspect_ratio, model_name=model_name,
            generate_audio=generate_audio, reference_images=reference_images,
        )

    async def generate_with_elements(
        self, prompt: str,
        element_images: Optional[List[str]] = None,
        element_videos: Optional[List[str]] = None,
        element_voices: Optional[List[str]] = None,
        duration: int = 5, resolution: str = "720p", aspect_ratio: str = "16:9",
        model_name: Optional[str] = None, generate_audio: bool = False,
        audio_url: Optional[str] = None,
        lipsync_model_name: Optional[str] = None,
    ) -> dict:
        if not element_images and not element_videos:
            return {"success": False, "error": "No elements provided"}
        return await self.generate_clip(
            prompt=prompt, duration=duration, resolution=resolution,
            aspect_ratio=aspect_ratio, model_name=model_name,
            generate_audio=generate_audio, element_images=element_images,
            element_videos=element_videos, element_voices=element_voices,
            audio_url=audio_url,
            lipsync_model_name=lipsync_model_name,
        )

    async def generate_with_interpolation(
        self, prompt: str, first_frame_path: str, last_frame_path: str,
        duration: int = 5, resolution: str = "720p", aspect_ratio: str = "16:9",
        model_name: Optional[str] = None, generate_audio: bool = False,
        audio_url: Optional[str] = None, lipsync_model_name: Optional[str] = None,
    ) -> dict:
        return await self.generate_from_image(
            prompt=prompt, image_path=first_frame_path, end_image_url=last_frame_path,
            duration=duration, resolution=resolution, aspect_ratio=aspect_ratio,
            model_name=model_name, generate_audio=generate_audio,
            audio_url=audio_url, lipsync_model_name=lipsync_model_name,
        )

    async def extend_video(
        self, original_video: str, prompt: str,
        duration: int = 5, resolution: str = "720p", aspect_ratio: str = "16:9",
        model_name: Optional[str] = None, audio_url: Optional[str] = None,
        lipsync_model_name: Optional[str] = None,
        generate_audio: bool = False,
    ) -> dict:
        if not original_video:
            return {"success": False, "error": "No input video provided"}
        return await self.generate_clip(
            prompt=prompt, duration=duration, resolution=resolution,
            aspect_ratio=aspect_ratio, model_name=model_name,
            audio_url=audio_url, generate_audio=generate_audio,
            reference_video=original_video,
            lipsync_model_name=lipsync_model_name,
        )

    async def generate_lipsync(
        self,
        *,
        video_url: str,
        audio_url: str,
        model_name: Optional[str] = None,
    ) -> dict:
        if self.use_mock:
            return await self._mock_generate("[lipsync]", 5)
        if not video_url or not audio_url:
            return {"success": False, "error": "Lip Sync requires both a video and an audio input."}

        endpoint_id, entry = self._resolve_lipsync_endpoint(model_name)
        args = FalService.build_lipsync_args(video_url=video_url, audio_url=audio_url)

        return await self._dispatch_and_finalize(
            capability="lipsync",
            endpoint_id=endpoint_id,
            args=args,
            entry=entry,
            model_name_used=model_name,
            audio_url=None,
            lipsync_model_name=None,
            meta={"lipsync_audio_url": audio_url},
        )

    async def generate_avatar(
        self,
        *,
        image_url: str,
        audio_url: str,
        prompt: Optional[str] = None,
        model_name: Optional[str] = None,
        resolution: Optional[str] = None,
        turbo_mode: Optional[bool] = None,
    ) -> dict:
        if self.use_mock:
            return await self._mock_generate("[avatar]", 5)
        if not image_url or not audio_url:
            return {"success": False, "error": "Avatar mode requires both an image and an audio input."}

        endpoint_id, entry = self._resolve_avatar_endpoint(model_name)
        args = {
            "image_url": image_url,
            "audio_url": audio_url,
        }
        is_omnihuman_v15 = "bytedance/omnihuman/v1.5" in endpoint_id
        if is_omnihuman_v15 and prompt and prompt.strip():
            args["prompt"] = prompt.strip()
        if is_omnihuman_v15:
            if resolution in {"720p", "1080p"}:
                args["resolution"] = resolution
            if turbo_mode is not None:
                args["turbo_mode"] = bool(turbo_mode)

        return await self._dispatch_and_finalize(
            capability="avatar",
            endpoint_id=endpoint_id,
            args=args,
            entry=entry,
            model_name_used=model_name,
            audio_url=None,
            lipsync_model_name=None,
            meta={"avatar_audio_url": audio_url, "resolution": resolution},
        )

    # ------------------------------------------------------------------ Core
    async def _dispatch_and_finalize(
        self, *, capability: str, endpoint_id: str, args: dict, entry: dict,
        model_name_used: Optional[str], audio_url: Optional[str],
        lipsync_model_name: Optional[str], meta: dict,
    ) -> dict:
        model_info = {
            "name": entry.get("name", endpoint_id),
            "provider": entry.get("provider", "fal.ai"),
        }
        lipsync_endpoint_id = None
        lipsync_model_resolved = None
        if audio_url:
            lipsync_endpoint_id, lipsync_entry = self._resolve_lipsync_endpoint(lipsync_model_name)
            lipsync_model_resolved = lipsync_entry.get("name", lipsync_model_name or "Kling LipSync")
        meta_lipsync_audio_url = audio_url or meta.get("lipsync_audio_url")
        if settings.fal_video_debug_dry_run:
            debug_payload = {
                "capability": capability,
                "endpoint_id": endpoint_id,
                "arguments": args,
                "model_info": model_info,
                "meta": {
                    **meta,
                    "lipsync_audio_url": meta_lipsync_audio_url,
                    "lipsync_model": lipsync_model_resolved,
                    "lipsync_endpoint_id": lipsync_endpoint_id,
                },
            }
            print("[VideoGenerator] DEBUG dry-run enabled — fal submission skipped")
            print(
                "[VideoGenerator] Debug payload:\n"
                + json.dumps(debug_payload, indent=2, ensure_ascii=False)
            )
            encoded_payload = base64.urlsafe_b64encode(
                json.dumps(debug_payload, ensure_ascii=False).encode("utf-8")
            ).decode("ascii")
            return {
                "success": True,
                "status": "debug_payload",
                "output": f"{_VIDEO_DEBUG_PREFIX}{encoded_payload}",
                "debug_payload": debug_payload,
                "cost": 0.0,
                "model": model_info.get("name"),
                "provider": model_info.get("provider"),
            }

        resp = await self.fal.dispatch_for_generator(
            capability=capability, endpoint_id=endpoint_id, arguments=args,
            model_info=model_info,
            args_meta={
                **meta,
                "lipsync_audio_url": meta_lipsync_audio_url,
                "lipsync_model": lipsync_model_resolved,
                "lipsync_endpoint_id": lipsync_endpoint_id,
            },
        )
        if not resp.get("success"):
            return resp
        if resp.get("status") == "pending_fal":
            return resp

        normalized = FalService.extract_output(capability, resp.get("raw_output"))
        if not normalized.get("success"):
            return normalized

        if audio_url:
            lipsync_resp = await self._apply_lipsync(
                normalized["video_url"],
                audio_url,
                lipsync_model_name=lipsync_model_name,
            )
            if lipsync_resp:
                normalized["video_url"] = lipsync_resp

        normalized["video_url"] = await self._fetch_and_upload(normalized["video_url"]) or normalized["video_url"]
        return await self._with_cost(normalized, endpoint_id, model_info=model_info,
                                     duration_s=meta.get("duration"))

    async def _apply_lipsync(
        self,
        video_url: str,
        audio_url: str,
        *,
        lipsync_model_name: Optional[str] = None,
    ) -> Optional[str]:
        """Chain lipsync onto a generated video (sync mode only)."""
        try:
            lipsync_endpoint_id, lipsync_entry = self._resolve_lipsync_endpoint(lipsync_model_name)
            args = FalService.build_lipsync_args(video_url=video_url, audio_url=audio_url)
            print(
                f"[VideoGenerator] Applying lipsync via "
                f"{lipsync_entry.get('name', lipsync_endpoint_id)} ({lipsync_endpoint_id})"
            )
            resp = await self.fal.submit(lipsync_endpoint_id, args)
            if resp.get("mode") == "webhook":
                # When webhooks are globally enabled but this call is not inside
                # a workflow context, submit() returns webhook mode. Drain it to
                # keep lipsync chaining deterministic.
                status = await self.fal.fetch_result(lipsync_endpoint_id, resp.get("request_id", ""))
                if status.get("status") == "COMPLETED":
                    out = FalService.extract_output("lipsync", status.get("output"))
                    if out.get("success"):
                        return out.get("video_url")
            if resp.get("mode") == "sync":
                out = FalService.extract_output("lipsync", resp.get("output"))
                if out.get("success"):
                    return out.get("video_url")
        except Exception as e:
            print(f"[VideoGenerator] lipsync chain failed: {e}")
        return None

    async def _with_cost(
        self, output: dict, endpoint_id: str, *,
        model_info: dict, duration_s: Optional[float] = None,
    ) -> dict:
        from app.core.database import get_database
        from app.services.fal_pricing import FalPricingService

        try:
            pricing = FalPricingService(get_database())
            cost_info = await pricing.compute_cost_usd(endpoint_id, duration_s=duration_s)
            output["cost"] = cost_info["cost_usd"]
        except Exception as e:
            print(f"[VideoGenerator] cost calc failed: {e}")
            output["cost"] = 0.0
        output["model"] = model_info.get("name")
        output["provider"] = model_info.get("provider")
        return output
