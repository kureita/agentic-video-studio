"""Audio Generator Service — Uses fal.ai for voice design, voice cloning, music, and sound effects.

All methods auto-dispatch:
  * Inside a workflow task with `FAL_WEBHOOK_PUBLIC_URL` set → submit + return `pending_fal`.
  * Otherwise (ad-hoc/sync) → block on `fal_client.subscribe`, post-process, return final url.
"""

from __future__ import annotations

import inspect
import os
import random
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Optional
from urllib.parse import quote

import httpx

from app.core.config import settings
from app.core.dependencies import get_storage_service
from app.core.model_registry import (
    get_model_by_id,
    get_model_by_name,
    resolve_endpoint_id,
)
from app.services.fal_service import FalService
from app.services.storage_service import S3StorageService


_DEFAULT_VOICE_DESIGN_ENDPOINT = "fal-ai/minimax/voice-design"
_DEFAULT_VOICE_CLONE_ENDPOINT = "fal-ai/minimax/voice-clone"
_DEFAULT_MUSIC_ENDPOINT = "fal-ai/elevenlabs/music"
_DEFAULT_SFX_ENDPOINT = "fal-ai/elevenlabs/sound-effects/v2"


class AudioGenerator:
    """Generates voice previews, music, and SFX via fal.ai."""

    def __init__(self) -> None:
        use_mock_audio = os.getenv("USE_MOCK_AUDIO", "").lower() == "true"
        self.use_mock = use_mock_audio or settings.use_mock_veo
        self.storage = get_storage_service()
        self.fal = FalService()

        if self.use_mock:
            print("[AudioGenerator] MOCK mode — reusing local audio assets")
        else:
            print("[AudioGenerator] PRODUCTION mode — using fal.ai")

    # ------------------------------------------------------------------ Mock
    def _get_mock_audio(self) -> Optional[Path]:
        try:
            output_dir = Path("static/audio")
            if output_dir.exists():
                audios = list(output_dir.glob("*.mp3")) + list(output_dir.glob("*.wav"))
                if audios:
                    return random.choice(audios)
        except Exception:
            pass
        return None

    async def _mock_generate(self, text: str, voice: str) -> dict[str, Any]:
        print(f"[AudioGenerator] MOCK: {text[:80]}...")
        mock_source = self._get_mock_audio()

        if mock_source and not mock_source.name.startswith("mock_"):
            try:
                with open(mock_source, "rb") as f:
                    content = f.read()
                filename = f"mock_reuse_{int(time.time())}.{mock_source.suffix.lstrip('.')}"
                audio_url = await self.storage.upload_file(content, filename, "audio/mpeg")
                return {"success": True, "audio_url": audio_url, "text": text,
                        "voice": voice, "mock": True}
            except Exception:
                return {"success": True,
                        "audio_url": f"{settings.api_base_url}/static/audio/{mock_source.name}",
                        "text": text, "voice": voice, "mock": True}

        return {"success": False, "error": "Mock audio generation requires a local audio asset"}

    # ------------------------------------------------------------------ Helpers
    async def _fetch_and_upload(self, url: str, suffix: str = "mp3") -> Optional[str]:
        if not url:
            return None
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=120.0)
            if response.status_code == 200:
                filename = f"audio_{int(time.time())}_{random.randint(1000, 9999)}.{suffix}"
                return await self.storage.upload_file(response.content, filename, "audio/mpeg")
        except Exception as e:
            print(f"[AudioGenerator] fetch failed: {e}")
        return url

    def _provider_fetchable_url(self, url: str) -> str:
        """Return a short unauthenticated URL that fal can fetch."""
        if not url:
            return url
        try:
            if not S3StorageService.is_s3_url(url):
                return url

            raw_url = S3StorageService.strip_presigned_params(url)
            api_base = (settings.api_base_url or "").rstrip("/")
            if not api_base or "localhost" in api_base or "127.0.0.1" in api_base:
                return S3StorageService().get_presigned_url(raw_url)

            api_prefix = "" if api_base.endswith("/api") else "/api"
            return f"{api_base}{api_prefix}/public/media-proxy?url={quote(raw_url, safe='')}"
        except Exception:
            return url

    def _probe_audio_duration(self, path: str) -> Optional[float]:
        if not shutil.which("ffprobe"):
            return None
        try:
            result = subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "default=noprint_wrappers=1:nokey=1",
                    path,
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=20,
            )
            return float(result.stdout.strip())
        except Exception as exc:
            print(f"[AudioGenerator] ffprobe duration failed: {exc}")
            return None

    def _transcode_voice_clone_source(self, input_path: str, output_path: str, duration: Optional[float]) -> bool:
        if not shutil.which("ffmpeg"):
            return False

        # MiniMax voice clone rejects very short samples. Loop short clips to a
        # little over 10s, and trim overlong clips to stay inside provider limits.
        target_seconds = 11.0 if duration is None or duration < 10.0 else min(duration, 300.0)
        loop_args = ["-stream_loop", "-1"] if duration is None or duration < 10.0 else []

        command = [
            "ffmpeg",
            "-y",
            *loop_args,
            "-i",
            input_path,
            "-t",
            f"{target_seconds:.2f}",
            "-vn",
            "-ac",
            "1",
            "-ar",
            "44100",
            "-b:a",
            "128k",
            output_path,
        ]

        try:
            subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
                timeout=120,
            )
            return Path(output_path).exists() and Path(output_path).stat().st_size > 0
        except Exception as exc:
            print(f"[AudioGenerator] voice clone source transcode failed: {exc}")
            return False

    async def _upload_voice_clone_source(
        self,
        data: bytes,
        filename: str,
        content_type: str,
        path: Optional[str] = None,
    ) -> str:
        """Prefer fal's CDN for model inputs; fall back to our storage."""
        try:
            import fal_client  # type: ignore

            upload_file = getattr(fal_client, "upload_file", None)
            if path and callable(upload_file):
                result = upload_file(path)
                if inspect.isawaitable(result):
                    result = await result
                if isinstance(result, str) and result.startswith("http"):
                    return result

            upload = getattr(fal_client, "upload", None)
            if callable(upload):
                result = upload(data, content_type, file_name=filename)
                if inspect.isawaitable(result):
                    result = await result
                if isinstance(result, str) and result.startswith("http"):
                    return result
        except Exception as exc:
            print(f"[AudioGenerator] fal CDN byte upload failed: {exc}")

        uploaded_url = await self.storage.upload_file(data, filename, content_type)
        return self._provider_fetchable_url(uploaded_url)

    async def _prepare_voice_clone_source(self, audio_url: str) -> Optional[str]:
        """Normalize clone samples so MiniMax accepts them.

        The provider requires a real audio file, and in practice rejects short
        generated previews with HTTP 422. We download the source, transcode it
        to MP3, loop short clips to 11s, upload the repaired file, and pass fal
        a short public proxy URL.
        """
        source_url = self._provider_fetchable_url(audio_url)
        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=120.0) as client:
                response = await client.get(source_url)
            if response.status_code != 200 or not response.content:
                print(f"[AudioGenerator] source audio download failed: HTTP {response.status_code}")
                return source_url

            with tempfile.TemporaryDirectory(prefix="voice_clone_") as tmpdir:
                input_path = str(Path(tmpdir) / "source_audio")
                output_path = str(Path(tmpdir) / "voice_clone_source.mp3")
                Path(input_path).write_bytes(response.content)

                duration = self._probe_audio_duration(input_path)
                print(f"[AudioGenerator] voice clone source duration={duration}")
                if duration is not None and duration < 10.0 and not shutil.which("ffmpeg"):
                    print("[AudioGenerator] voice clone source is too short and ffmpeg is unavailable")
                    return None

                prepared_bytes = response.content
                content_type = response.headers.get("content-type", "audio/mpeg").split(";")[0].strip()
                suffix = "mp3"

                if self._transcode_voice_clone_source(input_path, output_path, duration):
                    prepared_bytes = Path(output_path).read_bytes()
                    content_type = "audio/mpeg"

                filename = f"voice_clone_source_{int(time.time())}_{random.randint(1000, 9999)}.{suffix}"
                upload_path = output_path if Path(output_path).exists() else input_path
                return await self._upload_voice_clone_source(prepared_bytes, filename, content_type, upload_path)
        except Exception as exc:
            print(f"[AudioGenerator] prepare voice clone source failed: {exc}")
            return source_url

    def _resolve_endpoint(self, model_input: Optional[str], default: str, capability: str) -> str:
        return resolve_endpoint_id(
            model_input, default, model_type="audio", capability=capability
        )

    def _model_info(self, endpoint_id: str, fallback_name: str) -> dict[str, Any]:
        from app.core.model_registry import get_model_by_endpoint_id
        entry = get_model_by_endpoint_id(endpoint_id) or {}
        return {
            "name": entry.get("name", fallback_name),
            "provider": entry.get("provider", "fal.ai"),
            "fallback_price": entry.get("fallback_price"),
        }

    # ------------------------------------------------------------------ Public API
    async def generate_voice_design(
        self,
        *,
        prompt: str,
        preview_text: str,
        model_id: Optional[str] = None,
    ) -> dict[str, Any]:
        if self.use_mock:
            return await self._mock_generate(preview_text, "voice-design")
        if not prompt or not prompt.strip():
            return {"success": False, "error": "No voice description prompt provided"}
        if not preview_text or not preview_text.strip():
            return {"success": False, "error": "No preview text provided"}

        preview_text = preview_text.strip()[:500]
        endpoint_id = self._resolve_endpoint(model_id, _DEFAULT_VOICE_DESIGN_ENDPOINT, "voice_design")
        args = FalService.build_voice_design_args(prompt=prompt.strip(), preview_text=preview_text)
        model_info = self._model_info(endpoint_id, "MiniMax Voice Design")

        resp = await self.fal.dispatch_for_generator(
            capability="voice_design",
            endpoint_id=endpoint_id,
            arguments=args,
            model_info=model_info,
            args_meta={"chars": len(preview_text)},
        )
        if not resp.get("success"):
            return resp
        if resp.get("status") == "pending_fal":
            return resp

        output = FalService.extract_output("voice_design", resp.get("raw_output"))
        if not output.get("success"):
            return output
        output["audio_url"] = await self._fetch_and_upload(output["audio_url"])
        return await self._with_cost(output, endpoint_id, chars=len(preview_text), model_info=model_info)

    async def generate_voice_clone(
        self,
        *,
        audio_url: str,
        text: Optional[str] = None,
        preview_model: str = "speech-02-hd",
        model_id: Optional[str] = None,
    ) -> dict[str, Any]:
        preview_text = (text or "Hello, this is a preview of your cloned voice! I hope you like it!").strip()
        if self.use_mock:
            return await self._mock_generate(preview_text, "voice-clone")
        if not audio_url:
            return {"success": False, "error": "No source audio provided for voice cloning"}

        allowed_models = {"speech-02-hd", "speech-02-turbo", "speech-01-hd", "speech-01-turbo"}
        if preview_model not in allowed_models:
            preview_model = "speech-02-hd"

        prepared_audio_url = await self._prepare_voice_clone_source(audio_url)
        if not prepared_audio_url:
            return {
                "success": False,
                "error": (
                    "Voice clone source audio is shorter than MiniMax's 10 second minimum, "
                    "and the server could not repair it because ffmpeg is unavailable."
                ),
            }
        audio_url = prepared_audio_url
        endpoint_id = self._resolve_endpoint(model_id, _DEFAULT_VOICE_CLONE_ENDPOINT, "voice_clone")
        args = FalService.build_voice_clone_args(
            audio_url=audio_url,
            text=preview_text,
            model=preview_model,
            noise_reduction=True,
            need_volume_normalization=True,
        )
        model_info = self._model_info(endpoint_id, "MiniMax Instant Voice Cloning")

        resp = await self.fal.dispatch_for_generator(
            capability="voice_clone",
            endpoint_id=endpoint_id,
            arguments=args,
            model_info=model_info,
            args_meta={"chars": len(preview_text), "preview_model": preview_model},
        )
        if not resp.get("success"):
            error_text = str(resp.get("error") or "")
            if "422" in error_text:
                resp["error"] = (
                    "Voice clone request was rejected by MiniMax (422). "
                    "Use a source audio clip between 10 seconds and 5 minutes, "
                    "preferably MP3/WAV/M4A, and try again."
                )
            return resp
        if resp.get("status") == "pending_fal":
            return resp

        output = FalService.extract_output("voice_clone", resp.get("raw_output"))
        if not output.get("success"):
            return output
        output["audio_url"] = await self._fetch_and_upload(output["audio_url"])
        return await self._with_cost(output, endpoint_id, chars=len(preview_text), model_info=model_info)

    async def generate_music(
        self, prompt: str, duration: Optional[float] = None, model_id: Optional[str] = None,
    ) -> dict[str, Any]:
        if self.use_mock:
            return await self._mock_generate(prompt, "music")
        if not prompt or not prompt.strip():
            return {"success": False, "error": "No prompt provided for music generation"}

        endpoint_id = self._resolve_endpoint(model_id, _DEFAULT_MUSIC_ENDPOINT, "music")
        args = FalService.build_music_args(prompt=prompt, duration_s=duration)
        model_info = self._model_info(endpoint_id, "Music")

        resp = await self.fal.dispatch_for_generator(
            capability="music", endpoint_id=endpoint_id, arguments=args,
            model_info=model_info, args_meta={"duration": duration},
        )
        if not resp.get("success"):
            return resp
        if resp.get("status") == "pending_fal":
            return resp

        output = FalService.extract_output("music", resp.get("raw_output"))
        if not output.get("success"):
            return output
        output["audio_url"] = await self._fetch_and_upload(output["audio_url"])
        return await self._with_cost(output, endpoint_id, duration_s=duration, model_info=model_info)

    async def generate_sfx(
        self, prompt: str, duration: Optional[float] = None, model_id: Optional[str] = None,
    ) -> dict[str, Any]:
        if self.use_mock:
            return await self._mock_generate(prompt, "sfx")
        if not prompt or not prompt.strip():
            return {"success": False, "error": "No prompt provided for sound effects"}

        endpoint_id = self._resolve_endpoint(model_id, _DEFAULT_SFX_ENDPOINT, "sfx")
        args = FalService.build_sfx_args(prompt=prompt, duration_s=duration)
        model_info = self._model_info(endpoint_id, "SFX")

        resp = await self.fal.dispatch_for_generator(
            capability="sfx", endpoint_id=endpoint_id, arguments=args,
            model_info=model_info, args_meta={"duration": duration},
        )
        if not resp.get("success"):
            return resp
        if resp.get("status") == "pending_fal":
            return resp

        output = FalService.extract_output("sfx", resp.get("raw_output"))
        if not output.get("success"):
            return output
        output["audio_url"] = await self._fetch_and_upload(output["audio_url"])
        return await self._with_cost(output, endpoint_id, duration_s=duration, model_info=model_info)

    # ------------------------------------------------------------------ Billing
    async def _with_cost(
        self, output: dict[str, Any], endpoint_id: str, *,
        duration_s: Optional[float] = None, chars: Optional[int] = None,
        model_info: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        from app.core.database import get_database
        from app.services.fal_pricing import FalPricingService

        try:
            pricing = FalPricingService(get_database())
            cost_info = await pricing.compute_cost_usd(
                endpoint_id, duration_s=duration_s, chars=chars,
            )
            output["cost"] = cost_info["cost_usd"]
        except Exception as e:
            print(f"[AudioGenerator] pricing calc failed: {e}")
            output["cost"] = 0.0
        if model_info:
            output["model"] = model_info.get("name")
            output["provider"] = model_info.get("provider")
        return output
