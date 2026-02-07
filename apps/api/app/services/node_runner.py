"""Node Runner Service - Executes workflow nodes based on their type."""

from typing import Dict, Any, List, Optional

from app.services.image_generator import ImageGenerator
from app.services.video_generator import VideoGenerator


class NodeRunner:
    """Runs individual workflow nodes by type."""

    def __init__(self):
        self.image_generator = ImageGenerator()
        self.video_generator = VideoGenerator()

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
            
            elif node_type == "videoGen":
                return await self._run_video_gen_node(node_data, inputs)
            
            elif node_type == "vision" or node_type == "assistant":
                return await self._run_vision_node(node_data, inputs)
            
            elif node_type == "editorAgent":
                return await self._run_editor_agent_node(node_data, inputs)
            
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
        """
        inputs = {}
        
        for edge in edges:
            if edge.get("target") == node_id:
                source_id = edge.get("source")
                source_handle = edge.get("sourceHandle", "")
                target_handle = edge.get("targetHandle", "")
                
                # Extract the handle name (format: "type|name")
                target_input_name = target_handle.split("|")[-1] if "|" in target_handle else target_handle
                
                # Get output from source node
                if source_id in outputs:
                    source_output = outputs[source_id]
                    inputs[target_input_name] = source_output
                else:
                    # Try to get from node data directly (for text nodes, etc.)
                    source_node = next((n for n in nodes if n["id"] == source_id), None)
                    if source_node:
                        source_data = source_node.get("data", {})
                        # For text nodes, the output is the text field
                        if source_node.get("type") == "text":
                            inputs[target_input_name] = source_data.get("text", "")
        
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
        
        if not prompt and not reference_image:
            return {
                "success": False,
                "error": "No prompt or reference image provided",
            }
            
        # If we have an image but no prompt, provide a default prompt
        if reference_image and not prompt:
            prompt = "Variation of this image"
        
        # Get generation parameters
        model = data.get("model", "Google Nano Banana")
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

    async def _run_video_gen_node(
        self,
        data: Dict[str, Any],
        inputs: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Generate video using the VideoGenerator service."""
        # Get prompt from text input
        prompt = inputs.get("text") or inputs.get("prompt") or data.get("prompt", "")
        
        # Get various image/video inputs
        start_image = inputs.get("start_image")
        end_image = inputs.get("end_image")
        reference_images = inputs.get("reference_images")
        reference_video = inputs.get("reference_video")
        
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
        
        print(f"[NodeRunner] Generating video: prompt='{prompt[:50]}...', duration={duration}s, ratio={ratio}, resolution={resolution}")
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
                    use_fast_model=True,  # Use Veo 3.1 Fast by default
                    resolution=resolution,
                    aspect_ratio=ratio,
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
    ) -> Dict[str, Any]:
        """Vision node - uses Gemini model as a chat model to process text, images, and videos."""
        import httpx
        from google import genai
        from google.genai import types
        from app.core.config import settings
        
        # Get instruction from node data
        instruction = data.get("instruction", "")
        
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
            # Initialize Gemini client
            client = genai.Client(api_key=settings.gemini_api_key)
            
            # Build content list - use strings for text, Part for binary
            contents = []
            
            # Add instruction as text
            if text_input:
                contents.append(f"Context: {text_input}\n\nInstruction: {instruction}")
            else:
                contents.append(instruction)
            
            # Add images
            async with httpx.AsyncClient() as http_client:
                for img_url in ref_images:
                    if img_url:
                        try:
                            print(f"[Vision] Fetching image: {img_url[:80]}...")
                            response = await http_client.get(img_url, timeout=30.0)
                            if response.status_code == 200:
                                content_type = response.headers.get("content-type", "image/jpeg")
                                mime_type = content_type.split(";")[0].strip()
                                # Ensure valid mime type
                                if not mime_type.startswith("image/"):
                                    mime_type = "image/jpeg"
                                contents.append(types.Part.from_bytes(data=response.content, mime_type=mime_type))
                            else:
                                print(f"[Vision] Failed to fetch image: {response.status_code}")
                        except Exception as e:
                            print(f"[Vision] Error fetching image: {e}")
                
                # Add videos (Gemini supports video frames)
                for vid_url in ref_videos:
                    if vid_url:
                        try:
                            print(f"[Vision] Fetching video: {vid_url[:80]}...")
                            response = await http_client.get(vid_url, timeout=60.0)
                            if response.status_code == 200:
                                content_type = response.headers.get("content-type", "video/mp4")
                                mime_type = content_type.split(";")[0].strip()
                                if not mime_type.startswith("video/"):
                                    mime_type = "video/mp4"
                                contents.append(types.Part.from_bytes(data=response.content, mime_type=mime_type))
                            else:
                                print(f"[Vision] Failed to fetch video: {response.status_code}")
                        except Exception as e:
                            print(f"[Vision] Error fetching video: {e}")
            
            print(f"[Vision] Sending request with {len(contents)} parts to Gemini...")
            
            # Call Gemini 2.0 Flash (multimodal)
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=contents,
                config=types.GenerateContentConfig(
                    temperature=0.7,
                    max_output_tokens=2048,
                ),
            )
            
            output_text = response.text
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
    ) -> Dict[str, Any]:
        """Editor Agent node - uses Remotion to stitch videos and perform editing tasks."""
        # Get instruction from node data
        instruction = data.get("instruction", "")
        
        # Get inputs
        text_input = inputs.get("text", "")
        ref_images = inputs.get("ref_images", [])
        ref_videos = inputs.get("ref_videos", [])
        
        if not instruction:
            return {
                "success": False,
                "error": "No instruction provided",
            }
        
        # TODO: Implement Remotion integration
        # This should:
        # 1. Parse the instruction to understand the editing task
        # 2. Use Remotion to stitch videos, add transitions, effects, etc.
        # 3. Return the edited video URL
        
        return {
            "success": False,
            "error": "Editor Agent node not yet implemented",
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
