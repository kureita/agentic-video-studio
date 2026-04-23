import json
import os
import time
import base64
import mimetypes
import re
import subprocess
import tempfile
from typing import Dict, Any, List, Optional
from copy import deepcopy
from pydantic import BaseModel
from openai import AsyncOpenAI
import httpx

from app.core.config import settings
from app.core.model_registry import (
    AUDIO_MODELS,
    IMAGE_MODELS,
    VIDEO_MODELS,
    get_model_by_endpoint_id,
    get_model_by_id,
    get_model_by_name,
    resolve_endpoint_id,
)
from app.services.chat_model_registry import CHAT_MODELS
from app.services.firecrawl_service import FirecrawlService
from app.services.storage_service import S3StorageService

TEXT_REFERENCE_PATTERN = re.compile(r"@Text\s*#(\d+)", re.IGNORECASE)

class AgentService:
    def __init__(self):
        self.openrouter_api_key = settings.openrouter_api_key
        
        self.openrouter_client = None
        if self.openrouter_api_key:
            self.openrouter_client = AsyncOpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=self.openrouter_api_key,
                default_headers={
                    "HTTP-Referer": settings.api_base_url,
                    "X-Title": "Kureita"
                }
            )
            
        self.firecrawl_service = FirecrawlService()
        self._default_video_model_id = "kling-video-v3-standard"
        self._default_video_endpoint = "fal-ai/kling-video/v3/standard/text-to-video"
        self._chat_models_cache: Optional[List[Dict[str, Any]]] = None
        self._chat_models_cache_ts: float = 0.0

    async def _fetch_openrouter_modalities_map(self) -> Dict[str, List[str]]:
        if self._chat_models_cache is not None and (time.time() - self._chat_models_cache_ts) < 3600:
            return {
                str(model.get("openrouter_model")): list(model.get("input_modalities", []))
                for model in self._chat_models_cache
            }

        headers = {
            "HTTP-Referer": settings.api_base_url,
            "X-Title": "Kureita",
        }
        if self.openrouter_api_key:
            headers["Authorization"] = f"Bearer {self.openrouter_api_key}"

        modalities_by_model: Dict[str, List[str]] = {}
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.get("https://openrouter.ai/api/v1/models", headers=headers)
                response.raise_for_status()
                payload = response.json()

            for model in payload.get("data", []):
                model_id = str(model.get("id") or "")
                architecture = model.get("architecture") or {}
                input_modalities = architecture.get("input_modalities") or []
                if model_id and isinstance(input_modalities, list):
                    modalities_by_model[model_id] = [
                        str(modality).lower()
                        for modality in input_modalities
                        if isinstance(modality, str)
                    ]
        except Exception as err:
            print(f"[AgentService] Failed to fetch OpenRouter model metadata: {err}")

        return modalities_by_model

    async def get_chat_models(self) -> List[Dict[str, Any]]:
        modalities_by_model = await self._fetch_openrouter_modalities_map()
        models: List[Dict[str, Any]] = []

        for config in CHAT_MODELS:
            input_modalities = modalities_by_model.get(
                str(config.get("openrouter_model")),
                [str(modality).lower() for modality in config.get("fallback_input_modalities", ["text"])],
            )
            normalized_modalities = []
            for modality in input_modalities:
                lowered = str(modality).lower()
                if lowered not in normalized_modalities:
                    normalized_modalities.append(lowered)

            models.append({
                **config,
                "input_modalities": normalized_modalities,
                "is_multimodal": any(modality != "text" for modality in normalized_modalities),
            })

        self._chat_models_cache = models
        self._chat_models_cache_ts = time.time()
        return models

    async def _resolve_chat_model_config(self, display_name: str) -> Dict[str, Any]:
        models = await self.get_chat_models()
        for model in models:
            if model.get("display_name") == display_name:
                return model
        return models[0]

    async def _pick_best_chat_model_for_modalities(self, required_modalities: List[str]) -> Dict[str, Any]:
        models = await self.get_chat_models()
        normalized_required = [m for m in required_modalities if m and m != "text"]
        for model in models:
            input_modalities = set(model.get("input_modalities", []))
            if all(modality in input_modalities for modality in normalized_required):
                return model
        return models[0]

    def _get_attachment_summary(self, attachments: List[Dict[str, Any]]) -> str:
        if not attachments:
            return "None"
        summary_parts = []
        for attachment in attachments:
            filename = str(attachment.get("filename") or "file")
            media_type = str(attachment.get("type") or "application/octet-stream")
            file_url = str(attachment.get("url") or "").strip()
            if file_url:
                summary_parts.append(f"[Attached: {filename}] ({media_type}) - URL: {file_url}")
            else:
                summary_parts.append(f"[Attached: {filename}] ({media_type})")
        return "\n".join(summary_parts)

    def _infer_attachment_modalities(self, attachments: List[Dict[str, Any]]) -> List[str]:
        modalities: List[str] = []
        for attachment in attachments:
            media_type = str(attachment.get("type") or "").lower()
            if media_type.startswith("image/") and "image" not in modalities:
                modalities.append("image")
            elif media_type.startswith("audio/") and "audio" not in modalities:
                modalities.append("audio")
            elif media_type.startswith("video/") and "image" not in modalities:
                # Chat-side video understanding degrades to extracted representative frames,
                # so an image-capable model is sufficient even when native video input is absent.
                modalities.append("image")
        return modalities

    async def _fetch_attachment_bytes(self, attachment: Dict[str, Any]) -> tuple[Optional[bytes], Optional[str], Optional[str]]:
        file_url = str(attachment.get("url") or "").strip()
        if not file_url:
            return None, None, None

        media_type = str(attachment.get("type") or "").strip().lower()
        if not media_type:
            guessed_type, _ = mimetypes.guess_type(file_url)
            media_type = str(guessed_type or "application/octet-stream")

        source_url = file_url
        if S3StorageService.is_s3_url(file_url):
            source_url = S3StorageService().get_presigned_url(file_url)

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.get(source_url)
                response.raise_for_status()
                return response.content, media_type, source_url
        except Exception as err:
            print(f"[AgentService] Failed to fetch attachment '{file_url}': {err}")
            return None, media_type, source_url

    def _extract_video_frame_data_urls(self, video_bytes: bytes) -> List[str]:
        frame_urls: List[str] = []
        tmp_video_path = ""
        tmp_frame_path = ""

        try:
            os.makedirs("tmp", exist_ok=True)
            with tempfile.NamedTemporaryFile(suffix=".mp4", dir="tmp", delete=False) as tmp_video:
                tmp_video.write(video_bytes)
                tmp_video_path = tmp_video.name

            for frame_type in ("start_frame", "end_frame"):
                tmp_frame_path = tmp_video_path.replace(".mp4", f"_{frame_type}.jpg")

                if frame_type == "end_frame":
                    duration_result = subprocess.run(
                        [
                            "ffprobe",
                            "-v",
                            "error",
                            "-show_entries",
                            "format=duration",
                            "-of",
                            "default=noprint_wrappers=1:nokey=1",
                            tmp_video_path,
                        ],
                        capture_output=True,
                        text=True,
                        timeout=30,
                    )
                    duration = float(duration_result.stdout.strip()) if duration_result.stdout.strip() else 0.0
                    seek_time = max(0.0, duration - 0.1)
                    subprocess.run(
                        [
                            "ffmpeg",
                            "-y",
                            "-ss",
                            str(seek_time),
                            "-i",
                            tmp_video_path,
                            "-frames:v",
                            "1",
                            "-q:v",
                            "2",
                            tmp_frame_path,
                        ],
                        capture_output=True,
                        timeout=30,
                    )
                else:
                    subprocess.run(
                        [
                            "ffmpeg",
                            "-y",
                            "-i",
                            tmp_video_path,
                            "-frames:v",
                            "1",
                            "-q:v",
                            "2",
                            tmp_frame_path,
                        ],
                        capture_output=True,
                        timeout=30,
                    )

                if os.path.exists(tmp_frame_path) and os.path.getsize(tmp_frame_path) > 0:
                    with open(tmp_frame_path, "rb") as frame_file:
                        encoded_frame = base64.b64encode(frame_file.read()).decode("utf-8")
                    frame_urls.append(f"data:image/jpeg;base64,{encoded_frame}")

                if os.path.exists(tmp_frame_path):
                    os.unlink(tmp_frame_path)
                tmp_frame_path = ""
        except Exception as err:
            print(f"[AgentService] Failed to extract video frames: {err}")
        finally:
            for path in (tmp_frame_path, tmp_video_path):
                if path and os.path.exists(path):
                    try:
                        os.unlink(path)
                    except Exception:
                        pass

        return frame_urls

    async def _build_multimodal_content_parts(
        self,
        attachments: List[Dict[str, Any]],
        supports_video: bool,
    ) -> List[Dict[str, Any]]:
        parts: List[Dict[str, Any]] = []

        for attachment in attachments:
            file_bytes, media_type, source_url = await self._fetch_attachment_bytes(attachment)
            if not file_bytes or not media_type:
                continue

            if media_type.startswith("image/"):
                encoded = base64.b64encode(file_bytes).decode("utf-8")
                parts.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:{media_type};base64,{encoded}"},
                })
            elif media_type.startswith("audio/"):
                encoded = base64.b64encode(file_bytes).decode("utf-8")
                audio_format = media_type.split("/")[-1].split(";")[0].strip().lower() or "wav"
                parts.append({
                    "type": "input_audio",
                    "input_audio": {"data": encoded, "format": audio_format},
                })
            elif media_type.startswith("video/"):
                note = (
                    "A video attachment was provided. Representative start and end frames are attached next "
                    "to help with direct chat analysis."
                )
                if supports_video and source_url:
                    note = (
                        "A video attachment was provided. Representative start and end frames are attached next "
                        "to ground analysis reliably for this turn."
                    )
                parts.append({"type": "text", "text": note})

                frame_urls = self._extract_video_frame_data_urls(file_bytes)
                for frame_url in frame_urls:
                    parts.append({
                        "type": "image_url",
                        "image_url": {"url": frame_url, "detail": "low"},
                    })

        return parts

    def _resolve_video_model_entry(self, model_input: str) -> Optional[Dict[str, Any]]:
        if not model_input:
            return get_model_by_id(self._default_video_model_id)

        by_id = get_model_by_id(model_input)
        if by_id and by_id.get("type") == "video":
            return by_id

        by_name = get_model_by_name(model_input)
        if by_name and by_name.get("type") == "video":
            return by_name

        endpoint_id = resolve_endpoint_id(
            model_input=model_input,
            fallback_endpoint_id=self._default_video_endpoint,
            model_type="video",
        )
        by_ep = get_model_by_endpoint_id(endpoint_id)
        if by_ep and by_ep.get("type") == "video":
            return by_ep

        return get_model_by_endpoint_id(self._default_video_endpoint)

    def _pick_best_video_model(
        self,
        need_i2v: bool,
        need_audio: bool,
        need_reference: bool = False,
        need_elements: bool = False,
        need_v2v: bool = False,
    ) -> Dict[str, Any]:
        def has_caps(entry: Dict[str, Any]) -> bool:
            caps = {c.lower() for c in entry.get("capabilities", [])}
            return (
                (not need_i2v or "i2v" in caps)
                and (not need_audio or "audio" in caps)
                and (not need_reference or "reference" in caps)
                and (not need_elements or "elements" in caps)
                and (not need_v2v or "v2v" in caps)
            )

        candidates = [m for m in VIDEO_MODELS if has_caps(m)]
        if not candidates:
            return get_model_by_id(self._default_video_model_id) or VIDEO_MODELS[0]

        def rank(entry: Dict[str, Any]) -> int:
            tier = str(entry.get("tier", "budget")).lower()
            return {"pro": 0, "premium": 0, "mid": 1, "cost": 2, "budget": 2}.get(tier, 3)

        candidates.sort(key=rank)
        return candidates[0]

    def _resolve_audio_model_entry(self, model_input: str) -> Optional[Dict[str, Any]]:
        if not model_input:
            return None

        by_id = get_model_by_id(model_input)
        if by_id and by_id.get("type") == "audio":
            return by_id

        by_name = get_model_by_name(model_input)
        if by_name and by_name.get("type") == "audio":
            return by_name

        endpoint_id = resolve_endpoint_id(
            model_input=model_input,
            fallback_endpoint_id="fal-ai/minimax/speech-2.8-turbo",
            model_type="audio",
        )
        by_ep = get_model_by_endpoint_id(endpoint_id)
        if by_ep and by_ep.get("type") == "audio":
            return by_ep
        return None

    def _pick_best_audio_model(self, category: str) -> Optional[Dict[str, Any]]:
        candidates = [
            m for m in AUDIO_MODELS
            if str(m.get("category", "")).lower() == category.lower() and not bool(m.get("coming_soon", False))
        ]
        if not candidates:
            return None

        def rank(entry: Dict[str, Any]) -> int:
            tier = str(entry.get("tier", "budget")).lower()
            return {"pro": 0, "premium": 0, "mid": 1, "cost": 2, "budget": 2}.get(tier, 3)

        candidates.sort(key=rank)
        return candidates[0]

    def _normalize_audio_nodes_for_category(self, nodes: List[Dict[str, Any]]) -> tuple[List[Dict[str, Any]], List[str]]:
        """Ensure audioGen model category matches audioType (speech/music/sfx)."""
        normalized_nodes = deepcopy(nodes)
        warnings: List[str] = []
        type_to_category = {"speech": "tts", "music": "music", "sfx": "sfx"}

        for node in normalized_nodes:
            if node.get("type") != "audioGen":
                continue

            node_data = node.get("data", {})
            if not isinstance(node_data, dict):
                continue

            audio_type = str(node_data.get("audioType", "speech")).lower()
            expected_category = type_to_category.get(audio_type, "tts")
            selected_model = str(node_data.get("model") or "")
            entry = self._resolve_audio_model_entry(selected_model) if selected_model else None
            selected_category = str((entry or {}).get("category", "")).lower()

            if (not entry) or selected_category != expected_category or bool((entry or {}).get("coming_soon", False)):
                replacement = self._pick_best_audio_model(expected_category)
                if replacement:
                    replacement_id = str(replacement.get("id") or replacement.get("name") or "")
                    node_data["model"] = replacement_id
                    warnings.append(
                        f"Node '{node.get('id', 'unknown')}' audio model adjusted to '{replacement_id}' for audioType '{audio_type}'."
                    )
            elif entry:
                # Canonicalize model field to its stable id so the frontend menu matches.
                canonical_id = str(entry.get("id") or "")
                if canonical_id and node_data.get("model") != canonical_id:
                    node_data["model"] = canonical_id
            node["data"] = node_data

        return normalized_nodes, warnings

    def _normalize_video_nodes_for_capabilities(
        self,
        nodes: List[Dict[str, Any]],
        edges: List[Dict[str, Any]],
    ) -> tuple[List[Dict[str, Any]], List[str]]:
        """Ensure assistant-selected video model/audio combos match registry capabilities."""
        normalized_nodes = deepcopy(nodes)
        warnings: List[str] = []

        target_handles_by_target: Dict[str, set[str]] = {}
        for e in edges or []:
            target = e.get("target")
            if not target:
                continue
            target_handle = e.get("targetHandle") or e.get("target_handle") or ""
            if isinstance(target_handle, str) and target_handle:
                target_handles_by_target.setdefault(str(target), set()).add(target_handle)

        def infer_mode_from_handles(handles: set[str]) -> str:
            if any(h.endswith("elements_image") or h.endswith("elements_video") or h.endswith("elements_audio") for h in handles):
                return "elements"
            if any(h.endswith("reference_video") for h in handles):
                return "v2v"
            if any(h.endswith("reference_image") or h.endswith("reference_images") for h in handles):
                return "reference"
            if any(h.endswith("start_image") or h.endswith("end_image") for h in handles):
                return "i2v"
            return "auto"

        for node in normalized_nodes:
            if node.get("type") != "videoGen":
                continue

            node_data = node.get("data", {})
            if not isinstance(node_data, dict):
                continue

            node_id = str(node.get("id", ""))
            handles = target_handles_by_target.get(node_id, set())
            inferred_mode = infer_mode_from_handles(handles)
            raw_mode = str(node_data.get("inputMode") or "auto").strip().lower()
            if raw_mode == "t2v":
                raw_mode = "auto"
            if raw_mode not in {"auto", "i2v", "reference", "elements", "v2v"}:
                raw_mode = "auto"

            # Connected assets always take precedence over stale mode settings.
            final_mode = inferred_mode if inferred_mode != "auto" else raw_mode
            if final_mode == "t2v":
                final_mode = "auto"
            if node_data.get("inputMode") != final_mode:
                node_data["inputMode"] = final_mode

            requested_model = str(node_data.get("model") or self._default_video_model_id)
            entry = self._resolve_video_model_entry(requested_model)
            if not entry:
                continue

            caps = {c.lower() for c in entry.get("capabilities", [])}
            need_i2v = final_mode == "i2v"
            need_reference = final_mode == "reference"
            need_elements = final_mode == "elements"
            need_v2v = final_mode == "v2v"
            wants_audio = bool(node_data.get("generateAudio", False))

            supports_i2v = "i2v" in caps
            supports_reference = "reference" in caps
            supports_elements = "elements" in caps
            supports_v2v = "v2v" in caps
            supports_audio = "audio" in caps

            if (
                (need_i2v and not supports_i2v)
                or (need_reference and not supports_reference)
                or (need_elements and not supports_elements)
                or (need_v2v and not supports_v2v)
                or (wants_audio and not supports_audio)
            ):
                replacement = self._pick_best_video_model(
                    need_i2v=need_i2v,
                    need_audio=wants_audio,
                    need_reference=need_reference,
                    need_elements=need_elements,
                    need_v2v=need_v2v,
                )
                replacement_id = str(replacement.get("id") or self._default_video_model_id)
                node_data["model"] = replacement_id
                warnings.append(
                    f"Node '{node.get('id', 'unknown')}' model adjusted to '{replacement_id}' for capability compatibility."
                )
            else:
                # Canonicalize model field to its stable id so the frontend menu matches.
                canonical_id = str(entry.get("id") or "")
                if canonical_id and node_data.get("model") != canonical_id:
                    node_data["model"] = canonical_id

            # If a replacement still cannot satisfy audio, force-disable generateAudio.
            final_entry = self._resolve_video_model_entry(str(node_data.get("model", requested_model)))
            final_caps = {c.lower() for c in (final_entry or {}).get("capabilities", [])}
            if bool(node_data.get("generateAudio", False)) and "audio" not in final_caps:
                node_data["generateAudio"] = False
                warnings.append(
                    f"Node '{node.get('id', 'unknown')}' had generateAudio disabled because selected model lacks native audio."
                )

            node["data"] = node_data

        return normalized_nodes, warnings

    def _canonicalize_image_model_ids(self, nodes: List[Dict[str, Any]]) -> tuple[List[Dict[str, Any]], List[str]]:
        """Canonicalize imageGen 'model' fields to stable ids so the UI can find them."""
        normalized = deepcopy(nodes)
        warnings: List[str] = []
        for node in normalized:
            if node.get("type") != "imageGen":
                continue
            node_data = node.get("data", {}) or {}
            if not isinstance(node_data, dict):
                continue
            requested = str(node_data.get("model") or "").strip()
            if not requested:
                continue
            entry = get_model_by_id(requested)
            if not entry or entry.get("type") != "image":
                entry = get_model_by_name(requested)
            if entry and entry.get("type") == "image":
                canonical_id = str(entry.get("id") or "")
                if canonical_id and node_data.get("model") != canonical_id:
                    node_data["model"] = canonical_id
                    node["data"] = node_data
        return normalized, warnings

    def _prune_orphan_nodes(
        self,
        nodes: List[Dict[str, Any]],
        edges: List[Dict[str, Any]],
    ) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[str]]:
        """Remove nodes the chat agent emitted that aren't wired into the workflow.

        A node is considered an orphan and dropped if it has **no** incoming and
        **no** outgoing edges. Comment nodes are always kept (they're annotations).
        mediaUpload nodes are kept if their data.output is a real URL (user may
        add wiring after reviewing).
        """
        if not nodes:
            return nodes, edges, []

        incoming_by_node: Dict[str, int] = {}
        outgoing_by_node: Dict[str, int] = {}
        for edge in edges or []:
            src = str(edge.get("source", "") or "")
            tgt = str(edge.get("target", "") or "")
            if src:
                outgoing_by_node[src] = outgoing_by_node.get(src, 0) + 1
            if tgt:
                incoming_by_node[tgt] = incoming_by_node.get(tgt, 0) + 1

        warnings: List[str] = []
        kept: List[Dict[str, Any]] = []
        dropped_ids: set[str] = set()

        for node in nodes:
            node_id = str(node.get("id", ""))
            node_type = str(node.get("type", ""))
            has_in = incoming_by_node.get(node_id, 0) > 0
            has_out = outgoing_by_node.get(node_id, 0) > 0

            if has_in or has_out:
                kept.append(node)
                continue

            if node_type == "comment":
                kept.append(node)
                continue

            if node_type == "mediaUpload":
                # Keep if it has a concrete output url (user-provided asset).
                output_val = (node.get("data") or {}).get("output")
                if isinstance(output_val, str) and output_val.strip():
                    kept.append(node)
                    continue

            # Single-node workflows are legitimate — keep the only node.
            if len(nodes) == 1:
                kept.append(node)
                continue

            dropped_ids.add(node_id)
            warnings.append(
                f"Removed orphan node '{node_id}' (type={node_type}) with no connections."
            )

        if not dropped_ids:
            return nodes, edges, warnings

        pruned_edges = [
            edge
            for edge in (edges or [])
            if str(edge.get("source", "") or "") not in dropped_ids
            and str(edge.get("target", "") or "") not in dropped_ids
        ]
        return kept, pruned_edges, warnings

    def _synchronize_text_reference_edges(
        self,
        nodes: List[Dict[str, Any]],
        edges: List[Dict[str, Any]],
    ) -> tuple[List[Dict[str, Any]], List[str]]:
        """Ensure explicit text edges exist for any @Text #N prompt/instruction references."""
        normalized_edges = deepcopy(edges)
        warnings: List[str] = []

        text_nodes = [node for node in nodes if node.get("type") == "text"]
        text_node_ids = {str(node.get("id", "")) for node in text_nodes}
        edge_ids = {
            str(edge.get("id"))
            for edge in normalized_edges
            if edge.get("id") is not None
        }

        node_field_map = {
            "imageGen": ("prompt", "text|prompt"),
            "audioGen": ("prompt", "text|prompt"),
            "videoGen": ("prompt", "text|text"),
            "editorAgent": ("instruction", "text|text"),
            "assistant": ("instruction", "text|text"),
            "vision": ("instruction", "text|text"),
        }

        def _make_unique_edge_id(base_id: str) -> str:
            candidate = base_id
            counter = 2
            while candidate in edge_ids:
                candidate = f"{base_id}_{counter}"
                counter += 1
            edge_ids.add(candidate)
            return candidate

        for node in nodes:
            node_type = str(node.get("type", ""))
            field_config = node_field_map.get(node_type)
            if not field_config:
                continue

            field_name, target_handle = field_config
            node_data = node.get("data", {}) or {}
            raw_value = node_data.get(field_name)
            if not isinstance(raw_value, str):
                continue

            match = TEXT_REFERENCE_PATTERN.search(raw_value)
            if not match:
                continue

            text_index = int(match.group(1)) - 1
            if text_index < 0 or text_index >= len(text_nodes):
                continue

            expected_source_id = str(text_nodes[text_index].get("id", ""))
            target_id = str(node.get("id", ""))
            if not expected_source_id or not target_id:
                continue

            updated_edges: List[Dict[str, Any]] = []
            found_expected_edge = False

            for edge in normalized_edges:
                edge_target = str(edge.get("target", ""))
                edge_source = str(edge.get("source", ""))
                edge_target_handle = str(edge.get("targetHandle") or edge.get("target_handle") or "")

                is_text_edge_to_same_handle = (
                    edge_target == target_id
                    and edge_target_handle == target_handle
                    and edge_source in text_node_ids
                )

                if not is_text_edge_to_same_handle:
                    updated_edges.append(edge)
                    continue

                if edge_source == expected_source_id:
                    edge["sourceHandle"] = edge.get("sourceHandle") or "text|text"
                    edge["targetHandle"] = target_handle
                    updated_edges.append(edge)
                    found_expected_edge = True
                    continue

                warnings.append(
                    f"Adjusted text edge for node '{target_id}' to match {match.group(0)}."
                )

            normalized_edges = updated_edges

            if found_expected_edge:
                continue

            normalized_edges.append({
                "id": _make_unique_edge_id(
                    f"edge_{expected_source_id}_{target_id}_{target_handle.split('|')[-1]}"
                ),
                "source": expected_source_id,
                "target": target_id,
                "sourceHandle": "text|text",
                "targetHandle": target_handle,
            })
            warnings.append(
                f"Added missing text edge from '{expected_source_id}' to '{target_id}' for {match.group(0)}."
            )

        return normalized_edges, warnings
        
    async def generate_workflow(
        self,
        prompt: str,
        model: str = "Gemini 3.1 Flash Lite Preview (Low)",
        current_nodes: List[Dict] = [],
        current_edges: List[Dict] = [],
        chat_history: List[Dict] = [],
        attachments: List[Dict[str, Any]] = [],
    ) -> Dict[str, Any]:
        """
        Generate a workflow based on a user prompt using the selected model.
        """
        # Define default API failure response
        failure_response = {
            "success": False,
            "message": "The selected model's API key is not configured.",
            "thinking": None,
            "thinking_duration_ms": None,
            "tool_calls": [],
            "nodes": [],
            "edges": []
        }
        
        # Verify Key Availability
        if not self.openrouter_client:
             return failure_response

        requested_model = await self._resolve_chat_model_config(model)
        effective_model = requested_model
        required_modalities = self._infer_attachment_modalities(attachments)
        selected_input_modalities = set(str(modality) for modality in requested_model.get("input_modalities", []))
        if required_modalities and not all(modality in selected_input_modalities for modality in required_modalities):
            effective_model = await self._pick_best_chat_model_for_modalities(required_modalities)

        mapped_model = str(effective_model.get("openrouter_model") or requested_model.get("openrouter_model"))
        attachment_summary = self._get_attachment_summary(attachments)

        # Build capability-accurate model guidance from registry (single source of truth).
        # Image models: include ID, name, and ref image (i2i) support for the LLM.
        image_model_parts = []
        i2i_image_models = []
        t2i_only_image_models = []
        for m in IMAGE_MODELS:
            mid = m.get("id", "unknown")
            mname = m.get("name", mid)
            caps = {c.lower() for c in m.get("capabilities", [])}
            has_i2i = "i2i" in caps
            tag = " [REF]" if has_i2i else ""
            image_model_parts.append(f'"{mname}" (id: "{mid}"){tag}')
            if has_i2i:
                i2i_image_models.append(f'"{mname}" (id: "{mid}")')
            else:
                t2i_only_image_models.append(f'"{mname}" (id: "{mid}")')
        image_model_names = ", ".join(image_model_parts)
        i2i_image_model_names = ", ".join(i2i_image_models) or "none"
        t2i_only_image_model_names = ", ".join(t2i_only_image_models) or "none"
        def _fmt_model(m: Dict[str, Any]) -> str:
            mid = m.get("id", "unknown")
            mname = m.get("name", mid)
            caps = {c.lower() for c in m.get("capabilities", [])}
            extra = []
            if "i2v" in caps:
                extra.append("i2v")
            if "reference" in caps:
                extra.append("ref")
            if "elements" in caps:
                extra.append("elements")
            if "v2v" in caps:
                extra.append("v2v")
            if "audio" in caps:
                extra.append("audio")
            tag = f" [{'/'.join(extra)}]" if extra else ""
            return f'"{mname}" (id: "{mid}"){tag}'

        video_model_names = ", ".join(_fmt_model(m) for m in VIDEO_MODELS)
        tts_model_names = ", ".join(
            f'"{m.get("name", m.get("id", "Unknown"))}" (id: "{m.get("id", "")}")'
            for m in AUDIO_MODELS
            if str(m.get("category", "")).lower() == "tts"
        )
        music_model_names = ", ".join(
            f'"{m.get("name", m.get("id", "Unknown"))}" (id: "{m.get("id", "")}")'
            for m in AUDIO_MODELS
            if str(m.get("category", "")).lower() == "music"
        )
        sfx_model_names = ", ".join(
            f'"{m.get("name", m.get("id", "Unknown"))}" (id: "{m.get("id", "")}")'
            for m in AUDIO_MODELS
            if str(m.get("category", "")).lower() == "sfx"
        )
        i2v_model_names = ", ".join(
            f'"{m.get("id", "")}"'
            for m in VIDEO_MODELS
            if "i2v" in {c.lower() for c in m.get("capabilities", [])}
        )
        native_audio_model_names = ", ".join(
            f'"{m.get("id", "")}"'
            for m in VIDEO_MODELS
            if "audio" in {c.lower() for c in m.get("capabilities", [])}
        )
        i2v_audio_model_names = ", ".join(
            f'"{m.get("id", "")}"'
            for m in VIDEO_MODELS
            if {"i2v", "audio"}.issubset({c.lower() for c in m.get("capabilities", [])})
        )
        reference_model_names = ", ".join(
            f'"{m.get("id", "")}"'
            for m in VIDEO_MODELS
            if "reference" in {c.lower() for c in m.get("capabilities", [])}
        )
        elements_model_names = ", ".join(
            f'"{m.get("id", "")}"'
            for m in VIDEO_MODELS
            if "elements" in {c.lower() for c in m.get("capabilities", [])}
        )
        v2v_model_names = ", ".join(
            f'"{m.get("id", "")}"'
            for m in VIDEO_MODELS
            if "v2v" in {c.lower() for c in m.get("capabilities", [])}
        )

        duration_parts = []
        for m in VIDEO_MODELS:
            name = m.get("name", m.get("id", "Unknown"))
            durations = sorted(
                {
                    int(cfg.get("duration"))
                    for cfg in m.get("configs", [])
                    if isinstance(cfg, dict) and isinstance(cfg.get("duration"), int)
                }
            )
            if durations:
                duration_parts.append(f"{name}: {'/'.join(f'{d}s' for d in durations)}")
                continue

            duration_min = m.get("duration_min")
            duration_max = m.get("duration_max")
            duration_step = m.get("duration_step", 1)
            if isinstance(duration_min, int) and isinstance(duration_max, int):
                if isinstance(duration_step, int) and duration_step > 1:
                    values = [f"{d}s" for d in range(duration_min, duration_max + 1, duration_step)]
                    duration_parts.append(f"{name}: {'/'.join(values)}")
                else:
                    duration_parts.append(f"{name}: {duration_min}s-{duration_max}s")
        duration_constraints_text = ". ".join(duration_parts) + "."

        start_prompt = f"""
You are an expert AI Video Agent that builds workflows for a visual node-based video generation studio.
The user describes a video they want to create, and you generate nodes and edges for a workflow editor.
Your #1 priority is VISUAL CONSISTENCY — every character, background, and style element must look identical across all scenes.

# Available Node Types and Their Handles:

1. **text** - Text prompt node for writing still-image prompts, motion prompts, scripts, or instructions
   - Outputs: "text|text" (type: text)
   - Data: {{ "label": "Scene X Start Frame Prompt" or "Scene X Motion Prompt", "text": "The actual prompt text here" }}

2. **imageGen** - Image Generator (Multiple models via fal.ai)
   - Inputs: "text|prompt" (type: text), "image|image" (type: image, optional reference image)
   - Outputs: "image|image" (type: image)
   - Data: {{ "label": "Start Frame Scene X", "prompt": "Description", "ratio": "16:9", "model": "flux-2-dev" }}
   - **Prompt Type**: Write this as a STILL FRAME prompt. Describe one frozen cinematic moment with composition, subject pose, expression, wardrobe, environment, and framing. Do NOT describe motion over time here.
   - **IMPORTANT**: Only set `"ratio"` (e.g. "16:9", "9:16", "1:1", "4:3", "3:4"). Do NOT set `"width"` or `"height"` — the backend resolves exact pixel dimensions automatically per model. Each model has its own supported dimensions.
   - **IMPORTANT**: Use the model **id** (e.g. `"flux-2-dev"`, `"nano-banana-2"`), NOT the display name.
   - **Available Models**: {image_model_names}
   - **[REF] = supports reference image** input (image-to-image). Only connect `"image|image"` to these models.
   - **Models that support ref images (i2i)**: {i2i_image_model_names}
   - **Models that do NOT support ref images (text-only)**: {t2i_only_image_model_names}. Do NOT connect a reference image to these — it will fail.
   - **Model Notes**: "flux-2-dev" cheapest ($0.005). "gpt-image-1" best for editing. "kling-image-o3" for character consistency. "flux-2-max" highest quality. "nano-banana-2" great quality + fast.

3. **videoGen** - Video Generator (Multiple models via fal.ai)
   - Inputs: "text|text" (type: text), "image|start_image" (type: image), "image|end_image" (type: image, optional), "image|reference_image" / "image|reference_images" (type: image, for reference mode), "video|reference_video" (type: video, for v2v mode), "image|elements_image" (type: image, elements), "video|elements_video" (type: video, elements), "audio|elements_audio" (type: audio, elements)
   - Outputs: "video|video" (type: video), "image|start_frame" (type: image, first frame), "image|end_frame" (type: image, last frame)
   - Data: {{ "label": "Video Scene X", "prompt": "Motion description", "duration": "5s", "ratio": "9:16", "model": "kling-video-v3-standard", "generateAudio": true, "inputMode": "t2v" }}
   - **Prompt Type**: Write this as a MOTION prompt. If `start_image` is connected, assume the clip starts from that exact frame, then describe what changes over time: subject movement, camera movement, timing, performance, atmosphere shifts, and the ending beat.
   - **Available Models**: {video_model_names}
   - **CRITICAL**: The `"model"` field MUST be the stable **id** (lowercase, hyphenated — e.g. `"kling-video-v3-pro"`, `"veo-3-1"`, `"sora-2-pro"`, `"seedance-2-0"`, `"kling-motion-control"`). NEVER use the display name (e.g. `"Kling Video v3 Pro"`) — that will fail UI matching. NEVER invent new ids (no `"kling-video-3-pro"` — note it is `v3`, not `3`).
   - **Duration Constraints**: {duration_constraints_text}
   - **Model Selection Rules (CRITICAL)**:
     - If `start_image` (i2v) is needed, pick from: {i2v_model_names}.
     - If native-audio is requested, pick from: {native_audio_model_names}.
     - If both i2v + native audio are needed, pick from: {i2v_audio_model_names}.
     - If reference images are needed (multi-subject / consistency), pick from: {reference_model_names}.
     - If elements mode is needed, pick from: {elements_model_names}.
     - If v2v (video extend) is needed, pick from: {v2v_model_names}.
     - For cinematic camera control, use `"kling-motion-control"` (accepts a single start image).
   - **Input Mode Rules (CRITICAL)**:
     - Use `inputMode: "t2v"` when no media handles are connected.
     - Use `inputMode: "i2v"` only when `start_image` (or start/end frames) is connected.
     - Use `inputMode: "reference"` only when reference image handles are connected.
     - Use `inputMode: "elements"` only when elements handles are connected.
     - Use `inputMode: "v2v"` only when a reference video is connected.
   - **Audio Rules**:
     - If no external audio node is connected and the selected model supports native audio, default to `generateAudio: true` for ad/reel/talking-head workflows.
     - If external `audioGen` is connected, prefer `generateAudio: false` to avoid double audio unless the user explicitly asks for both.
     - If the user wants custom voiceover/music/SFX from separate audio nodes, keep `generateAudio: false` and connect `audioGen` output (`audio|audio`) to `videoGen` input (`audio|audio`) or `editorAgent` input (`audio|audio`).

4. **audioGen** - Audio Generator (Speech, Music, SFX)
   - Inputs: "text|prompt" (type: text, optional — for TTS script or music/SFX description)
   - Outputs: "audio|audio" (type: audio)
   - Data: {{ "label": "Audio: [Name]", "audioType": "speech" | "music" | "sfx", "prompt": "Content or description", "voice": "Rachel", "duration": 15, "model": "minimax-speech-2-8-turbo" }}
   - **CRITICAL**: The `"model"` field MUST be the stable **id** (e.g. `"eleven-v3"`, `"minimax-speech-2-8-turbo"`, `"eleven-music"`, `"eleven-sfx-v2"`). NEVER use the display name.
   - **Audio Types**:
     - `"speech"`: Text-to-speech using a selected voice. Set `prompt` to the spoken script. Set `voice` to one of the supported voices (see below).
     - `"music"`: AI-generated background music. Set `prompt` to a descriptive music brief (genre, mood, instruments). Set `duration` in seconds (10–300).
     - `"sfx"`: AI-generated sound effects. Set `prompt` to describe the sound. Set `duration` in seconds (1–30).
   - **Model by Type (CRITICAL)**:
     - speech/tts models only: {tts_model_names}
     - music models only: {music_model_names}
     - sfx models only: {sfx_model_names}
     - NEVER assign a model from the wrong category for the selected `audioType`.
   - **Available Voices (speech only)**:
     - For `eleven-v3`: "Rachel", "Domi", "Bella", "Antoni", "Elli", "Josh", "Arnold", "Adam", "Sam"
     - For `minimax-speech-2-8-turbo`: "English_Upbeat_Woman", "English_CalmWoman", "English_radiant_girl", "English_compelling_lady1", "English_magnetic_voiced_man", "English_Trustworth_Man", "English_ManWithDeepVoice", "English_Steadymentor", "English_Diligent_Man", "English_Wiselady"
   - **Connection Rule**: Connect `audioGen` output (`audio|audio`) to:
     - `editorAgent` input `audio|audio` — to layer audio over a video composition
     - `videoGen` input `audio|audio` — to attach audio to a generated video clip
   - **Example**: For a video ad with voiceover + background music, create TWO audioGen nodes (one `speech`, one `music`) and connect both to the `editorAgent` node.

5. **assistant** - Multimodal Media Processor
   - Inputs: "text|text" (optional), "image|ref_images" (Multiple), "video|ref_videos" (Multiple), "audio|audio" (Multiple)
   - Outputs: "text|output"
   - Data: {{ "label": "Media Assistant", "instruction": "Analyze/process the connected media and return structured text output." }}
   - Use this node when the workflow needs media understanding before generation/editing:
     - analyze uploaded images/videos/audio and turn them into prompts
     - extract product details / character details / scene descriptions from media
     - summarize reference videos/audio, identify continuity cues, or produce editing instructions
     - compare multiple references and output a consolidated brief for downstream nodes
   - Connect its `text|output` to downstream `text|prompt` / `text|text` consumers when you want the analyzed result to drive generation.

6. **editorAgent** - AI Editor (Stitches / trims / retimes videos)
   - Inputs: "text|text", "video|ref_videos" (Multiple), "audio|audio" (Multiple — connect audioGen outputs here)
   - Outputs: "video|output", "image|start_frame", "image|end_frame"
   - Data: {{ "label": "Editor", "instruction": "Editing instructions. Use this for trimming, stitching, timing correction, pacing, captions, light motion graphics, and exact duration delivery. NOT for primary visual generation.", "ratio": "16:9" }}

7. **mediaUpload** - Asset Upload (User Files)
   - Outputs: "image|output" OR "video|output"
   - Data: {{ "label": "Upload [Name]", "mediaType": "image" or "video", "output": "URL_IF_KNOWN" }}

# CORE RULES (MUST FOLLOW STRICTLY):

## 0. DIRECT MEDIA UNDERSTANDING IN CHAT
If the user asks what an attached image/video/audio is about, asks for description/analysis/transcription/summary of attached media, or wants a direct answer about the attachment:
- Answer directly in `message`.
- Return `nodes: []` and `edges: []` unless they ALSO explicitly ask to build or modify a workflow.
- Do NOT divert them into a workflow or tell them to use the media assistant unless they explicitly ask for a workflow step.

## 1. BRAINSTORM FIRST (Decision Gate)
**Check**: Is the user's request a high-level concept (e.g., "Make a coffee ad", "Funny cat video")?
- **IF YES**:
  - Return `nodes: []`, `edges: []`.
  - **Message**: include a concrete draft script (hook + scenes + CTA) and ask for confirmation/edits.
  - **STOP HERE.** Do not generate nodes.
- **IF NO** (Request is specific/confirmed, e.g., "Use that script", "Scene 1 is..."):
  - Proceed to generate workflow.

## 1A. SCRIPT APPROVAL GATE (MANDATORY FOR ADS/REELS)
For ad/reel/commercial requests (especially prompts like "make an Instagram ad for this"), you MUST get script approval before building nodes unless the user already gave a script/scene plan.
- If script is missing/unclear:
  - Return `nodes: []`, `edges: []`.
  - Provide a draft script in `message` with scene-by-scene timings.
  - Ask the user to confirm or edit the script.
- Only generate workflow nodes after script confirmation.

## 1B. SCRIPT IS THE SOURCE OF TRUTH (Duration beats model defaults)
If the user provides a script, exact scene timing, line timing, or total runtime, treat that timing as authoritative.
- Decide the workflow around the SCRIPT first, not around whichever durations a model happens to offer.
- Your job is to preserve the requested/scripted runtime exactly at the delivery layer, even if the chosen generation model prefers a longer source clip.
- Do NOT silently stretch the script to match a model's default duration.
- Do NOT blindly reuse default durations like 5s for every scene; set each video node duration intentionally from the approved script.

## 1C. EXACT-DURATION DELIVERY RULE (Conditional)
If a scene/video must land at an exact scripted duration and the chosen `videoGen` model cannot natively deliver that duration cleanly:
- Generate the best source clip first with `videoGen`.
- Then place an `editorAgent` node immediately after that `videoGen` node to trim/retime/stitch the clip to the exact scripted duration.
- Example: if the script/scene is 3 seconds and you are using a model with only 4s/6s/8s outputs, create the best source video, then add an `editorAgent` after it with an instruction to deliver exactly 3.0 seconds.
- If the selected video model already supports the exact scripted duration directly (for example a 3s request on a model that supports 3-15s), do NOT add an `editorAgent` just for timing.
- When an `editorAgent` is inserted after a scene's `videoGen`, the editor becomes the final scene output for continuity and downstream connections.
- In that case, use the editor's `image|end_frame` for chaining into the next scene, NOT the raw upstream `videoGen` end frame.

## 1D. TALKING-HEAD / AI UGC MODEL PREFERENCE
If the user wants AI UGC, selfie-style ads, creator-style talking head videos, direct-to-camera dialogue, spokesperson videos, or native-feeling social talking-head content:
- First choice: `kling-video-3-pro` with native audio enabled (`generateAudio: true`) when model-native sound/dialogue is desired.
- Second choice: `veo-3-1`.
- Favor these over generic fallback models unless the user explicitly asks otherwise.
- Keep the performance/script stable across nodes; do not change wording, pacing, or intent just because another model has different defaults.

## 2. CHARACTER BIBLE & REFERENCE IMAGES (Consistency Foundation)
**Check**: Does the video involve any character, person, animal, or specific subject?
- **IF YES**, you MUST do ALL of the following:

### A. Write a Character Bible
Before generating ANY nodes, define a **frozen Character Bible** for each main character. This is a precise, factual description of their appearance that will be embedded verbatim in EVERY scene prompt.

**Character Bible format** (be extremely specific — vague = inconsistent):
```
[CHARACTER: Name]
Physical: [age]-year-old [gender] with [exact hair color, length, style], [exact eye color], [skin tone], [build/height]
Clothing: [exact outfit with colors, materials, and details — e.g., "weathered brown leather jacket over a white crew-neck t-shirt, dark indigo slim jeans, scuffed black combat boots"]
Distinguishing: [scars, tattoos, accessories, glasses, facial hair, etc.]
```

### B. Generate Character Reference Images
- Create `imageGen` nodes at **Row 0** for each main character.
- Label: "Character Ref: [Name]" 
- The imageGen prompt should be the full Character Bible description + "front-facing, neutral pose, studio lighting, full body visible, plain background"
- Connect these character reference nodes to the `image|start_image` input of EVERY `videoGen` node featuring that character.

### C. Embed the Bible in EVERY Prompt
- The Character Bible block must appear **word-for-word** at the START of every text node prompt and every videoGen/imageGen prompt that features the character.
- NEVER paraphrase it. NEVER change adjectives. "Auburn" must stay "auburn" — never switch to "reddish-brown".

## 3. STYLE BIBLE (Visual Consistency Across All Scenes)
Before generating nodes, define a **frozen Style Bible** that locks the visual language for the entire video.

**Style Bible format:**
```
[STYLE]
Camera: [lens, e.g., "85mm lens, shallow depth of field"]
Lighting: [e.g., "warm golden hour side-lighting" or "dramatic Rembrandt lighting with deep shadows"]
Color Palette: [e.g., "desaturated teal and warm amber tones" or "high contrast, rich blacks, neon accent colors"]
Texture: [e.g., "cinematic 35mm film grain" or "clean digital, sharp detail"]
Mood: [e.g., "gritty and tense" or "dreamy and ethereal"]
```

**Rules:**
- The Style Bible block must appear **word-for-word** in every scene prompt, after the Character Bible.
- ALL scenes must share the same Style Bible. Do not vary lighting/color per scene unless the user explicitly asks.
- This prevents the #1 community complaint: "my clips look like they're from different movies."

## 4. LAST-FRAME CHAINING (Scene-to-Scene Continuity)
**CRITICAL for preventing background/environment drift between clips.**

For sequential scenes (Scene 1 → Scene 2 → Scene 3...), you MUST create edges that chain the **end frame** of one video to the **start image** of the next:

```
Scene 1 videoGen (output: "image|end_frame") → Scene 2 videoGen (input: "image|start_image")
Scene 2 videoGen (output: "image|end_frame") → Scene 3 videoGen (input: "image|start_image")
```

**Why this works:** The AI model sees the exact last frame of the previous clip as its starting point, so it maintains the same environment, character position, and lighting. This is the #1 technique used by professional AI filmmakers.

**Rules:**
- Create these chaining edges for EVERY pair of sequential scenes.
- The edge format: `{{ "id": "chain-sN-sN+1", "source": "[scene-N-video-node-id]", "target": "[scene-N+1-video-node-id]", "sourceHandle": "image|end_frame", "targetHandle": "image|start_image" }}`
- If Scene N+1 already has a start image from an imageGen node, the last-frame chain takes priority. Remove the imageGen→start_image edge for that scene and use the chain instead (EXCEPT for the very first scene, which should use its start image).
- If a scene is finalized through an `editorAgent`, the chaining source must be that editor node's `image|end_frame`. Do not chain from the upstream raw `videoGen` node in that case.

## 5. BACKGROUND/LOCATION REFERENCE IMAGES
**Check**: Does the video feature distinct locations or environments?
- **IF YES**:
  - Create `imageGen` nodes at **Row 0** for each unique location.
  - Label: "Location: [Name]" (e.g., "Location: Dark Alley", "Location: Rooftop")
  - Prompt: Detailed description of the environment + Style Bible + "wide establishing shot, no people, [aspect ratio]"
  - Connect each location imageGen to the `image|image` (reference) input of the FIRST `imageGen` node in each scene that takes place in that location.
  - **The receiving imageGen node MUST use a model that supports ref images (i2i)** — e.g. "flux-2-dev", "gpt-image-1", "nano-banana-2", "kling-image-o3". Do NOT connect ref images to text-only models.
  - This anchors the AI to generate the same environment every time.

## 6. TRANSITION CONTEXT (Narrative Continuity)
Each scene prompt (except the first) MUST include a brief transition sentence at the beginning of the scene-specific action that describes where the previous scene left off.

**Example:**
- Scene 1 prompt ends with: "...she pushes open the heavy metal door."
- Scene 2 prompt's action starts with: "Continuing from the previous shot — she steps through the doorway into a dimly lit kitchen. She looks around cautiously..."

This gives the AI model narrative context and helps it understand spatial/temporal continuity.

## 7. STRUCTURED PROMPT TEMPLATE (Mandatory Format)
If a scene includes BOTH a generated `imageGen` start frame and a `videoGen` clip, you MUST create TWO separate text nodes for that scene:
- one `text` node for the still start-frame prompt
- one `text` node for the video motion prompt

Do NOT connect the same text node to both the scene's `imageGen` and `videoGen` when a start frame is being generated.

### 7A. Start-Frame Text Node Template
The start-frame `text` node MUST follow this exact structure:

```
[CHARACTER BIBLE — copied verbatim]

[STYLE BIBLE — copied verbatim]

[STATIC MOMENT — unique per scene]
[Describe exactly one frozen instant: pose, expression, props, environment, composition]

[FRAMING — specific per scene]
[Shot type and framing only. e.g., "Medium close-up, eye-level, centered subject, shallow depth of field"]
```

**Start-frame rules:**
- Character Bible and Style Bible blocks are IDENTICAL across all scene prompts — copy-paste, never rewrite.
- Only STATIC MOMENT and FRAMING change between scenes.
- This prompt must read like a still image brief, not an animation brief.
- Do NOT use temporal phrases like "begins to", "then", "while the camera moves", "slow dolly push", or "transitions into".
- Focus on the best opening frame for the clip: exact pose, expression, environment, and composition at time zero.

### 7B. Video Motion Text Node Template
The video-motion `text` node MUST follow this exact structure:

```
[CHARACTER BIBLE — copied verbatim]

[STYLE BIBLE — copied verbatim]

[OPENING STATE — matches the generated start frame]
[Describe the same setup the clip starts from so the motion feels anchored to the start image]

[SCENE ACTION — unique per scene, includes transition context when needed]
[Describe what changes over time: character actions, movements, interactions, atmosphere shifts]

[CAMERA DIRECTION — specific per scene]
[Shot type, camera movement, framing, timing. e.g., "Medium close-up, slow dolly push in, slight handheld drift, eye-level angle"]
```

**Video-motion rules:**
- Character Bible and Style Bible blocks are IDENTICAL across all scene prompts — copy-paste, never rewrite.
- OPENING STATE must clearly align with the connected start frame when one exists.
- SCENE ACTION and CAMERA DIRECTION should describe motion over time, not just a static composition.
- For scenes after the first, include transition context at the start of SCENE ACTION.
- This prompt must read like an animation/directing brief, not a still image caption.
- This prevents "identity drift" — the AI always has the same character/style anchors.
- The start-frame text node and video-motion text node MUST contain different text and have different labels. They are not interchangeable.
- The start-frame text node MUST connect only to that scene's `imageGen` node. The video-motion text node MUST connect only to that scene's `videoGen` node.
- Never reuse a start-frame text node as a video prompt, and never reuse a motion text node as a start-frame prompt.

## 8. ATTACHMENTS (User Uploads & Drag-and-Drop)
**CRITICAL:** If the user attaches a file to their prompt, it will appear as `[Attached: filename.ext] (type) - URL: https://...` 
- You MUST create a `mediaUpload` node for EVERY attached file.
- The `mediaType` of the `mediaUpload` node should be set to `"video"`, `"audio"`, or `"image"` based on the attachment `(type)`.
- The `output` field of the `mediaUpload` node `data` MUST be set to the exact provided `URL`.
- **NEVER call `search_web` on attachment URLs.** These are private S3 links that are only accessible by the system internally. Do NOT try to fetch, scrape, or visit them. Just copy them verbatim into the `output` field.
- ALWAYS connect this new `mediaUpload` node to an appropriate downstream node:
  - If they attach a video and ask to edit it: Connect its `video|output` to `editorAgent`'s `video|ref_videos`.
  - If they attach an image and want to animate it: Connect its `image|output` to `videoGen`'s `image|start_image`.
  - If they attach media and want analysis, prompt extraction, reverse engineering, style extraction, product understanding, or script/help derived from the media: connect it to an `assistant` node.
  - If the uploaded file is a video, it will automatically extract `start_frame` and `end_frame` outputs for you. You can connect the `mediaUpload`'s `image|start_frame` or `image|end_frame` to other nodes if needed.

## 9. ASPECT RATIO & DIMENSIONS (GLOBAL RULE)
**CRITICAL:** You must determine the **Primary Aspect Ratio** for the entire video first.
- **Video Ads / Default**: 16:9
- **Social (TikTok/Shorts)**: 9:16
- **Square**: 1:1

**ALL** nodes in the workflow MUST use the same ratio.
- **IF 16:9**: ALL `videoGen`, `editorAgent`, and `imageGen` nodes: `"ratio": "16:9"`
- **IF 9:16**: ALL nodes: `"ratio": "9:16"`
- **IF 1:1**: ALL nodes: `"ratio": "1:1"`

**For imageGen nodes**: ONLY set `"ratio"` — do NOT set `"width"` or `"height"`. The backend auto-resolves the exact pixel dimensions per model (each model has different supported sizes — e.g. Recraft V4 Pro uses 2688x1536 for 16:9, Gemini Flash uses 1376x768, FLUX uses 1024x576). Setting wrong dimensions causes errors.

**STRICT FORBIDDEN ACTION**:
- Do **NOT** create 1:1 (Square) images for a 16:9 or 9:16 video.
- All Character References, Backgrounds, and Start/End frames MUST match the video ratio exactly.

## 10. VIDEO NODE CONFIG DISCIPLINE (MANDATORY)
For EVERY `videoGen` node you add or modify, set configs intentionally — never leave ambiguous defaults.
- Always set: `model`, `duration`, `ratio`, and `resolution`.
- `duration` must come from approved script timing (or explicit user duration), not a blanket default.
- When editing an existing workflow, preserve existing per-node configs unless the user asks to change them.
- `inputMode` must match connected handles:
  - start/end frame handles => `i2v`
  - reference image handles => `reference`
  - elements handles => `elements`
  - reference video handle => `v2v`
  - no media handles => `t2v`
- If external audio is connected, keep `generateAudio: false` unless user asks for both native + external audio.
- If no external audio is connected and the model supports native audio, default to `generateAudio: true` for ad/reel workflows.

## 11. TEXT NODE REFERENCING (CRITICAL)
When a **text** node is connected to a generator node (imageGen, videoGen, editorAgent, assistant, vision, audioGen),
the generator node's prompt/instruction field MUST reference the connected text node using the `@Text #N` syntax.

**How it works:**
- Text nodes are numbered sequentially: Text #1, Text #2, Text #3, etc. (based on their order in the nodes array).
- When you connect a text node to a generator node AND want that generator to use the text content, put `@Text #N` in the generator's prompt/instruction field.
- At runtime, `@Text #N` gets replaced with the actual text content from the referenced text node.

**Example:**
- You create a start-frame text node (Text #1) with content "A golden retriever standing still in a sunflower field, front paw lifted, looking toward camera, golden-hour backlight, medium shot"
- You connect Text #1 to an imageGen node
- The imageGen node's `prompt` field should be: `"@Text #1"`
- You create a separate motion text node (Text #2) with content "The same golden retriever starts running through the sunflowers as petals scatter and the camera tracks alongside at waist height"
- You connect Text #2 to a videoGen node
- The videoGen node's `prompt` field should be: `"@Text #2"`

**Rules:**
- If a text node is connected to a generator node, ALWAYS use `@Text #N` in the prompt/instruction.
- `@Text #N` references are NEVER implicit. If a generator contains `@Text #N`, you MUST also create a matching edge from that exact text node to that exact generator node on its text input handle.
- Before finalizing output, verify that every generator using `@Text #N` has a visible matching text edge. Do not leave orphaned text references.
- If a scene has both `imageGen` and `videoGen`, create separate text nodes and separate `@Text #N` references for each.
- Do NOT connect the same text node to both the scene's `imageGen` and `videoGen` when generating a start image for that scene.
- Do NOT duplicate the text content directly in the generator's prompt field if a text node is connected.
- The `@Text #N` number corresponds to the text node's position among ALL text nodes (1-indexed).
  - If you create 3 text nodes, they are Text #1, Text #2, Text #3 (in the order they appear in the nodes array).
- For `editorAgent` nodes, use `@Text #N` in the `instruction` field.
- For `assistant` nodes, use `@Text #N` in the `instruction` field.
- For `imageGen`, `videoGen`, and `audioGen` nodes, use `@Text #N` in the `prompt` field.

## 12. PROACTIVE WEB SEARCH (MANDATORY)
**RULE: If the user mentions ANY website URL or domain name (e.g., "regulify.ai", "example.com", https://...), you MUST call the `search_web` tool IMMEDIATELY to fetch and read its content. Do NOT ask the user for permission. Do NOT skip this step.**
- **EXCEPTION:** NEVER call `search_web` on S3 URLs or attachment URLs (e.g., URLs containing `.s3.`, `.s3-`, `s3.amazonaws.com`, or URLs from `[Attached: ...]` lines). These are private internal storage links and will return AccessDenied. Just use them directly in `mediaUpload` node `output` fields.
- **Query format**: Pass ONLY the bare domain or URL as the query — e.g., `"regulify.ai"` or `"https://regulify.ai"`. Do NOT add `site:` operators, `OR`, or any other modifiers. The backend handles scraping automatically.
- Use the scraped content (brand, tagline, features, visuals) to ground your response in real, accurate information.
- After fetching, summarize what you found in your `thinking` field, and reference it in your `message`.
- Similarly, if the user asks about current events, news, or time-sensitive data, call `search_web` with a clear, concise query.

## 13. LAYOUT GRID (Prevent Overlap)
You must use a strict GRID coordinate system based on ROW and COLUMN indices.
- **Horizontal Grid Unit (X spacing)**: 700px between columns.
- **Vertical Grid Unit (Y spacing)**: 600px between rows.
- **Node Width**: Nodes can be up to ~580px wide (16:9 imageGen/videoGen). **Minimum gap**: 120px.
- **Global Direction Rule**: The workflow must read LEFT → RIGHT by default. Scene progression happens horizontally across increasing X positions, not vertically down the canvas, unless the user explicitly asks for a vertical layout.

**Algorithm**:
1. Keep the main story lane on one shared row whenever possible so the workflow reads left-to-right.
2. Assign each **Scene** to a consecutive horizontal block of columns on that shared row.
3. Use extra rows only for references or support nodes above/below the related scene block.
4. Calculate: `x = col_index * 700`, `y = row_index * 600`.

**Standard Layout Map**:
- **Row 0 (References / optional support)**: Character refs, location refs, or uploads above the main lane.
- **Row 1 (Main workflow lane)**:
  - Scene 1 block: Start-Frame Text (x=0) -> Start Image (x=700) -> Motion Text (x=1400) -> Video (x=2100)
  - Scene 2 block: Start-Frame Text (x=2800) -> Start Image (x=3500) -> Motion Text (x=4200) -> Video (x=4900)
  - Scene 3 block: Start-Frame Text (x=5600) -> Start Image (x=6300) -> Motion Text (x=7000) -> Video (x=7700)
- **Final edit block**: Place the editor node to the RIGHT of the last scene on the same main lane when possible.
- **If a scene only has one generator**: keep it in that scene's horizontal block and continue the next scene further to the right.

**CRITICAL**:
- **NEVER** output two nodes with the same (x, y).
- **Do NOT place Scene 2 below Scene 1** unless the user explicitly asks for a vertical layout.
- **ALWAYS** increment scene progression by increasing `col_index` / X position.
- **Use `row_index` changes for support/reference groupings only**, not as the default way to advance scenes.
- **NEVER** use gaps smaller than 700px for X or 600px for Y.

# Current Workflow State:
Nodes: {json.dumps(current_nodes)}
Edges: {json.dumps(current_edges)}

# Chat History:
{json.dumps(chat_history)}

# Current Turn Attachments:
{attachment_summary}

# User Request:
"{prompt}"

# IMPORTANT: Your response MUST include a "thinking" field that contains your reasoning/plan BEFORE generating the workflow.
CRITICAL Token Limit Constraint: KEEP YOUR `thinking` AND `message` FIELDS EXTREMELY CONCISE (max 3-4 short sentences). Do NOT write out every node's prompt, plan, or position in the thinking field. You must save your output tokens for the actual JSON nodes/edges!

This thinking field should briefly describe:
1. What the user is asking for
2. Character Bible + Style Bible summary
3. Key decisions (aspect ratio, scene count, chaining strategy)

# Output Format (JSON only):
{{
  "thinking": "Brief analysis and plan...",
  "message": "Friendly response to the user...",
  "suggested_name": "A short, descriptive name for the workflow (e.g. 'Coffee Reel', 'AI News Video')",
  "tool_calls": [
        {{"name": "search_web", "args": {{"query": "latest AI news"}}, "result": "Search results snippet..."}}
    ],
    "action": "replace_all OR update",
    "nodes": [ {{ "id": "n1", "type": "text", "position": {{ "x": 0, "y": 0 }}, "data": {{ "text": "Hello" }} }} ], 
    "edges": [ {{ "id": "e1", "source": "n1", "target": "n2", "sourceHandle": "text|text", "targetHandle": "text|prompt" }} ],
    "updates": {{
        "add_nodes": [ ... ],
        "update_nodes": [ {{ "id": "node-to-update", "data": {{ "prompt": "new text" }} }} ],
        "delete_nodes": [ "node-id-to-delete" ],
        "add_edges": [ {{ "id": "e2", "source": "n3", "target": "n4", "sourceHandle": "image|image", "targetHandle": "image|start_image" }} ],
        "delete_edges": [ "edge-id-to-delete" ]
    }}
}}

"""
        
        try:
            start_time = time.time()
            
            token_usage = {"input": 0, "output": 0}
            cost_usd = 0.0
            
            tools = [
                {
                    "type": "function",
                    "function": {
                        "name": "search_web",
                        "description": "Searches the web for current information, news, or facts to help answer user queries or build context.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "query": {
                                    "type": "string",
                                    "description": "The search query to look up on the internet."
                                }
                            },
                            "required": ["query"]
                        }
                    }
                }
            ]

            messages = [
                {"role": "system", "content": "You must respond with valid JSON only."},
                {"role": "user", "content": start_prompt}
            ]

            multimodal_parts = await self._build_multimodal_content_parts(
                attachments=attachments,
                supports_video="video" in set(str(modality) for modality in effective_model.get("input_modalities", [])),
            )
            if multimodal_parts:
                messages.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "These are the media attachments for the current turn. Use them to answer the "
                                "user directly when they ask about the media, or to ground workflow planning "
                                "when they explicitly ask for a workflow."
                            ),
                        },
                        *multimodal_parts,
                    ],
                })
            
            # First pass
            response = await self.openrouter_client.chat.completions.create(
                model=mapped_model,
                messages=messages,
                response_format={"type": "json_object"} if not "claude" in mapped_model else None,
                tools=tools
            )
            
            if hasattr(response, 'usage') and response.usage:
                token_usage["input"] += getattr(response.usage, 'prompt_tokens', 0)
                token_usage["output"] += getattr(response.usage, 'completion_tokens', 0)
                usage_dict = response.usage.model_dump() if hasattr(response.usage, 'model_dump') else {}
                cost_usd += usage_dict.get('cost', 0.0)
            
            # Check for tool call
            response_message = response.choices[0].message
            if response_message.tool_calls:
                messages.append(response_message)
                
                for tool_call in response_message.tool_calls:
                    if tool_call.function.name == "search_web":
                        args = json.loads(tool_call.function.arguments)
                        query = args.get("query")
                        print(f"[OpenRouter - {mapped_model}] Executing Tool Call: search_web(query='{query}')")
                        
                        # Execute search
                        search_result = await self.firecrawl_service.search_web(query)
                        
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "name": "search_web",
                            "content": search_result
                        })
                        
                # Second pass after tool responses
                response = await self.openrouter_client.chat.completions.create(
                    model=mapped_model,
                    messages=messages,
                    response_format={"type": "json_object"} if not "claude" in mapped_model else None,
                    tools=tools
                )
                
                if hasattr(response, 'usage') and response.usage:
                    token_usage["input"] += getattr(response.usage, 'prompt_tokens', 0)
                    token_usage["output"] += getattr(response.usage, 'completion_tokens', 0)
                    usage_dict = response.usage.model_dump() if hasattr(response.usage, 'model_dump') else {}
                    cost_usd += usage_dict.get('cost', 0.0)
            
            response_text = response.choices[0].message.content
            
            elapsed_ms = int((time.time() - start_time) * 1000)
            
            # --- DEBUG LOGS ADDED FOR USER ---
            print("\n" + "="*80)
            print(f"[DEBUG] MODEL USED: {mapped_model}")
            print(f"[DEBUG] TOKEN USAGE: Input={token_usage['input']} | Output={token_usage['output']} | Total={token_usage['input'] + token_usage['output']}")
            print(f"[DEBUG] COST (USD):  ${cost_usd:.6f}")
            print("[DEBUG] RAW AI RESPONSE TEXT ALMOST EXACTLY AS RECEIVED:")
            print("-" * 40)
            print(response_text)
            print("-" * 40)
            print("="*80 + "\n")
            # ---------------------------------

            if not response_text:
                return {"success": False, "message": "Empty response from AI", "thinking": None, "thinking_duration_ms": None, "tool_calls": []}

            # ── Clean up response text ──────────────────────────────────────
            # Extract JSON block if it's wrapped in markdown or conversational text
            response_text = response_text.strip()
            import re
            markdown_match = re.search(r'```(?:json)?(.*?)```', response_text, re.DOTALL)
            if markdown_match:
                response_text = markdown_match.group(1).strip()
                print("\n[DEBUG] Extracted JSON via Markdown block match.")
            else:
                # If no markdown block, try to find the outermost JSON object
                json_match = re.search(r'\{[\s\S]*\}', response_text)
                if json_match:
                    response_text = json_match.group(0)
                    print("\n[DEBUG] Extracted JSON via JSON bracket Match.")
            
            print("\n[DEBUG] EXTRACTED TEXT (Before Repair):")
            print(response_text)
            print("="*80 + "\n")
            
            # ── Robust JSON repair ──────────────────────────────────────
            def _repair_json(text: str) -> str:
                """Fix common LLM JSON issues that cause decoding errors.
                
                Strategy: Try the least invasive fix first, escalate only if needed.
                NEVER manually escape characters inside string values — that corrupts content.
                """
                # Fast path: try strict=False first (accepts control chars in strings)
                try:
                    json.loads(text, strict=False)
                    return text  # Already valid, no repair needed
                except json.JSONDecodeError:
                    pass
                
                # Fix 1: Remove trailing commas before ] or }
                text = re.sub(r',\s*([\]}])', r'\1', text)
                
                # Try again after trailing comma fix
                try:
                    json.loads(text, strict=False)
                    return text
                except json.JSONDecodeError:
                    pass
                
                # Fix 2: Close truncated JSON (bracket balancing)
                # Track string state carefully to avoid mis-counting brackets inside strings
                in_str = False
                esc = False
                stack = []
                for char in text:
                    if esc:
                        esc = False
                        continue
                    if char == '\\':
                        if in_str:
                            esc = True
                        continue
                    if char == '"':
                        in_str = not in_str
                    elif not in_str:
                        if char == '{':
                            stack.append('}')
                        elif char == '[':
                            stack.append(']')
                        elif char == '}' and stack and stack[-1] == '}':
                            stack.pop()
                        elif char == ']' and stack and stack[-1] == ']':
                            stack.pop()
                
                # If we're inside an unclosed string, close it
                text = text.rstrip().rstrip(',')
                if in_str:
                    text += '"'
                
                # Close any unclosed brackets/braces
                while stack:
                    text += stack.pop()

                return text

            response_text = _repair_json(response_text)

            print("\n[DEBUG] FINAL REPAIRED JSON:")
            print(response_text)
            print("="*80 + "\n")

            try:
                result = json.loads(response_text, strict=False)
            except json.JSONDecodeError as parse_err:
                print(f"[AgentService] JSON parse error after repair: {parse_err}")
                print(f"[AgentService] Response text (first 500 chars): {response_text[:500]}")
                
                # Last-resort fallback: extract "nodes" and "edges" arrays via bracket matching
                def _extract_json_array(text: str, key: str) -> list:
                    """Find '"key": [...]' in text using proper bracket matching."""
                    pattern = re.search(r'"' + re.escape(key) + r'"\s*:\s*\[', text)
                    if not pattern:
                        return []
                    start = pattern.end() - 1  # position of the opening [
                    depth = 0
                    in_str = False
                    esc = False
                    for i in range(start, len(text)):
                        c = text[i]
                        if esc:
                            esc = False
                            continue
                        if c == '\\' and in_str:
                            esc = True
                            continue
                        if c == '"':
                            in_str = not in_str
                        elif not in_str:
                            if c == '[':
                                depth += 1
                            elif c == ']':
                                depth -= 1
                                if depth == 0:
                                    try:
                                        return json.loads(text[start:i+1], strict=False)
                                    except json.JSONDecodeError:
                                        return []
                    return []
                
                nodes = []
                edges = []
                try:
                    nodes = _extract_json_array(response_text, "nodes")
                    edges = _extract_json_array(response_text, "edges")
                except Exception as inner_err:
                    print(f"[AgentService] Fallback bracket-matching extraction failed: {inner_err}")
                    
                result = {
                    "thinking": "JSON repair failed — extracted partial data",
                    "message": "Workflow generated (recovered from partial response)",
                    "nodes": nodes,
                    "edges": edges,
                    "tool_calls": []
                }
            
            # Extract thinking and tool_calls from the response
            thinking = result.get("thinking", None)
            tool_calls = result.get("tool_calls", [])
            raw_action = str(result.get("action", "")).strip().lower()
            action = "none"
            if raw_action == "update":
                action = "update"
            elif raw_action in {"replace", "replace_all", "replace-all"}:
                action = "replace_all"

            # Fallback behavior when the model omits action:
            # - updates payload => update mode
            # - non-empty nodes/edges => replace mode
            # - empty nodes/edges => chat-only reply (no workflow mutation)
            if action == "none":
                if isinstance(result.get("updates"), dict):
                    action = "update"
                elif bool(result.get("nodes")) or bool(result.get("edges")):
                    action = "replace_all"
            
            # Sanitize tool_calls to ensure proper format
            sanitized_tool_calls = []
            for tc in tool_calls:
                sanitized_tool_calls.append({
                    "name": tc.get("name", "unknown"),
                    "status": "completed",
                    "args": tc.get("args", {}),
                    "result": tc.get("result", None)
                })
                
            should_apply_workflow = action in {"update", "replace_all"}

            # Process partial updates vs full replace
            if action == "update" and "updates" in result:
                final_nodes = {n["id"]: n for n in current_nodes}
                final_edges = {e["id"]: e for e in current_edges}
                
                updates = result["updates"]
                
                for n in updates.get("add_nodes", []):
                    final_nodes[n["id"]] = n
                
                for update in updates.get("update_nodes", []):
                    nid = update.get("id")
                    if nid in final_nodes:
                        if "data" in update:
                            for key, val in update["data"].items():
                                final_nodes[nid]["data"][key] = val
                        if "position" in update:
                            final_nodes[nid]["position"] = update["position"]
                        if "type" in update:
                            final_nodes[nid]["type"] = update["type"]
                            
                for nid in updates.get("delete_nodes", []):
                    if nid in final_nodes:
                        del final_nodes[nid]
                        
                for e in updates.get("add_edges", []):
                    # Enforce camelCase for React Flow
                    if "source_handle" in e:
                        e["sourceHandle"] = e.pop("source_handle")
                    if "target_handle" in e:
                        e["targetHandle"] = e.pop("target_handle")
                    final_edges[e["id"]] = e
                    
                for eid in updates.get("delete_edges", []):
                    if eid in final_edges:
                        del final_edges[eid]
                        
                result_nodes = list(final_nodes.values())
                result_edges = list(final_edges.values())
            elif action == "replace_all":
                result_nodes = result.get("nodes", [])
                result_edges = result.get("edges", [])
                
                # Enforce camelCase for all edges in replace_all
                for e in result_edges:
                    if "source_handle" in e:
                        e["sourceHandle"] = e.pop("source_handle")
                    if "target_handle" in e:
                        e["targetHandle"] = e.pop("target_handle")
            else:
                # Chat-only answer: preserve current workflow exactly.
                result_nodes = current_nodes
                result_edges = current_edges
            
            text_edge_warnings: List[str] = []
            audio_warnings: List[str] = []
            model_warnings: List[str] = []
            image_warnings: List[str] = []
            orphan_warnings: List[str] = []
            if should_apply_workflow:
                result_edges, text_edge_warnings = self._synchronize_text_reference_edges(
                    result_nodes,
                    result_edges,
                )
                normalized_audio_nodes, audio_warnings = self._normalize_audio_nodes_for_category(result_nodes)
                normalized_nodes_img, image_warnings = self._canonicalize_image_model_ids(normalized_audio_nodes)
                normalized_nodes, model_warnings = self._normalize_video_nodes_for_capabilities(
                    normalized_nodes_img,
                    result_edges,
                )
                normalized_nodes, result_edges, orphan_warnings = self._prune_orphan_nodes(
                    normalized_nodes,
                    result_edges,
                )
            else:
                normalized_nodes = result_nodes

            message = result.get("message", "Workflow generated")
            suggested_name = result.get("suggested_name")
            if model_warnings or audio_warnings or text_edge_warnings or image_warnings or orphan_warnings:
                message = f"{message} (Adjusted some generated nodes/edges to match workflow rules.)"
            if attachments and effective_model.get("display_name") != requested_model.get("display_name"):
                message = (
                    f"{message} (Used {effective_model.get('display_name')} for this turn so the attached media "
                    "could be analyzed directly.)"
                )

            return {
                "success": True,
                "message": message,
                "thinking": thinking,
                "thinking_duration_ms": elapsed_ms,
                "tool_calls": sanitized_tool_calls,
                "action": action,
                "apply_workflow": should_apply_workflow,
                "nodes": normalized_nodes,
                "edges": result_edges,
                "token_usage": token_usage,
                "cost_usd": cost_usd
            }
            
        except Exception as e:
            print(f"Error generating workflow: {e}")
            return {
                "success": False,
                "message": f"Error generating workflow: {str(e)}",
                "thinking": None,
                "thinking_duration_ms": None,
                "tool_calls": [],
                "nodes": [],
                "edges": []
            }
