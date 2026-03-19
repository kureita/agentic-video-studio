"""Node Runner Service - Executes workflow nodes based on their type."""

from typing import Dict, Any, List, Optional

from app.services.image_generator import ImageGenerator
from app.services.video_generator import VideoGenerator
from app.services.audio_generator import AudioGenerator
from app.services.editor_agent import EditorAgent
from app.core.model_registry import (
    VIDEO_MODELS,
    get_model_by_air_id,
    get_model_by_id,
    get_model_by_name,
    resolve_air_id,
)


class NodeRunner:
    """Runs individual workflow nodes by type."""

    def __init__(self):
        self.image_generator = ImageGenerator()
        self.video_generator = VideoGenerator()
        self.audio_generator = AudioGenerator()
        self.editor_agent = EditorAgent()
        self._default_video_model_id = "kling-video-3-standard"
        self._default_video_air_id = "klingai:kling-video@3-standard"

    async def run_node(
        self,
        node: Dict[str, Any],
        nodes: List[Dict[str, Any]],
        edges: List[Dict[str, Any]],
        outputs: Dict[str, Any],
        input_overrides: Optional[Dict[str, Any]] = None,
        strict_model_selection: bool = False,
    ) -> Dict[str, Any]:
        """
        Run a single node and return the result.
        
        Args:
            node: The node object to run
            nodes: All nodes in the workflow
            edges: All edges in the workflow  
            outputs: Existing outputs from previous nodes
            input_overrides: Optional overrides for node inputs
            strict_model_selection: If True, do not auto-fallback to other models
            
        Returns:
            Dict with success, output, and optional error
        """
        node_type = node.get("type")
        node_id = node.get("id")
        node_data = node.get("data", {})
        
        # Resolve inputs from connected nodes
        raw_inputs = self._resolve_inputs(node_id, nodes, edges, outputs)
        
        # editorAgent embeds URLs directly into TSX code that gets saved to MongoDB.
        # Presigned URLs expire (even at 7 days), so we must give the editor raw S3
        # URLs. The Remotion renderer on the frontend will call our /presign endpoint
        # to freshen them at render time.
        # All other node types receive presigned URLs as usual (they consume them immediately).
        if node_type == "editorAgent":
            inputs = raw_inputs  # raw S3 URLs — permanent, never expire
        else:
            inputs = self._presign_s3_urls(raw_inputs)
        
        # Apply overrides if provided
        if input_overrides:
            if node_type == "editorAgent":
                inputs.update(input_overrides)
            else:
                inputs.update(self._presign_s3_urls(input_overrides))
        
        print(f"[NodeRunner] Running node {node_id} (type: {node_type})")
        print(f"[NodeRunner] Resolved inputs: {list(inputs.keys())}")
        
        try:
            if node_type == "text":
                return await self._run_text_node(node_data, inputs)
            
            elif node_type == "upload":
                return await self._run_upload_node(node_data, inputs)
            
            elif node_type == "imageGen":
                return await self._run_image_gen_node(node_data, inputs, nodes)
            
            elif node_type == "audioGen":
                return await self._run_audio_gen_node(node_data, inputs, nodes)
            
            elif node_type == "videoGen":
                return await self._run_video_gen_node(
                    node_data,
                    inputs,
                    nodes,
                    strict_model_selection=strict_model_selection,
                )
            
            elif node_type == "vision" or node_type == "assistant":
                return await self._run_vision_node(node_data, inputs, nodes)
            
            elif node_type == "editorAgent":
                return await self._run_editor_agent_node(node_data, inputs, nodes, node_id=node_id, edges=edges, outputs=outputs)
            
            elif node_type == "mediaUpload":
                return await self._run_media_upload_node(node_data, inputs)
            
            # Legacy nodes (deprecated)
            elif node_type == "upscaler":
                return await self._run_upscaler_node(node_data, inputs)
            
            else:
                return {
                    "success": False,
                    "error": f"Unknown node type: {node_type}",
                }
                
        except Exception as e:
            print(f"[NodeRunner] Error running node {node_id}: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    def _presign_s3_urls(self, data: Any) -> Any:
        """Helper to recursively presign all S3 URLs in node inputs."""
        from app.services.storage_service import S3StorageService
        s3_service = S3StorageService()
        
        if isinstance(data, dict):
            return {k: self._presign_s3_urls(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._presign_s3_urls(item) for item in data]
        elif isinstance(data, str) and s3_service.is_s3_url(data):
            if data.startswith("http") and not (" " in data or "\n" in data):
                return s3_service.get_presigned_url(data)
        return data

    def _resolve_inputs(
        self,
        node_id: str,
        nodes: List[Dict[str, Any]],
        edges: List[Dict[str, Any]],
        outputs: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Resolve inputs for a node based on connected edges and existing outputs.
        
        Returns a dict with input handle names as keys.
        For inputs that can accept multiple connections (like ref_videos, ref_images),
        values are collected into lists.
        """
        inputs = {}
        
        for edge in edges:
            if edge.get("target") == node_id:
                source_id = edge.get("source")
                source_handle = edge.get("sourceHandle", "")
                target_handle = edge.get("targetHandle", "")
                
                print(f"[NodeRunner] Resolving edge: source={source_id}, target={node_id}")
                print(f"[NodeRunner] Handles: source_handle={source_handle}, target_handle={target_handle}")
                
                # Extract the handle name (format: "type|name")
                target_input_name = target_handle.split("|")[-1] if "|" in target_handle else target_handle
                source_handle_name = source_handle.split("|")[-1] if "|" in source_handle else source_handle
                
                print(f"[NodeRunner] Extracted target_input_name: {target_input_name}, source_handle_name: {source_handle_name}")
                
                # Get output from source node
                if source_id in outputs:
                    source_output = outputs[source_id]
                    
                    # Handle start_frame / end_frame extraction from video nodes
                    if source_handle_name in ("start_frame", "end_frame"):
                        # In the new architecture, frames are extracted in the browser using Canvas
                        # and saved directly to the outputs object as base64 strings.
                        frame_cache_key = f"{source_id}__{source_handle_name}"
                        if frame_cache_key in outputs:
                            source_output = outputs[frame_cache_key]
                            print(f"[NodeRunner] Loaded client-extracted {source_handle_name} from outputs: {str(source_output)[:30]}...")
                        else:
                            # ⚠️ Backwards compatibility / Headless execution fallback:
                            # If this is an autonomous "Run All", the client hasn't had a chance to extract it.
                            # We fall back to server-side ffmpeg extraction on the fly.
                            print(f"[NodeRunner] ⚙️ Missing {source_handle_name} for node {source_id} — falling back to server-side ffmpeg extraction.")
                            source_node = next((n for n in nodes if n["id"] == source_id), None)
                            if source_node and source_node.get("type") in ("videoGen", "mediaUpload") and isinstance(source_output, str):
                                frame_url = self._extract_video_frame(
                                    source_output,
                                    frame_type=source_handle_name,
                                )
                                if frame_url:
                                    source_output = frame_url
                                    print(f"[NodeRunner] Extracted {source_handle_name} from video: {frame_url[:80]}...")
                                else:
                                    print(f"[NodeRunner] ❌ Failed server-side extraction for {source_handle_name} (deploy with ffmpeg to fix)")
                                    source_output = None
                            else:
                                source_output = None

                    # Skip None outputs (e.g. missing extracted frame)
                    if source_output is None:
                        print(f"[NodeRunner] Skipping input '{target_input_name}' — source output is None")
                        continue
                    
                    # For inputs that can accept multiple connections, collect into list
                    if target_input_name in ["ref_videos", "ref_images", "audio"]:
                        if target_input_name not in inputs:
                            inputs[target_input_name] = []
                        # Append to list if not already there
                        if isinstance(inputs[target_input_name], list):
                            inputs[target_input_name].append(source_output)
                        else:
                            inputs[target_input_name] = [inputs[target_input_name], source_output]
                    else:
                        # Single value inputs (overwrite if multiple connections)
                        inputs[target_input_name] = source_output
                    
                    print(f"[NodeRunner] Set input '{target_input_name}' from outputs: {str(source_output)[:100]}")
                else:
                    # Try to get from node data directly (for text nodes, etc.)
                    source_node = next((n for n in nodes if n["id"] == source_id), None)
                    if source_node:
                        source_data = source_node.get("data", {})
                        # For text nodes, the output is the text field
                        if source_node.get("type") == "text":
                            inputs[target_input_name] = source_data.get("text", "")
                            print(f"[NodeRunner] Set input '{target_input_name}' from text node data")
        
        return inputs

    def _extract_video_frame(self, video_url: str, frame_type: str = "start_frame") -> Optional[str]:
        """
        Fallback server-side extraction for headless workflows.
        Extract the first or last frame from a video URL and return it as a Base64 data URI.
        """
        import tempfile
        import subprocess
        import base64
        import os
        import httpx
        
        try:
            # Download the video to a temp file
            with httpx.Client(timeout=60.0) as client:
                resp = client.get(video_url)
                if resp.status_code != 200:
                    print(f"[NodeRunner] Failed to download video for frame extraction: HTTP {resp.status_code}")
                    return None
                
                os.makedirs("tmp", exist_ok=True)
                with tempfile.NamedTemporaryFile(suffix=".mp4", dir="tmp", delete=False) as tmp_video:
                    tmp_video.write(resp.content)
                    tmp_video_path = tmp_video.name
            
            tmp_frame_path = tmp_video_path.replace(".mp4", "_frame.jpg")
            
            try:
                if frame_type == "end_frame":
                    duration_result = subprocess.run(
                        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                         "-of", "default=noprint_wrappers=1:nokey=1", tmp_video_path],
                        capture_output=True, text=True, timeout=30
                    )
                    duration = float(duration_result.stdout.strip()) if duration_result.stdout.strip() else 0
                    seek_time = max(0, duration - 0.1)
                    
                    subprocess.run(
                        ["ffmpeg", "-y", "-ss", str(seek_time), "-i", tmp_video_path,
                         "-frames:v", "1", "-q:v", "2", tmp_frame_path],
                        capture_output=True, timeout=30
                    )
                else:
                    subprocess.run(
                        ["ffmpeg", "-y", "-i", tmp_video_path,
                         "-frames:v", "1", "-q:v", "2", tmp_frame_path],
                        capture_output=True, timeout=30
                    )
                
                if os.path.exists(tmp_frame_path) and os.path.getsize(tmp_frame_path) > 0:
                    with open(tmp_frame_path, "rb") as f:
                        frame_data = f.read()
                    b64 = base64.b64encode(frame_data).decode()
                    return f"data:image/jpeg;base64,{b64}"
                else:
                    print(f"[NodeRunner] Frame extraction produced no output file")
                    return None
                    
            finally:
                for path in [tmp_video_path, tmp_frame_path]:
                    try:
                        if os.path.exists(path):
                            os.unlink(path)
                    except Exception:
                        pass
                        
        except Exception as e:
            print(f"[NodeRunner] Frame extraction error: {e}")
            return None


    async def _run_text_node(
        self,
        data: Dict[str, Any],
        inputs: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Text node just outputs its text content."""
        text = data.get("text", "")
        return {
            "success": True,
            "output": text,
        }

    async def _run_upload_node(
        self,
        data: Dict[str, Any],
        inputs: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Upload node outputs the uploaded file URL."""
        file_url = data.get("file_url") or data.get("url") or data.get("output")
        
        if not file_url:
            return {
                "success": False,
                "error": "No file uploaded",
            }
        
        return {
            "success": True,
            "output": file_url,
        }

    def _resolve_prompt_references(self, prompt: str, nodes: List[Dict[str, Any]]) -> str:
        """Resolve @Text #N references in prompt."""
        if not prompt or not isinstance(prompt, str):
            return prompt
            
        import re
        
        # Find all Text #N patterns
        matches = re.finditer(r"@Text\s*#(\d+)", prompt, re.IGNORECASE)
        
        resolved_prompt = prompt
        
        # Get all text nodes, preserving order from the list (creation/list order)
        text_nodes = [n for n in nodes if n.get("type") == "text"]
        
        for match in matches:
            full_match = match.group(0)
            index_str = match.group(1)
            
            try:
                index = int(index_str) - 1 # 1-based to 0-based
                if 0 <= index < len(text_nodes):
                    target_node = text_nodes[index]
                    # Get text content
                    text_content = target_node.get("data", {}).get("text", "")
                    resolved_prompt = resolved_prompt.replace(full_match, text_content)
            except Exception:
                pass # Ignore invalid references
                
        return resolved_prompt

    async def _run_image_gen_node(
        self,
        data: Dict[str, Any],
        inputs: Dict[str, Any],
        nodes: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Generate image using the ImageGenerator service."""
        # Get prompt from node data (typed) or inputs (connected)
        # Favor typed prompt if it exists, allowing for inspiration usage
        raw_prompt = data.get("prompt", "")
        if not raw_prompt:
            raw_prompt = inputs.get("prompt", "")
            
        # Resolve references (e.g. @Text #1)
        prompt = self._resolve_prompt_references(raw_prompt, nodes)
        
        # Get reference image from inputs (if any)
        reference_image = inputs.get("image")
        
        print(f"[NodeRunner] Image Gen Debug - inputs keys: {list(inputs.keys())}")
        print(f"[NodeRunner] Image Gen Debug - reference_image: {reference_image[:100] if reference_image else None}")
        print(f"[NodeRunner] Image Gen Debug - prompt: {prompt[:100] if prompt else None}")
        
        if not prompt and not reference_image:
            return {
                "success": False,
                "error": "No prompt or reference image provided",
            }
            
        # If we have an image but no prompt, provide a default prompt
        if reference_image and not prompt:
            prompt = "Variation of this image"
        
        # Get generation parameters
        model = data.get("model", "flux-2-dev")
        ratio = data.get("ratio", "1:1")
        count = data.get("count", 1)
        
        # Map aspect ratio
        aspect_ratio = ratio.replace(":", "/")
        
        # Determine style based on model
        style = "realistic"
        if "stable" in model.lower():
            style = "cinematic"
        
        print(f"[NodeRunner] Generating image: prompt='{prompt[:50]}...', model={model}, ratio={ratio}, has_ref_image={bool(reference_image)}")
        
        # Generate image(s)
        # For now, generate one image (we could extend to generate multiple)
        try:
            result = await self.image_generator.generate_image(
                prompt=prompt,
                aspect_ratio=ratio,
                style=style,
                reference_image=reference_image,
                model_name=model,
            )
            
            if result.get("success"):
                return {
                    "success": True,
                    "output": result.get("image_url"),
                    "cost": result.get("cost", 0.0),
                    "model": result.get("model", model),
                    "provider": result.get("provider", "Runware"),
                }
            else:
                return {
                    "success": False,
                    "error": result.get("error", "Image generation failed"),
                }
        except Exception as e:
             return {
                "success": False,
                "error": f"Generator Error: {str(e)}",
            }

    async def _run_audio_gen_node(
        self,
        data: Dict[str, Any],
        inputs: Dict[str, Any],
        nodes: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Generate audio using the AudioGenerator service.
        
        Supports three audio types:
        - 'speech' (default): Text-to-speech with voice selection
        - 'music': AI-generated music from a descriptive prompt
        - 'sfx': AI-generated sound effects from a descriptive prompt
        """
        # Get audio type from node data (defaults to "speech" for backward compat)
        audio_type = data.get("audioType", "speech")
        
        # Get text/prompt from node data (typed) or inputs (connected)
        raw_text = data.get("prompt", "")
        if not raw_text:
            raw_text = inputs.get("prompt", "")
            
        # Resolve references (e.g. @Text #1)
        text = self._resolve_prompt_references(raw_text, nodes)
        
        if not text or not text.strip():
            return {
                "success": False,
                "error": f"No text/prompt provided for {audio_type} generation",
            }
        
        print(f"[NodeRunner] Generating audio: type='{audio_type}', text='{text[:50]}...'")
        
        try:
            selected_model = data.get("model")
            if audio_type == "music":
                # Get duration from node data (default 15s for music)
                duration = data.get("duration", 15)
                if isinstance(duration, str):
                    duration = int(duration.replace("s", "").strip()) if duration.replace("s", "").strip().isdigit() else 15
                
                result = await self.audio_generator.generate_music(
                    prompt=text,
                    duration=duration,
                    model_id=selected_model if isinstance(selected_model, str) else None,
                )
            elif audio_type == "sfx":
                # Get duration from node data (default 5s for SFX)
                duration = data.get("duration", 5)
                if isinstance(duration, str):
                    duration = int(duration.replace("s", "").strip()) if duration.replace("s", "").strip().isdigit() else 5
                
                result = await self.audio_generator.generate_sfx(
                    prompt=text,
                    duration=duration,
                    model_id=selected_model if isinstance(selected_model, str) else None,
                )
            else:
                # Default: speech (TTS)
                voice = data.get("voice", "Rachel")
                result = await self.audio_generator.generate_speech(
                    text=text,
                    voice=voice,
                    model_id=selected_model if selected_model else "minimax-speech-2-8",
                )
            
            if result.get("success"):
                return {
                    "success": True,
                    "output": result.get("audio_url"),
                    "cost": result.get("cost", 0.0),
                    "model": result.get("model", data.get("model", audio_type)),
                    "provider": result.get("provider", "Runware"),
                }
            else:
                return {
                    "success": False,
                    "error": result.get("error", f"{audio_type.capitalize()} generation failed"),
                }
        except Exception as e:
            return {
                "success": False,
                "error": f"Audio Generator Error ({audio_type}): {str(e)}",
            }

    async def _run_video_gen_node(
        self,
        data: Dict[str, Any],
        inputs: Dict[str, Any],
        nodes: List[Dict[str, Any]],
        strict_model_selection: bool = False,
    ) -> Dict[str, Any]:
        """Generate video using the VideoGenerator service."""
        # Get prompt from text input
        raw_prompt = inputs.get("text") or inputs.get("prompt") or data.get("prompt", "")
        
        # Resolve references (e.g. @Text #1)
        prompt = self._resolve_prompt_references(raw_prompt, nodes)
        
        # Get various image/video inputs
        start_image = inputs.get("start_image")
        end_image = inputs.get("end_image")
        reference_images = inputs.get("reference_images")
        reference_video = inputs.get("reference_video")
        audio_input = inputs.get("audio")
        if isinstance(audio_input, list):
            audio_input = audio_input[0] if audio_input else None
        
        # Build prompt
        if not prompt and not start_image and not reference_images and not reference_video:
            return {
                "success": False,
                "error": "No prompt or input media provided for video generation",
            }
        
        # Default prompt if only media is provided
        if not prompt:
            if start_image:
                prompt = "Animate this image with natural motion"
            elif reference_images:
                prompt = "Generate video using these reference images"
            elif reference_video:
                prompt = "Generate video based on this reference video"
        
        # Get generation parameters (duration: "5s"|"8s"|"10s" from UI, or int)
        duration_val = data.get("duration", "5s")
        if isinstance(duration_val, int):
            duration = duration_val
        elif isinstance(duration_val, str):
            duration = int(duration_val.replace("s", "").strip()) if duration_val.replace("s", "").strip().isdigit() else 5
        else:
            duration = 5
        ratio = data.get("ratio", "16:9")
        resolution = data.get("resolution", "720p")
        # Determine model
        model_str = data.get("model", self._default_video_model_id)
        use_fast_model = "fast" in model_str.lower()
        generate_audio_val = data.get("generateAudio", False)
        if isinstance(generate_audio_val, str):
            generate_audio = generate_audio_val.strip().lower() in ("1", "true", "yes", "on")
        else:
            generate_audio = bool(generate_audio_val)

        has_start_image = bool(start_image)
        selected_model_str, generate_audio, model_warning, was_swapped = self._select_video_model_for_inputs(
            requested_model=model_str,
            has_start_image=has_start_image,
            wants_native_audio=generate_audio,
        )
        if was_swapped:
            print(f"[NodeRunner] Adjusted video model for capabilities: '{model_str}' -> '{selected_model_str}'")
        if model_warning:
            print(f"[NodeRunner] {model_warning}")
        if strict_model_selection and was_swapped:
            return {
                "success": False,
                "error": (
                    f"{model_warning or 'Model does not support the required capabilities.'} "
                    "Please switch to a model that supports this setup "
                    "(e.g. pick an I2V model when Start Image is connected, and an audio-capable model when Native Audio is enabled)."
                ),
            }
        model_str = selected_model_str

        if resolution not in ("720p", "1080p"):
            resolution = "720p"
        
        print(f"[NodeRunner] Generating video: prompt='{prompt[:50]}...', model='{model_str}', duration={duration}s, ratio={ratio}, resolution={resolution}, fast={use_fast_model}, generate_audio={generate_audio}")
        print(f"[NodeRunner] Inputs: start_image={bool(start_image)}, end_image={bool(end_image)}, ref_images={bool(reference_images)}, ref_video={bool(reference_video)}")
        
        try:
            # Determine which generation method to use based on inputs
            
            # Case 1: Start + End image (interpolation)
            if start_image and end_image:
                print("[NodeRunner] Using interpolation (start + end image)")
                # Note: Need to fetch images first if they're URLs
                # For now, assuming they're already local paths or URLs that VideoGenerator can handle
                result = await self.video_generator.generate_with_interpolation(
                    prompt=prompt,
                    first_frame_path=start_image,
                    last_frame_path=end_image,
                    duration=duration,
                    aspect_ratio=ratio,
                    model_name=model_str,
                    generate_audio=generate_audio,
                )
            
            # Case 2: Start image only (image-to-video)
            elif start_image:
                print("[NodeRunner] Using image-to-video")
                result = await self.video_generator.generate_from_image(
                    prompt=prompt,
                    image_path=start_image,
                    duration=duration,
                    resolution=resolution,
                    aspect_ratio=ratio,
                    model_name=model_str,
                    audio_url=audio_input,
                    generate_audio=generate_audio,
                )
            
            # Case 3: Reference images (style/asset reference)
            elif reference_images:
                print("[NodeRunner] Using reference images")
                # reference_images might be a single URL or list
                ref_list = [reference_images] if isinstance(reference_images, str) else reference_images
                result = await self.video_generator.generate_with_reference_images(
                    prompt=prompt,
                    reference_images=ref_list,
                    duration=duration,
                    aspect_ratio=ratio,
                    model_name=model_str,
                    generate_audio=generate_audio,
                )
            
            # Case 4: Reference video (extend or use as reference)
            elif reference_video:
                print("[NodeRunner] Using reference video (extension)")
                # For video extension, we need the video object, not just URL
                # This might require downloading first - implement later
                return {
                    "success": False,
                    "error": "Reference video input not yet fully implemented",
                }
            
            # Case 5: Text-to-video (no input media)
            else:
                print("[NodeRunner] Using text-to-video")
                result = await self.video_generator.generate_clip(
                    prompt=prompt,
                    duration=duration,
                    use_fast_model=use_fast_model,  # Use Veo 3.1 Fast by default
                    resolution=resolution,
                    aspect_ratio=ratio,
                    model_name=model_str,
                    audio_url=audio_input,
                    generate_audio=generate_audio,
                )
            
            if result.get("success"):
                video_url = result.get("video_url")
                
                # Proactively extract start & end frames so connected imageGen nodes
                # can be auto-filled by the frontend without an extra run.
                print(f"[NodeRunner] Extracting start/end frames from generated video...")
                start_frame = self._extract_video_frame(video_url, "start_frame")
                end_frame = self._extract_video_frame(video_url, "end_frame")
                
                if start_frame:
                    print(f"[NodeRunner] ✅ Start frame extracted ({len(start_frame)} chars)")
                else:
                    print(f"[NodeRunner] ⚠️ Start frame extraction failed (ffmpeg may not be installed)")
                if end_frame:
                    print(f"[NodeRunner] ✅ End frame extracted ({len(end_frame)} chars)")
                else:
                    print(f"[NodeRunner] ⚠️ End frame extraction failed (ffmpeg may not be installed)")
                
                response: Dict[str, Any] = {
                    "success": True,
                    "output": video_url,
                    "start_frame": start_frame,
                    "end_frame": end_frame,
                    "cost": result.get("cost", 0.0),
                    "model": result.get("model", model_str),
                    "provider": result.get("provider", "Runware"),
                }
                if model_warning:
                    response["warning"] = model_warning
                return response
            else:
                return {
                    "success": False,
                    "error": result.get("error", "Video generation failed"),
                }
                
        except Exception as e:
            print(f"[NodeRunner] Video generation error: {e}")
            return {
                "success": False,
                "error": f"Video generation error: {str(e)}",
            }

    def _resolve_video_model_entry(self, model_input: str) -> Optional[Dict[str, Any]]:
        """Resolve a video model entry from id, display name, or AIR id."""
        if not model_input:
            return get_model_by_id(self._default_video_model_id)

        by_id = get_model_by_id(model_input)
        if by_id and by_id.get("type") == "video":
            return by_id

        by_name = get_model_by_name(model_input)
        if by_name and by_name.get("type") == "video":
            return by_name

        air_id = resolve_air_id(
            model_input=model_input,
            fallback_air_id=self._default_video_air_id,
            model_type="video",
        )
        by_air = get_model_by_air_id(air_id)
        if by_air and by_air.get("type") == "video":
            return by_air

        return get_model_by_air_id(self._default_video_air_id)

    def _pick_best_video_model(self, need_i2v: bool, need_audio: bool) -> Dict[str, Any]:
        """Pick a fallback video model that satisfies capability constraints."""
        def has_caps(entry: Dict[str, Any]) -> bool:
            caps = {c.lower() for c in entry.get("capabilities", [])}
            return (not need_i2v or "i2v" in caps) and (not need_audio or "audio" in caps)

        candidates = [m for m in VIDEO_MODELS if has_caps(m)]
        if not candidates:
            return get_model_by_id(self._default_video_model_id) or VIDEO_MODELS[0]

        def rank(entry: Dict[str, Any]) -> int:
            tier = str(entry.get("tier", "budget")).lower()
            tier_rank = {"premium": 0, "mid": 1, "budget": 2}.get(tier, 3)
            return tier_rank

        candidates.sort(key=rank)
        return candidates[0]

    def _select_video_model_for_inputs(
        self,
        requested_model: str,
        has_start_image: bool,
        wants_native_audio: bool,
    ) -> tuple[str, bool, Optional[str], bool]:
        """Ensure selected model supports requested i2v/audio combo.

        Returns:
            (model_name, generate_audio, warning_or_none, was_swapped)
        """
        entry = self._resolve_video_model_entry(requested_model)
        if not entry:
            entry = get_model_by_id(self._default_video_model_id)
        if not entry:
            return requested_model, wants_native_audio, None, False

        caps = {c.lower() for c in entry.get("capabilities", [])}
        need_i2v = has_start_image
        need_audio = wants_native_audio

        supports_i2v = "i2v" in caps
        supports_audio = "audio" in caps

        if (need_i2v and not supports_i2v) or (need_audio and not supports_audio):
            reason_bits: List[str] = []
            if need_i2v and not supports_i2v:
                reason_bits.append("image-to-video")
            if need_audio and not supports_audio:
                reason_bits.append("native audio")
            reason = " + ".join(reason_bits) if reason_bits else "requested capabilities"

            replacement = self._pick_best_video_model(need_i2v=need_i2v, need_audio=need_audio)
            replacement_name = str(replacement.get("name") or replacement.get("id") or self._default_video_model_id)
            warning = (
                f"Requested model '{entry.get('name', requested_model)}' does not support {reason}; "
                f"switched to '{replacement_name}'."
            )
            return replacement_name, wants_native_audio, warning, True

        return str(entry.get("name") or requested_model), wants_native_audio, None, False

    async def _run_vision_node(
        self,
        data: Dict[str, Any],
        inputs: Dict[str, Any],
        nodes: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Vision node - uses GPT-4o mini to process text and images."""
        import httpx
        import base64
        from openai import AsyncOpenAI
        from app.core.config import settings

        # Get instruction from node data
        raw_instruction = data.get("instruction", "")

        # Resolve references
        instruction = self._resolve_prompt_references(raw_instruction, nodes)

        # Get inputs
        text_input = inputs.get("text", "")
        ref_images = inputs.get("ref_images", [])
        ref_videos = inputs.get("ref_videos", [])

        if not instruction:
            return {
                "success": False,
                "error": "No instruction provided",
            }

        # Normalize to lists
        if isinstance(ref_images, str):
            ref_images = [ref_images] if ref_images else []
        if isinstance(ref_videos, str):
            ref_videos = [ref_videos] if ref_videos else []

        try:
            client = AsyncOpenAI(api_key=settings.openai_api_key)

            # Build user message content
            user_content = []

            # Text part
            prompt_text = f"Context:\n{text_input}\n\nInstruction:\n{instruction}" if text_input else instruction
            user_content.append({"type": "text", "text": prompt_text})

            # Attach reference images as base64 data URIs
            async with httpx.AsyncClient() as http_client:
                for img_url in ref_images:
                    if img_url:
                        try:
                            print(f"[Vision] Fetching image: {img_url[:80]}...")
                            resp = await http_client.get(img_url, timeout=30.0)
                            if resp.status_code == 200:
                                content_type = resp.headers.get("content-type", "image/jpeg").split(";")[0].strip()
                                if not content_type.startswith("image/"):
                                    content_type = "image/jpeg"
                                b64 = base64.b64encode(resp.content).decode()
                                user_content.append({
                                    "type": "image_url",
                                    "image_url": {"url": f"data:{content_type};base64,{b64}", "detail": "low"},
                                })
                            else:
                                print(f"[Vision] Failed to fetch image: {resp.status_code}")
                        except Exception as e:
                            print(f"[Vision] Error fetching image: {e}")

                # Note: GPT-4o mini doesn't support raw video — skip video inputs
                if ref_videos:
                    print(f"[Vision] Skipping {len(ref_videos)} video input(s) — not supported by GPT-4o mini")

            print(f"[Vision] Sending request to GPT-5 mini ({len(user_content)} content parts)...")

            response = await client.chat.completions.create(
                model="gpt-5-mini",
                messages=[{"role": "user", "content": user_content}],
            )

            output_text = response.choices[0].message.content or ""
            print(f"[Vision] Response: {output_text[:100]}...")

            return {
                "success": True,
                "output": output_text,
            }

        except Exception as e:
            print(f"[Vision] Error: {e}")
            return {
                "success": False,
                "error": f"Vision node error: {str(e)}",
            }

    async def _run_editor_agent_node(
        self,
        data: Dict[str, Any],
        inputs: Dict[str, Any],
        nodes: List[Dict[str, Any]],
        node_id: str = "unknown",
        edges: Optional[List[Dict[str, Any]]] = None,
        outputs: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Editor Agent node - generates Remotion TSX composition code for client-side rendering.
        
        Supports three modes:
        - 'compositor': when upstream editorAgent nodes are connected (stitches scenes)
        - 'scene': when node has instruction but no upstream editorAgent nodes (standalone scene)
        - None: default monolithic mode (backward compatible)
        """
        # Get instruction from node data
        raw_instruction = data.get("instruction", "")
        
        # Resolve references
        instruction = self._resolve_prompt_references(raw_instruction, nodes)
        
        # Get inputs
        text_input = inputs.get("text", "")
        raw_audio = inputs.get("audio", [])
        ref_images = inputs.get("ref_images", [])
        ref_videos = inputs.get("ref_videos", [])
        
        # Normalize to lists (handle both single values and lists)
        if isinstance(ref_images, str):
            ref_images = [ref_images] if ref_images else []
        elif not isinstance(ref_images, list):
            ref_images = []
            
        if isinstance(ref_videos, str):
            ref_videos = [ref_videos] if ref_videos else []
        elif not isinstance(ref_videos, list):
            ref_videos = []
        
        if not instruction:
            return {
                "success": False,
                "error": "No instruction provided",
            }
        
        # ── Detect mode ──────────────────────────────────────────────────
        mode = None
        upstream_scenes = []
        edges = edges or []
        outputs = outputs or {}
        
        # Check if any upstream nodes are also editorAgent type
        upstream_editor_ids = []
        for edge in edges:
            if edge.get("target") == node_id:
                source_id = edge.get("source")
                source_node = next((n for n in nodes if n["id"] == source_id), None)
                if source_node and source_node.get("type") == "editorAgent":
                    upstream_editor_ids.append(source_id)
        
        if upstream_editor_ids:
            # COMPOSITOR MODE: this node receives scene outputs from other editorAgent nodes
            mode = "compositor"
            for uid in upstream_editor_ids:
                scene_code = outputs.get(uid, "")
                if scene_code:
                    # Try to extract scene config from the code
                    import re
                    duration_match = re.search(r'sceneDurationInFrames\s*=\s*(\d+)', scene_code)
                    scene_duration = int(duration_match.group(1)) if duration_match else 90
                    
                    name_match = re.search(r'export\s+function\s+(\w+)', scene_code)
                    scene_label = name_match.group(1) if name_match else f"Scene_{uid[:6]}"
                    
                    upstream_scenes.append({
                        "code": scene_code,
                        "durationFrames": scene_duration,
                        "label": scene_label,
                        "nodeId": uid,
                    })
            
            print(f"[NodeRunner] Editor Agent COMPOSITOR mode: {len(upstream_scenes)} upstream scenes")
        elif not ref_videos and not ref_images:
            # SCENE MODE: no media inputs, Remotion-only scene (text overlays, animations, etc.)
            mode = "scene"
            print(f"[NodeRunner] Editor Agent SCENE mode (no media inputs)")
        else:
            # DEFAULT MODE: has media inputs, backward-compatible monolithic generation
            print(f"[NodeRunner] Editor Agent DEFAULT mode: videos={len(ref_videos)}, images={len(ref_images)}")
        
        # Normalize audio to list
        if isinstance(raw_audio, str):
            raw_audio = [raw_audio] if raw_audio else []
        elif not isinstance(raw_audio, list):
            raw_audio = []

        # Build rich audio track metadata by tracing back to source nodes
        audio_tracks = []
        audio_source_map = {}  # url -> source_node_id
        for edge in edges:
            if edge.get("target") == node_id:
                target_handle = edge.get("targetHandle", "")
                handle_name = target_handle.split("|")[-1] if "|" in target_handle else target_handle
                if handle_name == "audio":
                    source_id = edge.get("source")
                    source_url = outputs.get(source_id, "")
                    if source_url:
                        audio_source_map[source_url] = source_id

        for url in raw_audio:
            source_id = audio_source_map.get(url)
            source_node = next((n for n in nodes if n["id"] == source_id), None) if source_id else None

            audio_type = "unknown"
            duration_seconds = 10
            description = ""

            if source_node:
                source_data = source_node.get("data", {})
                audio_type = source_data.get("audioType", "speech")
                duration_val = source_data.get("duration", None)
                if duration_val is not None:
                    if isinstance(duration_val, str):
                        duration_seconds = int(duration_val.replace("s", "").strip()) if duration_val.replace("s", "").strip().isdigit() else 10
                    else:
                        duration_seconds = int(duration_val)
                else:
                    # For speech, estimate from text length (~2.5 words/sec)
                    prompt_text = source_data.get("prompt", "")
                    word_count = len(prompt_text.split()) if prompt_text else 0
                    duration_seconds = max(3, round(word_count / 2.5)) if word_count > 0 else 10
                description = (source_data.get("prompt", "") or "")[:100]

            audio_tracks.append({
                "url": url,
                "type": audio_type,
                "duration_seconds": duration_seconds,
                "description": description or f"{audio_type} track",
            })

        print(f"[NodeRunner] Editor Agent (mode={mode}): instruction='{instruction[:50]}...', videos={len(ref_videos)}, images={len(ref_images)}, audio_tracks={len(audio_tracks)}")
        
        try:
            result = await self.editor_agent.edit_video(
                instruction=instruction,
                node_id=node_id,
                ref_videos=ref_videos,
                audio_tracks=audio_tracks,
                text_input=text_input,
                ref_images=ref_images,
                mode=mode,
                aspect_ratio=data.get("ratio", "9:16"),
                upstream_scenes=upstream_scenes if mode == "compositor" else None,
            )
            
            if result.get("success"):
                # For scene mode, include scene metadata in a JSON wrapper
                # so the frontend can distinguish scene vs compositor output
                output_data = result.get("code", "")
                
                if mode == "scene" and result.get("sceneConfig"):
                    import json
                    output_data = json.dumps({
                        "type": "scene",
                        "code": result.get("code", ""),
                        "sceneConfig": result.get("sceneConfig"),
                    })
                elif mode == "compositor":
                    import json
                    output_data = json.dumps({
                        "type": "compositor",
                        "code": result.get("code", ""),
                    })
                
                return {
                    "success": True,
                    "output": output_data,
                    "cost": result.get("cost", 0.0),
                    "tokens": result.get("tokens", 0),
                    "model": result.get("model", "claude-sonnet-4.6"),
                    "provider": result.get("provider", "Anthropic"),
                }
            else:
                return {
                    "success": False,
                    "error": result.get("error", "Code generation failed"),
                }
        except Exception as e:
            print(f"[NodeRunner] Editor Agent error: {e}")
            return {
                "success": False,
                "error": f"Editor Agent error: {str(e)}",
            }

    async def _run_media_upload_node(
        self,
        data: Dict[str, Any],
        inputs: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Media Upload node - outputs uploaded image or video."""
        file_url = data.get("file_url") or data.get("url") or data.get("output")
        media_type = data.get("mediaType", "image")
        
        if not file_url:
            return {
                "success": False,
                "error": "No media uploaded",
            }
        
        result = {
            "success": True,
            "output": file_url,
            "mediaType": media_type,
        }
        
        if media_type == "video":
            print(f"[NodeRunner] Extracting start/end frames from mediaUpload video...")
            start_frame = self._extract_video_frame(file_url, "start_frame")
            end_frame = self._extract_video_frame(file_url, "end_frame")
            
            if start_frame:
                result["start_frame"] = start_frame
            if end_frame:
                result["end_frame"] = end_frame
                
        return result

    # Legacy node (deprecated)
    async def _run_assistant_node(
        self,
        data: Dict[str, Any],
        inputs: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Legacy assistant node - redirects to vision node."""
        return await self._run_vision_node(data, inputs)

    async def _run_upscaler_node(
        self,
        data: Dict[str, Any],
        inputs: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Upscaler node - placeholder for image/video upscaling."""
        # TODO: Implement upscaling service
        return {
            "success": False,
            "error": "Upscaler node not yet implemented",
        }
