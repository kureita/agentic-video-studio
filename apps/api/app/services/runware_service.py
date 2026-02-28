import asyncio
import httpx
import uuid
import time
import base64
from typing import Dict, Any, List, Optional
from app.core.config import settings

# Generous read timeout since async models like Kling Image can take 2-4 minutes
_TIMEOUT = httpx.Timeout(connect=10.0, read=600.0, write=30.0, pool=5.0)

class RunwareService:
    """Unified service for image, video, and audio generation via Runware REST API."""
    
    def __init__(self):
        self.api_url = "https://api.runware.ai/v1"
        self.api_key = settings.runware_api_key
        
    async def _post(self, tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Send a JSON array of tasks to Runware API and return the first response."""
        if not self.api_key:
            return {"success": False, "error": "RUNWARE_API_KEY is not configured in .env.local"}
            
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        # Ensure all tasks have a UUID for tracing
        for task in tasks:
            if "taskUUID" not in task:
                task["taskUUID"] = str(uuid.uuid4())
                
        task_type = tasks[0].get("taskType", "unknown") if tasks else "unknown"
        model = tasks[0].get("model", "unknown") if tasks else "unknown"
        print(f"[Runware] POST {task_type} | model: {model}")
        
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                response = await client.post(self.api_url, json=tasks, headers=headers)
                
                if response.status_code != 200:
                    try:
                        error_data = response.json()
                        err_msg = error_data.get("error", {}).get("message", response.text)
                    except Exception:
                        err_msg = response.text
                    return {"success": False, "error": f"Runware API HTTP {response.status_code}: {err_msg}"}
                    
                result = response.json()
                
                # Top-level error object
                if "error" in result:
                    return {"success": False, "error": str(result["error"])}
                    
                data = result.get("data", [])
                if not data:
                    return {"success": False, "error": "Runware API returned no data"}
                    
                first_resp = data[0]
                # Check for task-level errors in the response
                if first_resp.get("taskType") == "error" or "error" in first_resp:
                    err_detail = first_resp.get("error", {}) or first_resp
                    err_msg = err_detail.get("message", str(err_detail)) if isinstance(err_detail, dict) else str(err_detail)
                    return {"success": False, "error": f"Runware task error: {err_msg}"}
                    
                return {"success": True, "data": first_resp}
        
        except httpx.TimeoutException:
            # httpx.ReadTimeout / ConnectTimeout have empty str() — always use explicit message
            print(f"[Runware] ⏱ Timeout on {task_type}/{model}")
            return {"success": False, "error": f"Runware timed out waiting for {task_type} with model '{model}'. Try a faster model (e.g. FLUX Schnell: runware:101@1 for images, Wan2.6 Flash: alibaba-wan2-6-flash for video)."}
        except asyncio.TimeoutError:
            print(f"[Runware] ⏱ asyncio timeout on {task_type}/{model}")
            return {"success": False, "error": "Runware API request timed out (asyncio)"}
        except httpx.RequestError as e:
            print(f"[Runware] 🔌 Network error: {type(e).__name__}: {e}")
            return {"success": False, "error": f"Runware network error ({type(e).__name__}): {str(e) or 'connection failed'}"}
        except Exception as e:
            print(f"[Runware] ❌ Unexpected error: {type(e).__name__}: {e}")
            return {"success": False, "error": f"Runware unexpected error ({type(e).__name__}): {str(e) or 'unknown'}"}

    async def _poll_task_completion(self, task_uuid: str, max_attempts: int = 60, delay: int = 10) -> dict:
        """Poll the getResponse endpoint until status is 'success' or 'error'."""
        print(f"[RunwareService] Async polling started for task {task_uuid}")
        for attempt in range(max_attempts):
            poll_task = {"taskType": "getResponse", "taskUUID": task_uuid}
            resp = await self._post([poll_task])
            
            if not resp["success"]:
                # Sometimes a transient network error happens while polling. 
                # Let's log it, wait, and try again, rather than failing immediately.
                print(f"[RunwareService] Warning: Poll request failed: {resp.get('error')}")
                await asyncio.sleep(delay)
                continue
                
            data = resp.get("data", {})
            print(f"[RunwareService DEBUG] Poll data: {data}")
            status = data.get("status")
            
            if status == "success" or data.get("videoURL") or data.get("imageURL") or data.get("audioURL"):
                print(f"[RunwareService] Task {task_uuid} completed successfully.")
                # The final response might contain the URL in the root of data 
                # or nested differently, let's just return what we got
                return {"success": True, "data": data}
            elif status == "failed" or status == "error" or data.get("error"):
                err_msg = str(data.get("error", "Unknown processing error"))
                return {"success": False, "error": f"Task failed during polling: {err_msg}"}
                
            # If status == processing or something else
            print(f"[RunwareService] Task {task_uuid} status: {status}, waiting {delay}s... (attempt {attempt+1}/{max_attempts})")
            await asyncio.sleep(delay)
            
        return {"success": False, "error": f"Task {task_uuid} timed out after {max_attempts*delay} seconds."}

    async def generate_image(self, prompt: str, width: int = 1024, height: int = 1024, model: str = "runware:101@1", number_results: int = 1) -> dict:
        """Generate an image from text."""
        task = {
            "taskType": "imageInference",
            "positivePrompt": prompt,
            "width": width,
            "height": height,
            "model": model,
            "numberResults": number_results
        }
        
        resp = await self._post([task])
        if not resp["success"]:
            return resp
            
        data = resp.get("data", {})
        if "imageURL" not in data and "taskUUID" in data:
            poll_resp = await self._poll_task_completion(data["taskUUID"], max_attempts=30, delay=5)
            if not poll_resp["success"]:
                return poll_resp
            data = poll_resp.get("data", {})
            
        image_url = data.get("imageURL")
        
        if not image_url:
            return {"success": False, "error": "No image URL in response"}
            
        return {
            "success": True,
            "image_url": image_url,
            "prompt": prompt,
            "model": model
        }

    async def image_to_image(self, prompt: str, image_url: str, width: int = 1024, height: int = 1024, model: str = "runware:101@1") -> dict:
        """Generate an image based on an input image and prompt."""
        task = {
            "taskType": "imageInference",
            "positivePrompt": prompt,
            "inputImage": image_url, # Can be direct URL to public image
            "width": width,
            "height": height,
            "model": model
        }
        
        resp = await self._post([task])
        if not resp["success"]:
            return resp
            
        data = resp.get("data", {})
        if "imageURL" not in data and "taskUUID" in data:
            poll_resp = await self._poll_task_completion(data["taskUUID"], max_attempts=30, delay=5)
            if not poll_resp["success"]:
                return poll_resp
            data = poll_resp.get("data", {})
            
        image_url = data.get("imageURL")
        if not image_url:
            return {"success": False, "error": "No image URL in response"}
            
        return {
            "success": True,
            "image_url": image_url,
            "prompt": prompt,
            "model": model
        }

    async def generate_video(self, prompt: str, model: str = "klingai:kling-video@3-standard", duration: int = 5, aspect_ratio: str = "16:9") -> dict:
        """Generate a video from text."""
        # Convert aspect ratio to width/height
        dimensions = {
            "16:9": (1280, 720),
            "9:16": (720, 1280),
            "1:1":  (960, 960),
            "4:3":  (960, 720),
            "3:4":  (720, 960)
        }
        width, height = dimensions.get(aspect_ratio, (1280, 720))

        task = {
            "taskType": "videoInference",
            "model": model,
            "outputType": "URL",
            "outputFormat": "MP4",
            "positivePrompt": prompt,
            "duration": duration,
            "width": width,
            "height": height
        }
        
        resp = await self._post([task])
        if not resp["success"]:
            return resp
            
        data = resp.get("data", {})
        if "videoURL" not in data and "taskUUID" in data:
            poll_resp = await self._poll_task_completion(data["taskUUID"])
            if not poll_resp["success"]:
                return poll_resp
            data = poll_resp.get("data", {})
            
        video_url = data.get("videoURL")
        if not video_url:
            return {"success": False, "error": "No video URL in response"}
            
        return {
            "success": True,
            "video_url": video_url,
            "duration": duration,
            "model": model
        }

    async def _url_to_data_uri(self, url: str) -> str:
        """Fetch a URL and convert it to a base64 data URI (e.g. data:image/jpeg;base64,...).
        This bypasses Runware's strict content-type URL validation for signed URLs.
        """
        if url.startswith("data:"):
            return url
            
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    content_type = resp.headers.get("Content-Type", "image/jpeg")
                    # Fallback to image/jpeg if it's application/octet-stream or text/plain
                    if "image" not in content_type:
                        content_type = "image/jpeg"
                        
                    b64_data = base64.b64encode(resp.content).decode("utf-8")
                    return f"data:{content_type};base64,{b64_data}"
        except Exception as e:
            print(f"[RunwareService] Error converting URL to Data URI: {e}")
            
        # Fallback to the original URL if fetching fails
        return url

    async def image_to_video(self, image_url: str, prompt: str, model: str = "klingai:kling-video@3-standard", duration: int = 5) -> dict:
        """Generate a video from a starting image."""
        
        # Safe-encode the URL to a Data URI because Runware rejects URLs lacking image Content-Type headers
        safe_image_data = await self._url_to_data_uri(image_url)
        
        task = {
            "taskType": "videoInference",
            "model": model,
            "outputType": "URL",
            "outputFormat": "MP4",
            "positivePrompt": prompt,
            "duration": duration,
            "inputs": {
                "frameImages": [
                    {
                        "image": safe_image_data,
                        "frame": "first"
                    }
                ]
            }
        }
        
        resp = await self._post([task])
        if not resp["success"]:
            return resp
            
        data = resp.get("data", {})
        if "videoURL" not in data and "taskUUID" in data:
            poll_resp = await self._poll_task_completion(data["taskUUID"])
            if not poll_resp["success"]:
                return poll_resp
            data = poll_resp.get("data", {})
            
        video_url = data.get("videoURL")
        if not video_url:
            return {"success": False, "error": "No video URL in response"}
            
        return {
            "success": True,
            "video_url": video_url,
            "duration": duration,
            "model": model
        }

    async def lipsync(self, video_url: str, audio_url: str, model: str = "klingai:7@1") -> dict:
        """Perform lip synchronization on a video using an audio track.
        Confirmed AIR ID: klingai:7@1 — https://runware.ai/docs/providers/klingai
        Requires inputs.video and inputs.audio fields.
        """
        safe_video_url = await self._url_to_data_uri(video_url)
        safe_audio_url = await self._url_to_data_uri(audio_url) if audio_url else audio_url
        
        task = {
            "taskType": "videoInference",
            "model": model,
            "outputType": "URL",
            "outputFormat": "MP4",
            "inputs": {
                "video": safe_video_url,
                "audio": safe_audio_url
            }
        }
        
        resp = await self._post([task])
        if not resp["success"]:
            return resp
            
        data = resp.get("data", {})
        if "videoURL" not in data and "taskUUID" in data:
            poll_resp = await self._poll_task_completion(data["taskUUID"])
            if not poll_resp["success"]:
                return poll_resp
            data = poll_resp.get("data", {})
            
        output_url = data.get("videoURL")
        if not output_url:
            return {"success": False, "error": "No video URL in response for lipsync"}
            
        return {
            "success": True,
            "video_url": output_url,
            "model": model
        }

    async def text_to_speech(self, text: str, voice: str = "English_Upbeat_Woman", model: str = "minimax:speech@2.8") -> dict:
        """Generate speech from text using MiniMax Speech 2.8 via Runware.
        Confirmed AIR ID: minimax:speech@2.8 — https://runware.ai/docs/providers/minimax
        Voice must be a valid MiniMax voice ID from the 332-voice library.
        """
        task = {
            "taskType": "audioInference",
            "model": model,
            "speech": {
                "text": text,
                "voice": voice
            }
        }
        
        resp = await self._post([task])
        if not resp["success"]:
            return resp
            
        data = resp.get("data", {})
        if "audioURL" not in data and "taskUUID" in data:
            poll_resp = await self._poll_task_completion(data["taskUUID"])
            if not poll_resp["success"]:
                return poll_resp
            data = poll_resp.get("data", {})
            
        audio_url = data.get("audioURL")
        if not audio_url:
            return {"success": False, "error": "No audio URL in response"}
            
        return {
            "success": True,
            "audio_url": audio_url,
            "text": text,
            "voice": voice,
            "model": model
        }

    async def generate_music(self, prompt: str, duration: int = 30, model: str = "elevenlabs:1@1") -> dict:
        """Generate music from a text prompt using ElevenLabs Music v1 via Runware.
        AIR ID: elevenlabs:1@1 — Eleven Music v1
        Supports detailed prompts describing genre, style, instruments, structure, and mood.
        Duration must be between 10-300 seconds (Runware constraint).
        """
        # Clamp duration to Runware's allowed range: 10-300 seconds
        duration = max(10, min(300, duration))
        
        task = {
            "taskType": "audioInference",
            "model": model,
            "positivePrompt": prompt,
            "duration": duration,
            "numberResults": 1,
            "outputFormat": "MP3",
            "outputType": "URL",
            "audioSettings": {
                "sampleRate": 22050,
                "bitrate": 32,
            },
        }
        
        resp = await self._post([task])
        if not resp["success"]:
            return resp
            
        data = resp.get("data", {})
        if "audioURL" not in data and "taskUUID" in data:
            poll_resp = await self._poll_task_completion(data["taskUUID"])
            if not poll_resp["success"]:
                return poll_resp
            data = poll_resp.get("data", {})
            
        audio_url = data.get("audioURL")
        if not audio_url:
            return {"success": False, "error": "No audio URL in music generation response"}
            
        return {
            "success": True,
            "audio_url": audio_url,
            "prompt": prompt,
            "model": model,
        }

    async def generate_sound_effects(self, prompt: str, duration: int = 10, model: str = "elevenlabs:1@1") -> dict:
        """Generate sound effects from a text prompt using ElevenLabs via Runware.
        AIR ID: elevenlabs:1@1 — same model handles both music and SFX based on prompt.
        Supports ambient sounds, impacts, whooshes, foley, and other audio textures.
        Duration must be between 10-300 seconds (Runware constraint).
        """
        # Clamp duration to Runware's allowed range: 10-300 seconds
        duration = max(10, min(300, duration))
        
        task = {
            "taskType": "audioInference",
            "model": model,
            "positivePrompt": prompt,
            "duration": duration,
            "numberResults": 1,
            "outputFormat": "MP3",
            "outputType": "URL",
            "audioSettings": {
                "sampleRate": 22050,
                "bitrate": 32,
            },
        }
        
        resp = await self._post([task])
        if not resp["success"]:
            return resp
            
        data = resp.get("data", {})
        if "audioURL" not in data and "taskUUID" in data:
            poll_resp = await self._poll_task_completion(data["taskUUID"])
            if not poll_resp["success"]:
                return poll_resp
            data = poll_resp.get("data", {})
            
        audio_url = data.get("audioURL")
        if not audio_url:
            return {"success": False, "error": "No audio URL in sound effects response"}
            
        return {
            "success": True,
            "audio_url": audio_url,
            "prompt": prompt,
            "model": model,
        }
