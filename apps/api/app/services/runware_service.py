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
            return {"success": False, "error": "RUNWARE_API_KEY environment variable is not set"}
            
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        # Ensure all tasks have a UUID and includeCost for billing
        for task in tasks:
            if "taskUUID" not in task:
                task["taskUUID"] = str(uuid.uuid4())
            task["includeCost"] = True  # Required for cost-based billing
                
        task_type = tasks[0].get("taskType", "unknown") if tasks else "unknown"
        model = tasks[0].get("model", "unknown") if tasks else "unknown"
        print(f"[Runware] POST {task_type} | model: {model}")
        
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                response = await client.post(self.api_url, json=tasks, headers=headers)
                
                if response.status_code != 200:
                    try:
                        error_data = response.json()
                        err_msg = error_data.get("error", {}).get("message")
                        if not err_msg and "errors" in error_data and error_data["errors"]:
                            err_msg = error_data["errors"][0].get("message")
                        if not err_msg:
                            err_msg = response.text
                    except Exception:
                        err_msg = response.text
                    return {"success": False, "error": f"Runware API HTTP {response.status_code}: {err_msg}"}
                    
                result = response.json()
                
                # Top-level error object
                if "error" in result:
                    return {"success": False, "error": str(result["error"])}
                    
                data = result.get("data", [])
                errors = result.get("errors", [])
                if errors:
                    err = errors[0]
                    err_msg = err.get("message", str(err)) if isinstance(err, dict) else str(err)
                    return {"success": False, "error": f"Runware error: {err_msg}"}

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
                error_msg = resp.get("error", "")
                
                # If it's a 4xx error (like 400 Bad Request) or explicit API error, it's likely permanent (e.g. content moderation)
                if "HTTP 4" in error_msg or "Runware error:" in error_msg or "Runware task error:" in error_msg:
                    print(f"[RunwareService] Permanent error during polling: {error_msg}")
                    return {"success": False, "error": error_msg}
                
                # Sometimes a transient network error happens while polling. 
                # Let's log it, wait, and try again, rather than failing immediately.
                print(f"[RunwareService] Warning: Poll request failed (likely transient): {error_msg}")
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

    async def generate_image(self, prompt: str, width: int = 1024, height: int = 1024, model: str = "bfl:flux-2@dev", number_results: int = 1) -> dict:
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
            "model": model,
            "cost": data.get("cost", 0.0),
        }

    async def image_to_image(self, prompt: str, image_url: str, width: int = 1024, height: int = 1024, model: str = "bfl:flux-2@dev", strength: float = 0.8) -> dict:
        """Generate an image based on an input image and prompt."""
        seed_image = await self._url_to_data_uri(image_url)

        # Base task structure
        task: Dict[str, Any] = {
            "taskType": "imageInference",
            "positivePrompt": prompt,
            "width": width,
            "height": height,
            "model": model
        }

        provider = model.split(":")[0].lower() if ":" in model else ""

        # Construct payload based on provider-specific requirements
        if provider in ("google", "openai"):
            # Google (Gemini/Imagen) & OpenAI (GPT Image):
            # Uses top-level referenceImages array, no strength
            task["referenceImages"] = [seed_image]
        elif provider == "klingai":
            # Kling AI: Uses nested inputs.referenceImages, no strength
            task["inputs"] = {"referenceImages": [seed_image]}
        elif provider == "bytedance":
            # ByteDance (SeedEdit/Seedream): Uses top-level referenceImages array
            task["referenceImages"] = [seed_image]
        elif provider == "recraft":
            # Recraft V4 currently has inconsistent I2I support on Runware REST.
            # We'll try referenceImages (top-level) but it may still return 400.
            task["referenceImages"] = [seed_image]
        elif provider == "xai":
            # Grok / xAI: Uses seedImage + strength
            task["seedImage"] = seed_image
            task["strength"] = strength
        else:
            # Default (Flux/SD/Runware): Uses seedImage (string) and strength (float)
            task["seedImage"] = seed_image
            task["strength"] = strength
        
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
            "model": model,
            "cost": data.get("cost", 0.0),
        }

    # ── Dimension tables ────────────────────────────────────────────────────
    #
    # VIDEO default: standard broadcast resolutions (720p, 1080p …).
    # IMAGE default: every value is a multiple of 64 so FLUX / SD / Runware
    #   native models never reject the payload.
    # Per-model overrides live in _MODEL_DIMENSIONS and are returned AS-IS
    #   (they contain the exact values each provider's API accepts).

    _VIDEO_DEFAULT_DIMENSIONS = {
        "16:9": (1280, 720),
        "9:16": (720, 1280),
        "1:1":  (960, 960),
        "4:3":  (960, 720),
        "3:4":  (720, 960),
    }

    _IMAGE_DEFAULT_DIMENSIONS = {
        "16:9": (1024, 576),
        "9:16": (576, 1024),
        "1:1":  (1024, 1024),
        "4:3":  (1024, 768),
        "3:4":  (768, 1024),
        "3:2":  (1152, 768),
        "2:3":  (768, 1152),
        "21:9": (1344, 576),
    }

    # Keys are model-ID prefixes (matched via str.startswith).
    # Values map aspect_ratio → (width, height).
    # These are the EXACT dimensions each provider accepts — never modify them.
    _MODEL_DIMENSIONS: Dict[str, Dict[str, tuple]] = {
        # ── Video models ──────────────────────────────────────────
        "klingai:kling-video@3-pro": {
            "16:9": (1920, 1080),
            "9:16": (1080, 1920),
            "1:1":  (1440, 1440),
            "4:3":  (1440, 1080),
            "3:4":  (1080, 1440),
        },
        "minimax:4@1": {
            "16:9": (1366, 768),
            "9:16": (768, 1366),
            "1:1":  (1024, 1024),
        },
        # Google video (Veo) — conservative dimensions verified to work.
        "google:": {
            "16:9": (1280, 720),
            "9:16": (720, 1280),
            "1:1":  (1024, 1024),
            "4:3":  (960, 720),
            "3:4":  (720, 960),
            "3:2":  (1152, 768),
            "2:3":  (768, 1152),
            "21:9": (1344, 576),
        },

        # ── Image models ─────────────────────────────────────────
        "bytedance:seedream": {
            "16:9": (2560, 1440),
            "9:16": (1440, 2560),
            "1:1":  (2048, 2048),
            "4:3":  (2048, 1536),
            "3:4":  (1536, 2048),
        },
        "recraft:v4": {
            "16:9": (1024, 576),
            "9:16": (576, 1024),
            "1:1":  (1024, 1024),
            "4:3":  (1024, 768),
            "3:4":  (768, 1024),
        },
        "klingai:kling-image": {
            "16:9": (1360, 768),
            "9:16": (768, 1360),
            "1:1":  (1024, 1024),
            "4:3":  (1168, 880),
            "3:4":  (880, 1168),
            "3:2":  (1248, 832),
            "2:3":  (832, 1248),
            "21:9": (1552, 656),
        },
        "openai:1": {
            "16:9": (1536, 1024),
            "9:16": (1024, 1536),
            "1:1":  (1024, 1024),
        },
        "openai:2": {
            "16:9": (1792, 1024),
            "9:16": (1024, 1792),
            "1:1":  (1024, 1024),
        },
    }

    def _resolve_dimensions(self, model: str, aspect_ratio: str) -> tuple:
        """Return (width, height) for a VIDEO model and aspect ratio."""
        for prefix, dim_map in self._MODEL_DIMENSIONS.items():
            if model.startswith(prefix):
                return dim_map.get(aspect_ratio, dim_map.get("16:9", (1280, 720)))
        return self._VIDEO_DEFAULT_DIMENSIONS.get(aspect_ratio, (1280, 720))

    def _resolve_image_dimensions(self, model: str, aspect_ratio: str) -> tuple:
        """Return (width, height) for an IMAGE model and aspect ratio.

        Model-specific entries are returned as-is (providers dictate exact
        pixel values).  The fallback is _IMAGE_DEFAULT_DIMENSIONS where
        every value is a multiple of 64 — safe for FLUX, SD, and Runware
        native models.
        """
        for prefix, dim_map in self._MODEL_DIMENSIONS.items():
            if model.startswith(prefix):
                return dim_map.get(aspect_ratio, dim_map.get("16:9", (1024, 576)))
        return self._IMAGE_DEFAULT_DIMENSIONS.get(aspect_ratio, (1024, 576))

    def _resolve_duration(self, model: str, duration: int) -> int | float:
        """Return valid duration for the model constraints."""
        if model.startswith("google:"):
            # Veo 3.1 only supports 4, 6, 8
            if duration <= 4: return 4
            elif duration <= 6: return 6
            else: return 8
        return duration

    def _audio_provider_settings(self, model: str, generate_audio: bool) -> Optional[Dict[str, Any]]:
        """Build providerSettings for native audio generation if supported."""
        if not generate_audio:
            return None
        provider = model.split(":")[0].lower() if ":" in model else ""
        # Verified payload shape on Runware for Veo:
        # providerSettings.google.generateAudio = true
        if provider == "google":
            return {"google": {"generateAudio": True}}
        return None

    async def generate_video(
        self,
        prompt: str,
        model: str = "klingai:kling-video@3-standard",
        duration: int = 5,
        aspect_ratio: str = "16:9",
        generate_audio: bool = False,
    ) -> dict:
        """Generate a video from text."""
        width, height = self._resolve_dimensions(model, aspect_ratio)
        resolved_duration = self._resolve_duration(model, duration)
        
        print(f"[VideoGenerator] Resolved dimensions for {model} ({aspect_ratio}): {width}x{height}, duration: {resolved_duration}")

        task = {
            "taskType": "videoInference",
            "model": model,
            "outputType": "URL",
            "outputFormat": "MP4",
            "positivePrompt": prompt,
            "duration": resolved_duration,
            "width": width,
            "height": height
        }

        provider_settings = self._audio_provider_settings(model, generate_audio)
        if provider_settings:
            task["providerSettings"] = provider_settings
        elif generate_audio:
            return {
                "success": False,
                "error": (
                    f"Native audio was requested but model '{model}' does not support it. "
                    "Please either disable 'Generate Audio' or switch to an audio-capable model (e.g. Google Veo 3.1 / Veo 3.1 Fast)."
                ),
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
            "model": model,
            "cost": data.get("cost", 0.0),
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
                    raw_content_type = resp.headers.get("Content-Type", "image/jpeg")
                    content_type = raw_content_type.split(";")[0].strip()

                    # ⚠️ Guard: never wrap a video file as an image data URI.
                    # This can happen when ffprobe fails and a video URL leaks through
                    # as a start_image input — the MP4 would be labelled image/jpeg silently.
                    if content_type.startswith("video/"):
                        print(f"[RunwareService] _url_to_data_uri: ⚠️ URL is a video ({content_type}), not an image — returning raw URL. Frame extraction may have failed.")
                        return url

                    # Fallback to image/jpeg if it's not an image type
                    if not content_type.startswith("image/"):
                        content_type = "image/jpeg"
                        
                    b64_data = base64.b64encode(resp.content).decode("utf-8")
                    data_uri = f"data:{content_type};base64,{b64_data}"
                    print(f"[RunwareService] _url_to_data_uri: ✅ converted to data URI ({content_type}, {len(resp.content)} bytes)")
                    return data_uri
                else:
                    print(f"[RunwareService] _url_to_data_uri: ⚠️ HTTP {resp.status_code} — falling back to raw URL")
        except Exception as e:
            print(f"[RunwareService] _url_to_data_uri: ⚠️ Exception ({type(e).__name__}: {e}) — falling back to raw URL")
            
        # Fallback to the original URL if fetching fails
        print(f"[RunwareService] _url_to_data_uri: ⚠️ Using raw URL as fallback (may fail if not publicly accessible)")
        return url

    async def _upload_image_to_runware(self, image_data: str) -> Optional[str]:
        """Upload an image to Runware and return the imageUUID for use in video tasks.
        
        Accepts: data URI, base64 string, or publicly accessible URL.
        Returns: imageUUID string, or None on failure.
        
        Using imageUpload is the RELIABLE way to pass images to Runware video models.
        Passing data URIs directly in frameImages is inconsistently supported across providers.
        """
        task = {
            "taskType": "imageUpload",
            "image": image_data,
        }
        print(f"[RunwareService] Uploading image to Runware (imageUpload)...")
        resp = await self._post([task])
        if resp.get("success"):
            image_uuid = resp.get("data", {}).get("imageUUID")
            if image_uuid:
                print(f"[RunwareService] ✅ Image uploaded to Runware: {image_uuid}")
                return image_uuid
            print(f"[RunwareService] ⚠️ imageUpload succeeded but no imageUUID in response: {resp}")
        else:
            print(f"[RunwareService] ⚠️ imageUpload failed: {resp.get('error')} — will use data URI as fallback")
        return None

    async def image_to_video(
        self,
        image_url: str,
        prompt: str,
        model: str = "klingai:kling-video@3-standard",
        duration: int = 5,
        aspect_ratio: str = "16:9",
        end_image_url: Optional[str] = None,
        generate_audio: bool = False,
    ) -> dict:
        """Generate a video from a starting image (and optional end image).
        
        Flow:
        1. Convert image URL → data URI (handles localhost, S3 signed URLs, etc.)
        2. Upload to Runware via imageUpload → get stable imageUUID
        3. Pass imageUUID in provider-specific frameImages param
        4. Optionally upload end_image_url and add a second entry with frame="last"
        
        Provider payload structure:
        - klingai / runway / google: task["inputs"]["frameImages"] = [{"image": uuid, "frame": "first"}, {"image": uuid2, "frame": "last"}]
        - bytedance / minimax / pixverse:  task["frameImages"] = [{"inputImage": uuid, "frame": "first"}, {"inputImage": uuid2, "frame": "last"}]
        - alibaba (wan):      task["inputs"]["frameImages"] = [uuid]  ← end-frame NOT supported
        """
        # Convert aspect ratio to width/height (respects per-model overrides)
        width, height = self._resolve_dimensions(model, aspect_ratio)

        print(f"[RunwareService] image_to_video: model={model}, aspect_ratio={aspect_ratio}, has_end_image={bool(end_image_url)}")

        # Step 1: Convert the start URL to a data URI
        data_uri = await self._url_to_data_uri(image_url)

        # Step 2: Upload to Runware's imageUpload API to get a stable UUID.
        image_ref = await self._upload_image_to_runware(data_uri)
        if not image_ref:
            print(f"[RunwareService] Falling back to data URI directly in frameImages")
            image_ref = data_uri

        # ── Pre-flight guard ──────────────────────────────────────────────────
        is_data_uri = isinstance(image_ref, str) and image_ref.startswith("data:")
        is_uuid_ref = isinstance(image_ref, str) and len(image_ref) == 36 and image_ref.count("-") == 4
        is_video_url = isinstance(image_ref, str) and (
            ".mp4" in image_ref or
            ".webm" in image_ref or
            "vm.runware.ai" in image_ref
        )
        if not is_data_uri and not is_uuid_ref and is_video_url:
            return {
                "success": False,
                "error": (
                    "Cannot use a video as a frame image. "
                    "The 'start_frame'/'end_frame' extraction requires ffmpeg (ffprobe) to be installed. "
                    "Deploy the Docker image with ffmpeg to enable video-to-video chaining."
                )
            }

        # Step 3 (optional): Upload end image if provided
        end_image_ref: Optional[str] = None
        if end_image_url:
            end_data_uri = await self._url_to_data_uri(end_image_url)
            end_image_ref = await self._upload_image_to_runware(end_data_uri)
            if not end_image_ref:
                print(f"[RunwareService] End-image upload failed, falling back to data URI")
                end_image_ref = end_data_uri
            print(f"[RunwareService] End image ready: {str(end_image_ref)[:60]}")

        task: Dict[str, Any] = {
            "taskType": "videoInference",
            "model": model,
            "outputType": "URL",
            "outputFormat": "MP4",
            "positivePrompt": prompt,
            "duration": duration,
        }

        provider_settings = self._audio_provider_settings(model, generate_audio)
        if provider_settings:
            task["providerSettings"] = provider_settings
        elif generate_audio:
            return {
                "success": False,
                "error": (
                    f"Native audio was requested but model '{model}' does not support it. "
                    "Please either disable 'Generate Audio' or switch to an audio-capable model (e.g. Google Veo 3.1 / Veo 3.1 Fast)."
                ),
            }

        provider = model.split(":")[0].lower() if ":" in model else ""

        if provider == "google":
            # Google Veo: top-level frameImages with "inputImage" key
            # Ref: https://runware.ai/docs/en/providers/google
            task["width"] = width
            task["height"] = height
            frame_images = [{"inputImage": image_ref, "frame": "first"}]
            if end_image_ref:
                frame_images.append({"inputImage": end_image_ref, "frame": "last"})
                print(f"[RunwareService] Added end-frame to google payload")
            task["frameImages"] = frame_images

        elif provider in ("klingai", "runway"):
            # KlingAI / Runway: nested under inputs (legacy format, works in production)
            frame_images = [{"image": image_ref, "frame": "first"}]
            if end_image_ref:
                frame_images.append({"image": end_image_ref, "frame": "last"})
                print(f"[RunwareService] Added end-frame to {provider} payload")
            task["inputs"] = {"frameImages": frame_images}

        elif provider == "alibaba":
            # Wan 2.6 / Flash: plain string list, end-frame not supported
            if end_image_ref:
                print(f"[RunwareService] ⚠️ Alibaba (Wan) does not support end-frame — ignoring end image")
            task["inputs"] = {"frameImages": [image_ref]}
            task["resolution"] = "720p"

        else:
            # Bytedance (Seedance), MiniMax (Hailuo), PixVerse:
            task["width"] = width
            task["height"] = height
            frame_images = [{"inputImage": image_ref, "frame": "first"}]
            if end_image_ref:
                frame_images.append({"inputImage": end_image_ref, "frame": "last"})
                print(f"[RunwareService] Added end-frame to {provider} payload")
            task["frameImages"] = frame_images

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
            "model": model,
            "cost": data.get("cost", 0.0),
        }

    async def lipsync(self, video_url: str, audio_url: str, model: str = "klingai:7@1") -> dict:
        """Perform lip synchronization on a video using an audio track.
        Confirmed AIR ID: klingai:7@1 — https://runware.ai/docs/providers/klingai
        Requires inputs.video and inputs.audio fields.
        """
        safe_video_url = await self._url_to_data_uri(video_url)
        # Keep audio URLs as-is. _url_to_data_uri is image-oriented and can
        # incorrectly coerce non-image MIME types.
        safe_audio_url = audio_url
        
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
            "model": model,
            "cost": data.get("cost", 0.0),
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
            "model": model,
            "cost": data.get("cost", 0.0),
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
            "cost": data.get("cost", 0.0),
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
            "cost": data.get("cost", 0.0),
        }
