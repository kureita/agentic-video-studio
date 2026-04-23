"""Audio Generator Service — Uses fal.ai for speech, music, sound effects, and lipsync.

All methods auto-dispatch:
  * Inside a workflow task with `FAL_WEBHOOK_PUBLIC_URL` set → submit + return `pending_fal`.
  * Otherwise (ad-hoc/sync) → block on `fal_client.subscribe`, post-process, return final url.
"""

from __future__ import annotations

import asyncio
import os
import random
import time
from io import BytesIO
from pathlib import Path
from typing import Any, Optional

import httpx

from app.core.config import settings
from app.core.dependencies import get_storage_service
from app.core.model_registry import (
    get_model_by_id,
    get_model_by_name,
    resolve_endpoint_id,
)
from app.services.fal_service import FalService


_DEFAULT_TTS_ENDPOINT = "fal-ai/minimax/speech-2.8-turbo"
_DEFAULT_MUSIC_ENDPOINT = "fal-ai/elevenlabs/music"
_DEFAULT_SFX_ENDPOINT = "fal-ai/elevenlabs/sound-effects/v2"


class AudioGenerator:
    """Generates audio (TTS, music, SFX) via fal.ai."""

    def __init__(self) -> None:
        use_mock_audio = os.getenv("USE_MOCK_AUDIO", "").lower() == "true"
        self.use_mock = use_mock_audio or settings.use_mock_veo
        self.storage = get_storage_service()
        self.fal = FalService()

        if self.use_mock:
            print("[AudioGenerator] MOCK mode — using gTTS")
        else:
            print("[AudioGenerator] PRODUCTION mode — using fal.ai")

        # Default voice used when no `voice` is passed
        self.default_minimax_voice = "English_Upbeat_Woman"
        self.default_eleven_voice = "Rachel"
        # MiniMax native voices (sent as `voice_id` in `voice_setting`).
        self._minimax_voices = {
            "English_Upbeat_Woman",
            "English_CalmWoman",
            "English_radiant_girl",
            "English_compelling_lady1",
            "English_Wiselady",
            "English_magnetic_voiced_man",
            "English_Trustworth_Man",
            "English_ManWithDeepVoice",
            "English_Steadymentor",
            "English_Diligent_Man",
        }
        # Fallback: ElevenLabs-style friendly names mapped into MiniMax voice_ids
        # (used only when a non-native voice is selected for the minimax endpoint).
        self._eleven_to_minimax = {
            "Rachel": "English_Upbeat_Woman",
            "Bella": "English_radiant_girl",
            "Elli": "English_CalmWoman",
            "Domi": "English_compelling_lady1",
            "Adam": "English_magnetic_voiced_man",
            "Antoni": "English_Trustworth_Man",
            "Arnold": "English_ManWithDeepVoice",
            "Josh": "English_Steadymentor",
            "Sam": "English_Diligent_Man",
        }

    def _resolve_voice_for_endpoint(self, endpoint_id: str, voice: str) -> str:
        """Return the provider-specific voice identifier for the chosen TTS endpoint.

        * For MiniMax: use a MiniMax voice_id if provided; otherwise translate from
          an ElevenLabs-style friendly name; otherwise use the MiniMax default.
        * For ElevenLabs: pass the friendly voice name through as-is (fal.ai's
          ElevenLabs endpoint accepts names like 'Rachel', 'Adam', etc.).
        """
        ep = (endpoint_id or "").lower()
        v = (voice or "").strip()
        if "minimax" in ep:
            if v in self._minimax_voices:
                return v
            if v in self._eleven_to_minimax:
                return self._eleven_to_minimax[v]
            return self.default_minimax_voice
        # ElevenLabs (or unknown endpoint): pass friendly name through.
        return v or self.default_eleven_voice

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

        try:
            from gtts import gTTS

            def generate_gtts() -> Optional[bytes]:
                try:
                    fp = BytesIO()
                    gTTS(text=text, lang="en", slow=False).write_to_fp(fp)
                    fp.seek(0)
                    return fp.read()
                except Exception:
                    return None

            loop = asyncio.get_event_loop()
            audio_bytes = await loop.run_in_executor(None, generate_gtts)
            if audio_bytes:
                filename = f"mock_speech_{int(time.time())}_{random.randint(1000, 9999)}.mp3"
                audio_url = await self.storage.upload_file(audio_bytes, filename, "audio/mpeg")
                return {"success": True, "audio_url": audio_url, "text": text,
                        "voice": voice, "mock": True}
        except ImportError:
            print("[AudioGenerator] MOCK: gTTS not installed.")
        except Exception as e:
            print(f"[AudioGenerator] MOCK: gTTS error: {e}")

        return {"success": False, "error": "Mock generation failed"}

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
    async def generate_speech(
        self, text: str, voice: str = "Rachel", model_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Generate speech from text via fal.ai."""
        if self.use_mock:
            return await self._mock_generate(text, voice)
        if not text or not text.strip():
            return {"success": False, "error": "No text provided"}

        endpoint_id = self._resolve_endpoint(model_id, _DEFAULT_TTS_ENDPOINT, "tts")
        voice_id = self._resolve_voice_for_endpoint(endpoint_id, voice)
        args = FalService.build_tts_args(text=text, voice=voice_id)
        model_info = self._model_info(endpoint_id, "TTS")

        resp = await self.fal.dispatch_for_generator(
            capability="tts",
            endpoint_id=endpoint_id,
            arguments=args,
            model_info=model_info,
            args_meta={"chars": len(text), "voice": voice_id},
        )
        if not resp.get("success"):
            return resp
        if resp.get("status") == "pending_fal":
            return resp  # NodeRunner / workflow will wait on webhook

        # Sync mode: post-process
        output = FalService.extract_output("tts", resp.get("raw_output"))
        if not output.get("success"):
            return output
        output["audio_url"] = await self._fetch_and_upload(output["audio_url"])
        return await self._with_cost(output, endpoint_id, chars=len(text),
                                     duration_s=output.get("duration"),
                                     model_info=model_info)

    async def generate_music(
        self, prompt: str, duration: int = 15, model_id: Optional[str] = None,
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
            model_info=model_info, args_meta={"duration_s": duration},
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
        self, prompt: str, duration: int = 10, model_id: Optional[str] = None,
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
            model_info=model_info, args_meta={"duration_s": duration},
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

    async def generate_multiple(self, texts: list[str], voice: str = "Rachel") -> list[dict]:
        results = []
        for idx, text in enumerate(texts):
            print(f"[AudioGenerator] Generating audio {idx + 1}/{len(texts)}...")
            results.append(await self.generate_speech(text=text, voice=voice))
        return results

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
