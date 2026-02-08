"""Editor Agent Service - Uses Gemini + Remotion for video editing."""

import asyncio
import os
import random
import time
import httpx
from pathlib import Path
from typing import Optional, List, Dict, Any

from google import genai
from google.genai import types

from app.core.config import settings


class EditorAgent:
    """AI-powered video editor using Gemini and Remotion."""

    def __init__(self):
        self.output_dir = Path("static/videos")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize Gemini client
        self.client = genai.Client(api_key=settings.gemini_api_key)
        
        # Remotion server URL
        self.remotion_url = settings.remotion_url
        
        print(f"[EditorAgent] Initialized with Remotion URL: {self.remotion_url}")

    async def edit_video(
        self,
        instruction: str,
        ref_videos: Optional[List[str]] = None,
        audio: Optional[str] = None,
        text_input: Optional[str] = None,
        ref_images: Optional[List[str]] = None,
    ) -> dict:
        """
        Edit video based on natural language instruction.
        
        Args:
            instruction: Natural language editing instruction
            ref_videos: List of video URLs to edit/stitch
            audio: Audio URL to add to video
            text_input: Additional text context
            ref_images: Reference images for overlays/backgrounds
            
        Returns:
            Dictionary with video URL and metadata
        """
        try:
            print(f"[EditorAgent] Starting edit with instruction: {instruction[:100]}...")
            
            # Normalize inputs
            ref_videos = ref_videos or []
            ref_images = ref_images or []
            if isinstance(ref_videos, str):
                ref_videos = [ref_videos]
            if isinstance(ref_images, str):
                ref_images = [ref_images]
            
            # Step 1: Analyze the instruction using Gemini
            editing_plan = await self._analyze_instruction(
                instruction=instruction,
                num_videos=len(ref_videos),
                has_audio=bool(audio),
                has_images=len(ref_images) > 0,
                text_context=text_input,
            )
            
            print(f"[EditorAgent] Editing plan: {editing_plan}")
            
            # Step 2: Generate Remotion composition code
            remotion_code = await self._generate_remotion_code(
                editing_plan=editing_plan,
                ref_videos=ref_videos,
                audio=audio,
                ref_images=ref_images,
            )
            
            print(f"[EditorAgent] Generated Remotion code ({len(remotion_code)} chars)")
            
            # Step 3: Render video using Remotion
            video_url = await self._render_with_remotion(
                remotion_code=remotion_code,
                ref_videos=ref_videos,
                audio=audio,
                ref_images=ref_images,
            )
            
            print(f"[EditorAgent] Video rendered: {video_url}")
            
            return {
                "success": True,
                "video_url": video_url,
                "instruction": instruction,
                "editing_plan": editing_plan,
            }
            
        except Exception as e:
            print(f"[EditorAgent] Error: {e}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": str(e),
            }

    async def _analyze_instruction(
        self,
        instruction: str,
        num_videos: int,
        has_audio: bool,
        has_images: bool,
        text_context: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Use Gemini to analyze the editing instruction and create a plan."""
        
        prompt = f"""You are a video editing AI assistant. Analyze this editing instruction and create a structured editing plan.

Instruction: {instruction}

Available inputs:
- Number of videos: {num_videos}
- Has audio: {has_audio}
- Has images: {has_images}
- Text context: {text_context or "None"}

Create a single JSON object (not an array) with these fields:
1. "task_type": One of ["stitch", "transition", "overlay", "effects", "composite"]
2. "duration": Total video duration in seconds (estimate based on inputs)
3. "fps": Frame rate (default 30)
4. "transitions": List of transition types between clips (e.g., "fade", "slide", "cut")
5. "effects": List of effects to apply (e.g., "reverse", "color_grade", "zoom", "pan")
6. "text_overlays": List of text overlays with timing and content
7. "audio_handling": How to handle audio ("add", "replace", "mix", "none")
8. "layout": For multi-video composites ("grid", "pip", "split", "sequence")

Return ONLY a single JSON object, no markdown or explanation."""

        try:
            response = self.client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.3,
                    response_mime_type="application/json",
                ),
            )
            
            import json
            plan = json.loads(response.text)
            
            # Handle case where Gemini returns a list instead of object
            if isinstance(plan, list):
                print(f"[EditorAgent] Warning: Gemini returned list, using first item")
                plan = plan[0] if plan else {}
            
            # Ensure it's a dict
            if not isinstance(plan, dict):
                print(f"[EditorAgent] Warning: Invalid plan type, using default")
                plan = {}
            
            # Validate required fields and set defaults
            plan.setdefault("task_type", "stitch")
            plan.setdefault("duration", num_videos * 4)
            plan.setdefault("fps", 30)
            plan.setdefault("transitions", ["fade"] * max(0, num_videos - 1))
            plan.setdefault("effects", [])
            plan.setdefault("text_overlays", [])
            plan.setdefault("audio_handling", "add" if has_audio else "none")
            plan.setdefault("layout", "sequence")
            
            return plan
            
        except Exception as e:
            print(f"[EditorAgent] Error analyzing instruction: {e}")
            # Return default plan
            return {
                "task_type": "stitch",
                "duration": num_videos * 4,
                "fps": 30,
                "transitions": ["fade"] * max(0, num_videos - 1),
                "effects": [],
                "text_overlays": [],
                "audio_handling": "add" if has_audio else "none",
                "layout": "sequence",
            }

    async def _generate_remotion_code(
        self,
        editing_plan: Dict[str, Any],
        ref_videos: List[str],
        audio: Optional[str],
        ref_images: List[str],
    ) -> str:
        """Generate Remotion composition code based on the editing plan."""
        
        # For now, create a simple composition that stitches videos
        # In the future, this could use Gemini to generate more complex code
        
        task_type = editing_plan.get("task_type", "stitch")
        duration = editing_plan.get("duration", 10)
        fps = editing_plan.get("fps", 30)
        transitions = editing_plan.get("transitions", [])
        
        # Simple template for video stitching
        code = f"""
import {{ AbsoluteFill, Sequence, OffthreadVideo, Audio, interpolate, useCurrentFrame }} from "remotion";

export const EditorComposition = () => {{
  const frame = useCurrentFrame();
  
  return (
    <AbsoluteFill style={{{{ backgroundColor: "black" }}}}>
"""
        
        # Add video sequences
        current_time = 0
        for i, video_url in enumerate(ref_videos):
            clip_duration = duration / len(ref_videos) if ref_videos else duration
            from_frame = int(current_time * fps)
            duration_frames = int(clip_duration * fps)
            
            # Add transition effect
            transition = transitions[i] if i < len(transitions) else "fade"
            
            code += f"""
      <Sequence from={{{from_frame}}} durationInFrames={{{duration_frames}}}>
        <AbsoluteFill>
          <OffthreadVideo
            src="{video_url}"
            style={{{{
              width: "100%",
              height: "100%",
              objectFit: "cover",
            }}}}
          />
        </AbsoluteFill>
      </Sequence>
"""
            current_time += clip_duration
        
        # Add audio if provided
        if audio:
            code += f"""
      <Audio src="{audio}" />
"""
        
        code += """
    </AbsoluteFill>
  );
};
"""
        
        return code

    async def _render_with_remotion(
        self,
        remotion_code: str,
        ref_videos: List[str],
        audio: Optional[str],
        ref_images: List[str],
    ) -> str:
        """Render video using Remotion server."""
        
        # For now, use a simplified approach:
        # Create scenes from the videos and call the existing Remotion server
        
        scenes = []
        current_time = 0.0
        clip_duration = 4.0  # Default 4 seconds per clip
        
        for i, video_url in enumerate(ref_videos):
            scenes.append({
                "id": i + 1,
                "start_time": current_time,
                "end_time": current_time + clip_duration,
                "description": f"Video clip {i + 1}",
                "visual_prompt": f"Clip {i + 1}",
                "voiceover_text": None,
                "on_screen_text": None,
                "asset_url": video_url,
            })
            current_time += clip_duration
        
        # If no videos, create a placeholder
        if not scenes:
            scenes.append({
                "id": 1,
                "start_time": 0.0,
                "end_time": 4.0,
                "description": "Placeholder",
                "visual_prompt": "Placeholder",
                "voiceover_text": None,
                "on_screen_text": "No video input provided",
                "asset_url": None,
            })
        
        # Prepare render request
        filename = f"edited_{int(time.time())}_{random.randint(1000, 9999)}.mp4"
        
        render_request = {
            "project_id": f"editor_{int(time.time())}",
            "scenes": scenes,
            "brand": {
                "name": "Editor Agent",
                "tagline": None,
                "primary_colors": [],
                "logo_url": None,
                "tone": "professional",
            },
            "story": {
                "title": "Edited Video",
                "call_to_action": "",
            },
            "output_filename": filename,
        }
        
        # Call Remotion server
        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                print(f"[EditorAgent] Calling Remotion server at {self.remotion_url}/render")
                response = await client.post(
                    f"{self.remotion_url}/render",
                    json=render_request,
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get("success"):
                        # Return the URL to the rendered video
                        video_url = f"{settings.api_base_url}/static/videos/{filename}"
                        return video_url
                    else:
                        raise Exception(f"Remotion render failed: {result.get('error')}")
                else:
                    raise Exception(f"Remotion server error: {response.status_code} - {response.text}")
                    
        except httpx.ConnectError:
            print(f"[EditorAgent] Cannot connect to Remotion server at {self.remotion_url}")
            print("[EditorAgent] Make sure Remotion server is running: cd apps/remotion && npm run server")
            raise Exception("Remotion server not available. Please start it with: cd apps/remotion && npm run server")
        except Exception as e:
            print(f"[EditorAgent] Remotion render error: {e}")
            raise
