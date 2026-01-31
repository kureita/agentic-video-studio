"""Audio Generator Service - Uses ElevenLabs for voiceover generation."""

import asyncio
from typing import Optional

from elevenlabs import AsyncElevenLabs
from elevenlabs.core import ApiError

from app.core.config import settings


class AudioGenerator:
    """Generates voiceovers using ElevenLabs."""

    def __init__(self):
        self.client = AsyncElevenLabs(api_key=settings.elevenlabs_api_key)
        self.default_voice_id = settings.elevenlabs_voice_id

    async def generate_voiceover(
        self,
        text: str,
        voice_id: Optional[str] = None,
        model: str = "eleven_multilingual_v2",
    ) -> dict:
        """
        Generate voiceover audio from text.
        
        Args:
            text: The text to convert to speech
            voice_id: ElevenLabs voice ID (uses default if not provided)
            model: ElevenLabs model to use
            
        Returns:
            Dictionary with audio URL and metadata
        """
        voice = voice_id or self.default_voice_id
        
        try:
            # Generate audio
            audio_generator = await self.client.text_to_speech.convert(
                voice_id=voice,
                text=text,
                model_id=model,
                output_format="mp3_44100_128",
            )
            
            # Collect audio chunks
            audio_chunks = []
            async for chunk in audio_generator:
                audio_chunks.append(chunk)
            
            audio_data = b"".join(audio_chunks)
            
            # Save audio file (for MVP, local storage)
            import time
            filename = f"voiceover_{int(time.time())}.mp3"
            
            with open(filename, "wb") as f:
                f.write(audio_data)
            
            return {
                "success": True,
                "audio_url": f"/static/audio/{filename}",
                "filename": filename,
                "text": text,
                "voice_id": voice,
            }

        except ApiError as e:
            return {
                "success": False,
                "error": f"ElevenLabs API error: {str(e)}",
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    async def list_voices(self) -> list[dict]:
        """List available voices."""
        try:
            response = await self.client.voices.get_all()
            
            return [
                {
                    "voice_id": voice.voice_id,
                    "name": voice.name,
                    "category": voice.category,
                    "description": voice.description,
                }
                for voice in response.voices
            ]
        except Exception as e:
            print(f"Error listing voices: {e}")
            return []

    async def get_voice_preview(self, voice_id: str) -> Optional[str]:
        """Get preview URL for a voice."""
        try:
            voice = await self.client.voices.get(voice_id)
            return voice.preview_url
        except Exception:
            return None

