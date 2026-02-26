"""Audio Generator Service - Uses Runware API for text-to-speech."""

import asyncio
import os
import random
import time
import wave
import struct
import httpx
from pathlib import Path
from typing import Optional
from io import BytesIO

from app.core.config import settings
from app.core.dependencies import get_storage_service
from app.services.runware_service import RunwareService

_MODEL_MAP = {
    # Frontend display name → Official Runware AIR ID
    # Confirmed from: https://runware.ai/docs/providers/minimax (MiniMax Speech 2.8)
    "MiniMax":    "minimax:speech@2.8",
    "ElevenLabs": "minimax:speech@2.8",  # Map ElevenLabs to MiniMax via Runware
}

class AudioGenerator:
    """Generates audio using Runware API (minimax, etc)."""

    def __init__(self):
        use_mock_audio = os.getenv("USE_MOCK_AUDIO", "").lower() == "true"
        self.use_mock = use_mock_audio or settings.use_mock_veo
        self.storage = get_storage_service()
        self.runware = RunwareService()
        
        if self.use_mock:
            print("[AudioGenerator] Running in MOCK mode - using gTTS for free text-to-speech")
        else:
            print("[AudioGenerator] Running in PRODUCTION mode - using Runware API")
        
        # Default Runware voice
        self.default_voice = "English_Upbeat_Woman"  # MiniMax confirmed English voice
        self.default_model = "minimax:speech@2.8"      # Official Runware AIR ID
        
        # Frontend voice name → MiniMax TTS voice ID
        # Confirmed English voices from: https://runware.ai/docs/providers/minimax
        self.voice_ids = {
            # Female voices
            "Rachel":  "English_Upbeat_Woman",          # Warm, upbeat female
            "Bella":   "English_radiant_girl",           # Young, radiant female
            "Elli":    "English_CalmWoman",              # Calm, composed female
            "Domi":    "English_compelling_lady1",       # Compelling, expressive female
            # Male voices
            "Adam":    "English_magnetic_voiced_man",   # Rich, magnetic male
            "Antoni":  "English_Trustworth_Man",        # Trustworthy, clear male
            "Arnold":  "English_ManWithDeepVoice",      # Deep-voiced male
            "Josh":    "English_Steadymentor",          # Steady mentor tone
            "Sam":     "English_Diligent_Man",          # Diligent, professional male
        }

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

    async def _mock_generate(self, text: str, voice: str) -> dict:
        print(f"[AudioGenerator] MOCK: Generating speech for text: {text[:80]}...")
        mock_source = self._get_mock_audio()
        
        if mock_source and not mock_source.name.startswith("mock_"):
            try:
                with open(mock_source, "rb") as f:
                     content = f.read()
                filename = f"mock_reuse_{int(time.time())}.{mock_source.suffix.lstrip('.')}"
                audio_url = await self.storage.upload_file(content, filename, "audio/mpeg")
                return {
                    "success": True,
                    "audio_url": audio_url,
                    "text": text,
                    "voice": voice,
                    "mock": True,
                }
            except Exception:
                audio_url = f"{settings.api_base_url}/static/audio/{mock_source.name}"
                return {
                    "success": True,
                    "audio_url": audio_url,
                    "text": text,
                    "voice": voice,
                    "mock": True,
                }
        
        try:
            from gtts import gTTS
            import asyncio
            filename = f"mock_speech_{int(time.time())}_{random.randint(1000, 9999)}.mp3"
            
            def generate_gtts():
                try:
                    tts = gTTS(text=text, lang='en', slow=False)
                    fp = BytesIO()
                    tts.write_to_fp(fp)
                    fp.seek(0)
                    return fp.read()
                except Exception:
                    return None
            
            loop = asyncio.get_event_loop()
            audio_bytes = await loop.run_in_executor(None, generate_gtts)
            
            if audio_bytes:
                audio_url = await self.storage.upload_file(audio_bytes, filename, "audio/mpeg")
                return {
                    "success": True,
                    "audio_url": audio_url,
                    "text": text,
                    "voice": voice,
                    "mock": True,
                }
        except ImportError:
            print("[AudioGenerator] MOCK: gTTS not installed.")
        except Exception as e:
            print(f"[AudioGenerator] MOCK: Error with gTTS: {e}")
        
        # Fallback empty block
        return {"success": False, "error": "Mock generation failed"}

    async def _fetch_and_upload(self, url: str) -> Optional[str]:
        """Fetch file from URL and save to StorageService, returning the storage URL."""
        if not url: return None
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=120.0)
                if response.status_code == 200:
                    filename = f"speech_{int(time.time())}.mp3"
                    storage_url = await self.storage.upload_file(response.content, filename, "audio/mpeg")
                    return storage_url
        except Exception as e:
            print(f"[AudioGenerator] Error fetching audio {url}: {e}")
        return url # fallback to runware url

    def _get_model(self, model_name: Optional[str]) -> str:
        if not model_name: return self.default_model
        for key, val in _MODEL_MAP.items():
            if key in model_name:
                return val
        return self.default_model

    async def generate_speech(
        self,
        text: str,
        voice: str = "Rachel",
        model_id: str = "minimax-speech-2-8",
    ) -> dict:
        """Generate speech from text."""
        if self.use_mock:
            return await self._mock_generate(text, voice)
        
        if not text or not text.strip():
            return {"success": False, "error": "No text provided"}
        
        try:
            voice_id = self.voice_ids.get(voice, self.default_voice)
            target_model = self._get_model(model_id)
            print(f"[AudioGenerator] Generating speech: {text[:100]}..., voice: {voice_id}")
            
            result = await self.runware.text_to_speech(
                text=text,
                voice=voice_id,
                model=target_model
            )
            
            if result.get("success"):
                final_url = await self._fetch_and_upload(result.get("audio_url"))
                result["audio_url"] = final_url
                
            return result

        except Exception as e:
            print(f"[AudioGenerator] Error: {e}")
            return {"success": False, "error": str(e)}

    async def generate_multiple(
        self,
        texts: list[str],
        voice: str = "Rachel",
    ) -> list[dict]:
        """Generate speech for multiple texts."""
        results = []
        for idx, text in enumerate(texts):
            print(f"[AudioGenerator] Generating audio {idx + 1}/{len(texts)}...")
            result = await self.generate_speech(text=text, voice=voice)
            results.append(result)
        return results
