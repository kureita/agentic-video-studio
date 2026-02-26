"""Node Runner Service - Executes workflow nodes based on their type."""

from typing import Dict, Any, List, Optional

from app.services.image_generator import ImageGenerator
from app.services.video_generator import VideoGenerator
from app.services.audio_generator import AudioGenerator
from app.services.editor_agent import EditorAgent


class NodeRunner:
    """Runs individual workflow nodes by type."""

    def __init__(self):
        self.image_generator = ImageGenerator()
        self.video_generator = VideoGenerator()
        self.audio_generator = AudioGenerator()
        self.editor_agent = EditorAgent()

    async def run_node(
        self,
        node: Dict[str, Any],
        nodes: List[Dict[str, Any]],
        edges: List[Dict[str, Any]],
        outputs: Dict[str, Any],
        input_overrides: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Run a single node and return the result.
        
        Args:
            node: The node object to run
            nodes: All nodes in the workflow
            edges: All edges in the workflow  
            outputs: Existing outputs from previous nodes
            input_overrides: Optional overrides for node inputs
            
        Returns:
            Dict with success, output, and optional error
        """
        node_type = node.get("type")
        node_id = node.get("id")
        node_data = node.get("data", {})
        
        # Resolve inputs from connected nodes
        inputs = self._resolve_inputs(node_id, nodes, edges, outputs)
        
        # Apply overrides if provided
        if input_overrides:
            inputs.update(input_overrides)
        
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
                return await self._run_video_gen_node(node_data, inputs, nodes)
            
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
                
                print(f"[NodeRunner] Extracted target_input_name: {target_input_name}")
                
                # Get output from source node
                if source_id in outputs:
                    source_output = outputs[source_id]
                    
                    # For inputs that can accept multiple connections, collect into list
                    if target_input_name in ["ref_videos", "ref_images"]:
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
        # Favor typed prompt if it exists, allowing for template usage
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
        model = data.get("model", "FLUX Schnell")
        ratio = data.get("ratio", "1:1")
        count = data.get("count", 1)
        
        # Map aspect ratio
        aspect_ratio = ratio.replace(":", "/")
        
        # Determine style based on model
        style = "realistic"
        if "Stable" in model:
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
        """Generate audio using the AudioGenerator service."""
        # Get text from node data (typed) or inputs (connected)
        raw_text = data.get("prompt", "")
        if not raw_text:
            raw_text = inputs.get("prompt", "")
            
        # Resolve references (e.g. @Text #1)
        text = self._resolve_prompt_references(raw_text, nodes)
        
        if not text or not text.strip():
            return {
                "success": False,
                "error": "No text provided for speech generation",
            }
        
        # Get voice parameter
        voice = data.get("voice", "Rachel")
        
        print(f"[NodeRunner] Generating audio: text='{text[:50]}...', voice={voice}")
        
        try:
            result = await self.audio_generator.generate_speech(
                text=text,
                voice=voice,
            )
            
            if result.get("success"):
                return {
                    "success": True,
                    "output": result.get("audio_url"),
                }
            else:
                return {
                    "success": False,
                    "error": result.get("error", "Audio generation failed"),
                }
        except Exception as e:
            return {
                "success": False,
                "error": f"Audio Generator Error: {str(e)}",
            }

    async def _run_video_gen_node(
        self,
        data: Dict[str, Any],
        inputs: Dict[str, Any],
        nodes: List[Dict[str, Any]],
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
        
        # Get generation parameters (duration: "4s"|"6s"|"8s" from UI, or int)
        duration_val = data.get("duration", "4s")
        if isinstance(duration_val, int):
            duration = duration_val
        elif isinstance(duration_val, str):
            duration = int(duration_val.replace("s", "").strip()) if duration_val.replace("s", "").strip().isdigit() else 4
        else:
            duration = 4
        ratio = data.get("ratio", "16:9")
        resolution = data.get("resolution", "720p")
        # Determine model
        model_str = data.get("model", "Veo 3.1 Fast")
        use_fast_model = "Fast" in model_str

        if resolution not in ("720p", "1080p"):
            resolution = "720p"

        # Validate duration for Veo 3.1 (only supports 4, 6, or 8 seconds)
        if duration not in [4, 6, 8]:
            if duration <= 4:
                duration = 4
            elif duration <= 6:
                duration = 6
            else:
                duration = 8
        
        print(f"[NodeRunner] Generating video: prompt='{prompt[:50]}...', duration={duration}s, ratio={ratio}, resolution={resolution}, fast={use_fast_model}")
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
                    model_name=model_str,
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
                )
            
            if result.get("success"):
                return {
                    "success": True,
                    "output": result.get("video_url"),
                }
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
        audio = inputs.get("audio")
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
        
        # For default mode, still require media inputs
        if mode is None and not ref_videos and not ref_images:
            return {
                "success": False,
                "error": "No video or image inputs provided. Connect videos or images to edit.",
            }
        
        print(f"[NodeRunner] Editor Agent (mode={mode}): instruction='{instruction[:50]}...', videos={len(ref_videos)}, images={len(ref_images)}, has_audio={bool(audio)}")
        
        try:
            result = await self.editor_agent.edit_video(
                instruction=instruction,
                node_id=node_id,
                ref_videos=ref_videos,
                audio=audio,
                text_input=text_input,
                ref_images=ref_images,
                mode=mode,
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
        
        return {
            "success": True,
            "output": file_url,
            "mediaType": media_type,
        }

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
