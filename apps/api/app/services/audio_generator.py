"""Audio Generator Service - Uses ElevenLabs for text-to-speech."""

import asyncio
import os
import random
import time
import wave
import struct
from pathlib import Path
from typing import Optional
import httpx

from app.core.config import settings


class AudioGenerator:
    """Generates audio using ElevenLabs text-to-speech API."""

    def __init__(self):
        # Check for dedicated audio mock flag first, fall back to general mock flag
        use_mock_audio = os.getenv("USE_MOCK_AUDIO", "").lower() == "true"
        self.use_mock = use_mock_audio or settings.use_mock_veo
        
        # Ensure output directory exists
        self.output_dir = Path("static/audio")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        if self.use_mock:
            print("[AudioGenerator] Running in MOCK mode - using gTTS for free text-to-speech")
            self.api_key = None
        else:
            if settings.elevenlabs_api_key:
                os.environ["ELEVENLABS_API_KEY"] = settings.elevenlabs_api_key
            self.api_key = os.getenv("ELEVENLABS_API_KEY")
            if not self.api_key:
                print("[AudioGenerator] WARNING: ELEVENLABS_API_KEY not set, switching to mock mode")
                self.use_mock = True
                print("[AudioGenerator] Running in MOCK mode - using gTTS for free text-to-speech")
            else:
                print("[AudioGenerator] Running in PRODUCTION mode - using ElevenLabs API")
        
        # ElevenLabs API endpoint
        self.api_base = "https://api.elevenlabs.io/v1"
        
        # Voice ID mapping (ElevenLabs premade voices)
        self.voice_ids = {
            "Rachel": "21m00Tcm4TlvDq8ikWAM",
            "Adam": "pNInz6obpgDQGcFmaJgB",
            "Antoni": "ErXwobaYiN019PkySvjV",
            "Arnold": "VR6AewLTigWG4xSOukaG",
            "Bella": "EXAVITQu4vr4xnSDxMaL",
            "Domi": "AZnzlk1XvdvUeBnXmlld",
            "Elli": "MF3mGyEYCl7XYWbV9V6O",
            "Josh": "TxGEqnHWrfWFTfGW9XjX",
            "Sam": "yoZ06aMxZJJ28mfd3POQ",
        }

    def _get_mock_audio(self) -> Optional[Path]:
        """Get a random existing audio from static/audio for mock mode."""
        audios = list(self.output_dir.glob("*.mp3")) + list(self.output_dir.glob("*.wav"))
        if audios:
            return random.choice(audios)
        return None

    async def _mock_generate(self, text: str, voice: str) -> dict:
        """Mock audio generation using gTTS (Google Text-to-Speech)."""
        print(f"[AudioGenerator] MOCK: Generating speech for text: {text[:80]}...")
        print(f"[AudioGenerator] MOCK: Voice: {voice} (gTTS uses default voice)")
        
        # Check if we have existing mock audio files to reuse
        mock_source = self._get_mock_audio()
        
        # Only reuse if it's not a mock file (to avoid reusing old mock files)
        if mock_source and not mock_source.name.startswith("mock_"):
            audio_url = f"{settings.api_base_url}/static/audio/{mock_source.name}"
            print(f"[AudioGenerator] MOCK: Reusing existing audio: {mock_source.name}")
            return {
                "success": True,
                "audio_url": audio_url,
                "text": text,
                "voice": voice,
                "mock": True,
            }
        
        # Try to use gTTS for actual speech in mock mode (free, no API key needed)
        try:
            from gtts import gTTS
            import asyncio
            
            filename = f"mock_speech_{int(time.time())}_{random.randint(1000, 9999)}.mp3"
            audio_path = self.output_dir / filename
            
            print(f"[AudioGenerator] MOCK: Generating speech with gTTS...")
            
            # Run gTTS in a thread pool to avoid blocking
            def generate_gtts():
                try:
                    tts = gTTS(text=text, lang='en', slow=False)
                    tts.save(str(audio_path))
                    return True
                except Exception as e:
                    print(f"[AudioGenerator] MOCK: gTTS generation error: {e}")
                    return False
            
            # Run in executor to avoid blocking the event loop
            loop = asyncio.get_event_loop()
            success = await loop.run_in_executor(None, generate_gtts)
            
            if success and audio_path.exists() and audio_path.stat().st_size > 0:
                audio_url = f"{settings.api_base_url}/static/audio/{filename}"
                print(f"[AudioGenerator] MOCK: Successfully created speech using gTTS ({audio_path.stat().st_size} bytes)")
                
                return {
                    "success": True,
                    "audio_url": audio_url,
                    "text": text,
                    "voice": voice,
                    "mock": True,
                }
            else:
                print(f"[AudioGenerator] MOCK: gTTS file creation failed or empty")
                raise Exception("gTTS file creation failed")
                
        except ImportError:
            print("[AudioGenerator] MOCK: gTTS not installed, falling back to silent audio")
            print("[AudioGenerator] MOCK: Install gTTS with: pip install gtts")
        except Exception as e:
            print(f"[AudioGenerator] MOCK: Error with gTTS: {e}")
        
        # Fallback: create silent WAV file
        print("[AudioGenerator] MOCK: Creating silent WAV file as fallback")
        filename = f"mock_speech_{int(time.time())}_{random.randint(1000, 9999)}.wav"
        audio_path = self.output_dir / filename
        
        # Generate a 2-second silent WAV file
        sample_rate = 44100  # 44.1 kHz
        duration = 2  # seconds
        num_samples = sample_rate * duration
        
        with wave.open(str(audio_path), 'w') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            
            # Write silent audio (all zeros)
            for _ in range(num_samples):
                wav_file.writeframes(struct.pack('<h', 0))
        
        audio_url = f"{settings.api_base_url}/static/audio/{filename}"
        print(f"[AudioGenerator] MOCK: Created silent WAV file: {filename}")
        
        return {
            "success": True,
            "audio_url": audio_url,
            "text": text,
            "voice": voice,
            "mock": True,
        }

    async def generate_speech(
        self,
        text: str,
        voice: str = "Rachel",
        model_id: str = "eleven_multilingual_v2",
    ) -> dict:
        """
        Generate speech from text using ElevenLabs.
        
        Args:
            text: Text to convert to speech
            voice: Voice name (Rachel, Adam, etc.)
            model_id: ElevenLabs model ID
            
        Returns:
            Dictionary with audio URL and metadata
        """
        # Use mock mode if enabled
        if self.use_mock:
            return await self._mock_generate(text, voice)
        
        if not text or not text.strip():
            return {
                "success": False,
                "error": "No text provided",
            }
        
        try:
            # Get voice ID
            voice_id = self.voice_ids.get(voice, self.voice_ids["Rachel"])
            
            print(f"[AudioGenerator] Generating speech: {text[:100]}...")
            print(f"[AudioGenerator] Voice: {voice} (ID: {voice_id})")
            
            # Prepare request
            url = f"{self.api_base}/text-to-speech/{voice_id}"
            headers = {
                "Accept": "audio/mpeg",
                "Content-Type": "application/json",
                "xi-api-key": self.api_key,
            }
            
            payload = {
                "text": text,
                "model_id": model_id,
                "voice_settings": {
                    "stability": 0.5,
                    "similarity_boost": 0.75,
                }
            }
            
            # Make API request
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, json=payload, headers=headers)
                
                if response.status_code == 200:
                    # Save the audio
                    filename = f"speech_{int(time.time())}_{random.randint(1000, 9999)}.mp3"
                    audio_path = self.output_dir / filename
                    
                    # Save audio data
                    with open(audio_path, "wb") as f:
                        f.write(response.content)
                    
                    audio_url = f"{settings.api_base_url}/static/audio/{filename}"
                    print(f"[AudioGenerator] Audio saved: {audio_url}")
                    
                    return {
                        "success": True,
                        "audio_url": audio_url,
                        "text": text,
                        "voice": voice,
                    }
                else:
                    error_msg = f"ElevenLabs API error: {response.status_code}"
                    try:
                        error_data = response.json()
                        error_msg = f"{error_msg} - {error_data.get('detail', {}).get('message', 'Unknown error')}"
                    except:
                        pass
                    
                    print(f"[AudioGenerator] Error: {error_msg}")
                    return {
                        "success": False,
                        "error": error_msg,
                    }

        except Exception as e:
            print(f"[AudioGenerator] Error: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    async def generate_multiple(
        self,
        texts: list[str],
        voice: str = "Rachel",
    ) -> list[dict]:
        """
        Generate speech for multiple texts.
        
        Args:
            texts: List of text strings
            voice: Voice name
            
        Returns:
            List of results with audio URLs
        """
        results = []
        total = len(texts)
        
        for idx, text in enumerate(texts):
            print(f"[AudioGenerator] Generating audio {idx + 1}/{total}...")
            
            result = await self.generate_speech(
                text=text,
                voice=voice,
            )
            
            results.append(result)
        
        return results
