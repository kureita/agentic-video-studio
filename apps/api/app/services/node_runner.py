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
                return await self._run_image_gen_node(node_data, inputs)
            
            elif node_type == "videoGen":
                return await self._run_video_gen_node(node_data, inputs)
            
            elif node_type == "assistant":
                return await self._run_assistant_node(node_data, inputs)
            
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

    async def _run_image_gen_node(
        self,
        data: Dict[str, Any],
        inputs: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Generate image using the ImageGenerator service."""
        # Get prompt from input or node data
        prompt = inputs.get("prompt") or data.get("prompt", "")
        
        if not prompt:
            return {
                "success": False,
                "error": "No prompt provided for image generation",
            }
        
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
        
        print(f"[NodeRunner] Generating image: prompt='{prompt[:50]}...', model={model}, ratio={ratio}")
        
        # Generate image(s)
        # For now, generate one image (we could extend to generate multiple)
        result = await self.image_generator.generate_image(
            prompt=prompt,
            aspect_ratio=ratio,
            style=style,
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

    async def _run_video_gen_node(
        self,
        data: Dict[str, Any],
        inputs: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Generate video using the VideoGenerator service."""
        # Get prompt from text input
        prompt = inputs.get("text") or inputs.get("prompt") or data.get("prompt", "")
        
        # Get reference image if provided
        image_url = inputs.get("image") or data.get("image")
        
        if not prompt and not image_url:
            return {
                "success": False,
                "error": "No prompt or image provided for video generation",
            }
        
        # Build prompt
        full_prompt = prompt if prompt else "Animate this image with natural motion"
        
        # Get generation parameters
        duration_str = data.get("duration", "5s")
        duration = int(duration_str.replace("s", "")) if isinstance(duration_str, str) else 5
        ratio = data.get("ratio", "1:1")
        
        print(f"[NodeRunner] Generating video: prompt='{full_prompt[:50]}...', duration={duration}s, ratio={ratio}")
        
        # Generate video (Veo supports 4, 6, 8 second durations)
        if duration <= 4:
            duration = 4
        elif duration <= 6:
            duration = 6
        else:
            duration = 8
        
        result = await self.video_generator.generate_clip(
            prompt=full_prompt,
            duration=duration,
            use_fast_model=True,  # Use fast model for workflow execution
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

    async def _run_assistant_node(
        self,
        data: Dict[str, Any],
        inputs: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Assistant node - placeholder for LLM-based processing."""
        # TODO: Implement LLM-based text processing
        return {
            "success": False,
            "error": "Assistant node not yet implemented",
        }

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
