"""Node Runner Service - Executes workflow nodes based on their type."""

from typing import Dict, Any, List, Optional

from app.services.image_generator import ImageGenerator
from app.services.video_generator import VideoGenerator
from app.services.audio_generator import AudioGenerator
from app.services.editor_agent import EditorAgent
from app.services.chat_model_registry import CHAT_MODELS, get_chat_model_by_display_name, get_chat_model_by_openrouter_id
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
                source_output = None
                if source_id in outputs:
                    source_output = outputs[source_id]
                else:
                    # Try to get from node data directly (for text nodes, dragged assets, etc.)
                    source_node = next((n for n in nodes if n["id"] == source_id), None)
                    if source_node:
                        source_data = source_node.get("data", {})
                        if source_node.get("type") == "text":
                            source_output = source_data.get("text", "")
                            print(f"[NodeRunner] Fallback: Set input '{target_input_name}' from text node data")
                        elif "output" in source_data:
                            source_output = source_data.get("output")
                            print(f"[NodeRunner] Fallback: Set input '{target_input_name}' from source node data.output")

                if source_output is not None:
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
                    if target_input_name in [
                        "ref_videos",
                        "ref_images",
                        "audio",
                        "image",
                        "reference_image",
                        "reference_images",
                        "elements",
                        "elements_image",
                        "elements_video",
                        "elements_audio",
                    ]:
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
                    
                    print(f"[NodeRunner] Set input '{target_input_name}': {str(source_output)[:100]}")
        
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

        input_mode = str(data.get("inputMode", "auto") or "auto").strip().lower()
        if input_mode == "t2v":
            input_mode = "auto"
        if input_mode not in ("auto", "i2v", "reference", "elements", "v2v"):
            input_mode = "auto"

        # Get various image/video inputs
        start_image = inputs.get("start_image")
        end_image = inputs.get("end_image")
        raw_reference_images = inputs.get("reference_images") or inputs.get("reference_image")
        raw_elements = inputs.get("elements")  # legacy single-handle elements input
        raw_element_images = inputs.get("elements_image")
        raw_element_videos = inputs.get("elements_video")
        raw_element_voices = inputs.get("elements_audio")
        reference_video = inputs.get("reference_video")
        if isinstance(reference_video, list):
            reference_video = reference_video[0] if reference_video else None

        def _normalize_media_list(value: Any) -> List[str]:
            if isinstance(value, str):
                return [value] if value else []
            if isinstance(value, list):
                return [item for item in value if isinstance(item, str) and item]
            return []

        reference_images: List[str] = []
        reference_images = _normalize_media_list(raw_reference_images)

        element_images = _normalize_media_list(raw_element_images)
        element_videos = _normalize_media_list(raw_element_videos)
        element_voices = _normalize_media_list(raw_element_voices)
        # Backward compatibility with previous single-handle elements mode (image-only)
        if not element_images and not element_videos:
            legacy_elements = _normalize_media_list(raw_elements)
            if legacy_elements:
                element_images = legacy_elements

        audio_input = inputs.get("audio")
        if isinstance(audio_input, list):
            audio_input = audio_input[0] if audio_input else None
        
        # Build prompt
        has_any_element_media = bool(element_images or element_videos or element_voices)
        has_any_input_media = bool(start_image or reference_images or reference_video or has_any_element_media)
        if not prompt and not has_any_input_media:
            return {
                "success": False,
                "error": "No prompt or input media provided for video generation",
            }

        inferred_mode = "auto"
        if start_image:
            inferred_mode = "i2v"
        elif has_any_element_media:
            inferred_mode = "elements"
        elif reference_images:
            inferred_mode = "reference"
        elif reference_video:
            inferred_mode = "v2v"

        # Auto mode follows connected assets; with no assets it becomes text-only generation implicitly.
        if input_mode == "auto":
            input_mode = inferred_mode

        # Default prompt if only media is provided
        if not prompt:
            if input_mode == "i2v" and start_image:
                prompt = "Animate this image with natural motion"
            elif input_mode == "elements" and has_any_element_media:
                prompt = "Generate video with these visual elements"
            elif input_mode == "reference" and reference_images:
                prompt = "Generate video using these reference images"
            elif input_mode == "v2v" and reference_video:
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
        requested_entry = self._resolve_video_model_entry(model_str)
        if requested_entry:
            requested_caps = {str(c).lower() for c in requested_entry.get("capabilities", [])}
            if "native_audio_default" in requested_entry:
                requested_audio_default = bool(requested_entry.get("native_audio_default", False))
            else:
                requested_audio_default = "audio" in requested_caps
        else:
            requested_audio_default = False
        generate_audio_explicit = "generateAudio" in data and data.get("generateAudio") is not None
        generate_audio_val = data.get("generateAudio")
        if isinstance(generate_audio_val, str):
            generate_audio = generate_audio_val.strip().lower() in ("1", "true", "yes", "on")
        elif isinstance(generate_audio_val, bool):
            generate_audio = generate_audio_val
        else:
            generate_audio = requested_audio_default

        needs_i2v = input_mode == "i2v"
        needs_elements = input_mode == "elements"
        needs_reference = input_mode == "reference"
        needs_v2v = input_mode == "v2v"
        selected_model_str, generate_audio, model_warning, was_swapped = self._select_video_model_for_inputs(
            requested_model=model_str,
            has_start_image=needs_i2v,
            wants_elements=needs_elements,
            wants_reference=needs_reference,
            wants_v2v=needs_v2v,
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
                    "(e.g. pick an I2V model for Start Image mode, an elements-capable model for Elements mode, "
                    "a reference-capable model for Reference mode, "
                    "a V2V model for Extend mode, and an audio-capable model when Native Audio is enabled)."
                ),
            }
        model_str = selected_model_str

        selected_entry = self._resolve_video_model_entry(model_str)
        if selected_entry and not generate_audio_explicit:
            selected_caps = {str(c).lower() for c in selected_entry.get("capabilities", [])}
            if "native_audio_default" in selected_entry:
                generate_audio = bool(selected_entry.get("native_audio_default", False))
            else:
                generate_audio = "audio" in selected_caps

        def _as_int(value: Any, fallback: int) -> int:
            try:
                return int(value)
            except (TypeError, ValueError):
                return fallback

        frame_images_max = _as_int(selected_entry.get("frame_images_max", 2) if selected_entry else 2, 2)
        reference_min = _as_int(selected_entry.get("reference_images_min", 1) if selected_entry else 1, 1)
        reference_max = _as_int(selected_entry.get("reference_images_max", 1) if selected_entry else 1, 1)
        if reference_max < reference_min:
            reference_max = reference_min
        elements_min = _as_int(selected_entry.get("elements_min", 1) if selected_entry else 1, 1)
        elements_max = _as_int(selected_entry.get("elements_max", 1) if selected_entry else 1, 1)
        if elements_max < elements_min:
            elements_max = elements_min
        warning_notes: List[str] = []

        if selected_entry:
            valid_resolutions = [
                str(cfg.get("resolution"))
                for cfg in selected_entry.get("configs", [])
                if isinstance(cfg, dict) and isinstance(cfg.get("resolution"), str)
            ]
            valid_resolutions = list(dict.fromkeys(valid_resolutions))
            if valid_resolutions and resolution not in valid_resolutions:
                resolution = valid_resolutions[0]

        print(
            f"[NodeRunner] Generating video: prompt='{prompt[:50]}...', mode={input_mode}, model='{model_str}', "
            f"duration={duration}s, ratio={ratio}, resolution={resolution}, fast={use_fast_model}, generate_audio={generate_audio}"
        )
        print(
            f"[NodeRunner] Inputs: start_image={bool(start_image)}, end_image={bool(end_image)}, "
            f"elements_image={len(element_images)}, elements_video={len(element_videos)}, elements_audio={len(element_voices)}, "
            f"ref_images={len(reference_images)}, ref_video={bool(reference_video)}"
        )
        
        try:
            # Case 1: Start image mode (with optional end image if model supports interpolation)
            if input_mode == "i2v":
                if not start_image:
                    return {
                        "success": False,
                        "error": "Start Image is required for Start/End Image mode.",
                    }

                if end_image and frame_images_max >= 2:
                    print("[NodeRunner] Using interpolation (start + end image)")
                    result = await self.video_generator.generate_with_interpolation(
                        prompt=prompt,
                        first_frame_path=start_image,
                        last_frame_path=end_image,
                        duration=duration,
                        resolution=resolution,
                        aspect_ratio=ratio,
                        model_name=model_str,
                        generate_audio=generate_audio,
                    )
                else:
                    if end_image and frame_images_max < 2:
                        warning_notes.append(
                            f"Model '{selected_entry.get('name', model_str) if selected_entry else model_str}' "
                            "supports only one frame image; end frame was ignored."
                        )
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

            # Case 2: Elements mode (Kling VIDEO 3.0 Standard / Pro)
            elif input_mode == "elements":
                if not has_any_element_media:
                    return {
                        "success": False,
                        "error": "Elements mode requires at least one connected element image or element video.",
                    }

                if element_videos and (element_images or element_voices):
                    return {
                        "success": False,
                        "error": "Elements mode cannot combine element video with element image/audio connections.",
                    }

                if element_voices and not element_images:
                    return {
                        "success": False,
                        "error": "Element audio connections require at least one element image connection.",
                    }

                elements_count = len(element_videos) if element_videos else len(element_images)
                if elements_count < elements_min:
                    return {
                        "success": False,
                        "error": (
                            f"Selected model requires at least {elements_min} element image(s), "
                            f"but received {elements_count}."
                        ),
                    }

                if elements_count > elements_max:
                    warning_notes.append(
                        f"Selected model supports up to {elements_max} element image(s); "
                        f"using the first {elements_max}."
                    )
                    if element_videos:
                        element_videos = element_videos[:elements_max]
                    else:
                        element_images = element_images[:elements_max]

                print(
                    f"[NodeRunner] Using elements mode (images={len(element_images)}, "
                    f"videos={len(element_videos)}, voices={len(element_voices)})"
                )
                result = await self.video_generator.generate_with_elements(
                    prompt=prompt,
                    element_images=element_images,
                    element_videos=element_videos,
                    element_voices=element_voices,
                    duration=duration,
                    resolution=resolution,
                    aspect_ratio=ratio,
                    model_name=model_str,
                    generate_audio=generate_audio,
                )

            # Case 3: Reference images mode
            elif input_mode == "reference":
                if not reference_images:
                    return {
                        "success": False,
                        "error": "Reference Images mode requires at least one connected reference image.",
                    }

                if len(reference_images) < reference_min:
                    return {
                        "success": False,
                        "error": (
                            f"Selected model requires at least {reference_min} reference image(s), "
                            f"but received {len(reference_images)}."
                        ),
                    }

                if len(reference_images) > reference_max:
                    warning_notes.append(
                        f"Selected model supports up to {reference_max} reference image(s); "
                        f"using the first {reference_max}."
                    )
                    reference_images = reference_images[:reference_max]

                print(f"[NodeRunner] Using reference images (count={len(reference_images)})")
                result = await self.video_generator.generate_with_reference_images(
                    prompt=prompt,
                    reference_images=reference_images,
                    duration=duration,
                    resolution=resolution,
                    aspect_ratio=ratio,
                    model_name=model_str,
                    generate_audio=generate_audio,
                )

            # Case 4: Video extend/reference mode
            elif input_mode == "v2v":
                if not reference_video:
                    return {
                        "success": False,
                        "error": "Video Extend mode requires a connected reference video.",
                    }

                print("[NodeRunner] Using reference video / extension mode")
                result = await self.video_generator.extend_video(
                    original_video=reference_video,
                    prompt=prompt,
                    duration=duration,
                    resolution=resolution,
                    aspect_ratio=ratio,
                    model_name=model_str,
                    audio_url=audio_input,
                    generate_audio=generate_audio,
                )

            # Case 5: Auto/text generation (no connected media)
            else:
                print("[NodeRunner] Using auto text generation (no connected media)")
                if start_image:
                    # Guardrail for inconsistent saved node data.
                    warning_notes.append("Unexpected start image found in text mode; image-to-video was used.")
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
                else:
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
                warnings: List[str] = []
                if model_warning:
                    warnings.append(model_warning)
                warnings.extend(warning_notes)
                if warnings:
                    response["warning"] = " ".join(warnings)
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

    def _pick_best_video_model(
        self,
        need_i2v: bool,
        need_elements: bool,
        need_reference: bool,
        need_v2v: bool,
        need_audio: bool,
    ) -> Dict[str, Any]:
        """Pick a fallback video model that satisfies capability constraints."""
        def has_caps(entry: Dict[str, Any]) -> bool:
            caps = {c.lower() for c in entry.get("capabilities", [])}
            return (
                (not need_i2v or "i2v" in caps)
                and (not need_elements or "elements" in caps)
                and (not need_reference or "reference" in caps)
                and (not need_v2v or "v2v" in caps)
                and (not need_audio or "audio" in caps)
            )

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
        wants_elements: bool,
        wants_reference: bool,
        wants_v2v: bool,
        wants_native_audio: bool,
    ) -> tuple[str, bool, Optional[str], bool]:
        """Ensure selected model supports requested input/audio capability combo.

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
        need_elements = wants_elements
        need_reference = wants_reference
        need_v2v = wants_v2v
        need_audio = wants_native_audio

        supports_i2v = "i2v" in caps
        supports_elements = "elements" in caps
        supports_reference = "reference" in caps
        supports_v2v = "v2v" in caps
        supports_audio = "audio" in caps

        if (
            (need_i2v and not supports_i2v)
            or (need_elements and not supports_elements)
            or (need_reference and not supports_reference)
            or (need_v2v and not supports_v2v)
            or (need_audio and not supports_audio)
        ):
            reason_bits: List[str] = []
            if need_i2v and not supports_i2v:
                reason_bits.append("image-to-video")
            if need_elements and not supports_elements:
                reason_bits.append("elements")
            if need_reference and not supports_reference:
                reason_bits.append("reference images")
            if need_v2v and not supports_v2v:
                reason_bits.append("video extension/reference video")
            if need_audio and not supports_audio:
                reason_bits.append("native audio")
            reason = " + ".join(reason_bits) if reason_bits else "requested capabilities"

            replacement = self._pick_best_video_model(
                need_i2v=need_i2v,
                need_elements=need_elements,
                need_reference=need_reference,
                need_v2v=need_v2v,
                need_audio=need_audio,
            )
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
        """Media assistant node - processes text, images, video references, and audio."""
        import httpx
        import base64
        from openai import AsyncOpenAI
        from app.core.config import settings
        from app.services.storage_service import S3StorageService

        # Get instruction from node data
        raw_instruction = data.get("instruction", "")

        # Resolve references
        instruction = self._resolve_prompt_references(raw_instruction, nodes)

        # Get inputs
        text_input = inputs.get("text", "")
        ref_images = inputs.get("ref_images", [])
        ref_videos = inputs.get("ref_videos", [])
        ref_audio = inputs.get("audio", [])

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
        if isinstance(ref_audio, str):
            ref_audio = [ref_audio] if ref_audio else []

        selected_model = "Gemini 3.1 Pro Preview (High)"
        model_config = (
            get_chat_model_by_display_name(selected_model)
            or get_chat_model_by_openrouter_id(selected_model)
            or next((model for model in CHAT_MODELS if model.get("display_name") == selected_model), CHAT_MODELS[0])
        )
        model_name = str(model_config.get("openrouter_model") or "openai/gpt-5-mini")
        use_openrouter = bool(settings.openrouter_api_key)

        try:
            if use_openrouter:
                client = AsyncOpenAI(
                    base_url="https://openrouter.ai/api/v1",
                    api_key=settings.openrouter_api_key,
                    default_headers={
                        "HTTP-Referer": settings.api_base_url,
                        "X-Title": "Kureita",
                    },
                )
            else:
                client = AsyncOpenAI(api_key=settings.openai_api_key)
                model_name = "gpt-5-mini"

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

                if ref_videos:
                    print(f"[Vision] Converting {len(ref_videos)} video input(s) into start/end frames for multimodal analysis")
                    for video_url in ref_videos:
                        if not video_url:
                            continue

                        for frame_type in ("start_frame", "end_frame"):
                            try:
                                frame_data = self._extract_video_frame(video_url, frame_type)
                                if frame_data:
                                    user_content.append({
                                        "type": "image_url",
                                        "image_url": {"url": frame_data, "detail": "low"},
                                    })
                            except Exception as frame_err:
                                print(f"[Vision] Error extracting {frame_type} from video: {frame_err}")

                for audio_url in ref_audio:
                    if not audio_url:
                        continue
                    try:
                        safe_audio_url = audio_url
                        if S3StorageService.is_s3_url(audio_url):
                            safe_audio_url = S3StorageService().get_presigned_url(audio_url)

                        print(f"[Vision] Fetching audio: {safe_audio_url[:80]}...")
                        resp = await http_client.get(safe_audio_url, timeout=60.0)
                        if resp.status_code == 200:
                            content_type = resp.headers.get("content-type", "audio/mpeg").split(";")[0].strip()
                            audio_format = content_type.split("/")[-1].lower() if "/" in content_type else "mpeg"
                            b64 = base64.b64encode(resp.content).decode()
                            user_content.append({
                                "type": "input_audio",
                                "input_audio": {"data": b64, "format": audio_format},
                            })
                        else:
                            print(f"[Vision] Failed to fetch audio: {resp.status_code}")
                    except Exception as audio_err:
                        print(f"[Vision] Error fetching audio: {audio_err}")

            print(f"[Vision] Sending request to {model_name} ({len(user_content)} content parts)...")

            response = await client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": user_content}],
            )

            output_text = response.choices[0].message.content or ""
            print(f"[Vision] Response: {output_text[:100]}...")

            return {
                "success": True,
                "output": output_text,
                "model": model_name,
                "provider": "OpenRouter" if use_openrouter else "OpenAI",
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
        nodes: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Legacy assistant node - redirects to vision node."""
        return await self._run_vision_node(data, inputs, nodes or [])

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
