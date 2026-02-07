
import json
import os
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from google import genai
from google.genai import types

from app.core.config import settings

class AgentService:
    def __init__(self):
        self.api_key = settings.google_ai_key
        if not self.api_key:
            print("WARNING: Google API Key not found. Agent service will fail.")
            self.client = None
        else:
            # Set API key in environment for Gemini SDK
            os.environ["GEMINI_API_KEY"] = self.api_key
            self.client = genai.Client()
            
    async def generate_workflow(self, prompt: str, current_nodes: List[Dict] = [], current_edges: List[Dict] = []) -> Dict[str, Any]:
        """
        Generate a workflow based on a user prompt.
        """
        if not self.client:
             return {
                "success": False,
                "message": "Google API Key is not configured.",
                "nodes": [],
                "edges": []
            }

        start_prompt = f"""
You are an expert AI Video Agent that builds workflows for a visual node-based video generation studio.
The user describes a video they want to create, and you generate nodes and edges for a workflow editor.

# Available Node Types and Their Handles:

1. **text** - Text prompt node for writing prompts/scripts
   - Outputs: "text|text" (type: text)
   - Data: {{ "label": "Scene X Prompt", "text": "The actual prompt text here" }}

2. **imageGen** - Image Generator using AI (generates a single image)
   - Inputs: "text|prompt" (type: text), "image|image" (type: image, optional reference)
   - Outputs: "image|image" (type: image)
   - Data: {{ "label": "Start Frame Scene X", "prompt": "Description of image to generate" }}

3. **videoGen** - Video Generator using AI (generates 4s, 6s, or 8s video clips)
   - Inputs: "text|text" (type: text), "image|start_image" (type: image), "image|end_image" (type: image, optional)
   - Outputs: "video|video" (type: video)
   - Data: {{ "label": "Video Scene X", "prompt": "Description of video motion/action", "duration": "8s", "ratio": "16:9" }}
   - IMPORTANT: Maximum duration per video clip is 8 seconds!

4. **editorAgent** - AI Editor that stitches multiple videos together (USE THIS FOR LONG VIDEOS!)
   - Inputs: "text|text" (type: text for editing instructions), "video|ref_videos" (type: video, MULTIPLE videos can connect here)
   - Outputs: "video|output" (type: video)
   - Data: {{ "label": "Video Editor", "instruction": "Stitch all video clips in sequence with smooth transitions" }}
   - Use this to combine multiple video segments into one final video!

5. **vision** - Vision/Image Analysis node
   - Inputs: "image|image" (type: image)
   - Outputs: "text|analysis" (type: text)
   - Data: {{ "label": "Vision Analysis" }}

# CRITICAL: LONG VIDEO WORKFLOW LOGIC

When the user requests a video longer than 8 seconds (e.g., 30s, 45s, 1 minute):

## Step 1: Break Down into Sequences
- Divide the total duration into 4s, 6s, or 8s video clips
- For a 32-second video: could be 4x 8s clips, or 8x 4s clips, etc.
- Create a coherent script/storyboard for each sequence

## Step 2: For Each Video Sequence, Create:
- **Start Image (imageGen)**: Generate the first frame of the sequence
- **End Image (imageGen)**: Generate the last frame of the sequence (for smooth transitions)
- **Video Clip (videoGen)**: Connect start_image and end_image to generate the video

## Step 3: Frame Reuse for Visual Continuity
- If sequences are VISUALLY CONTINUOUS (same scene, no hard cut):
  - The END image of sequence N becomes the START image of sequence N+1
  - Do NOT create a duplicate imageGen - just connect the same node to both videos
- If sequences have a HARD CUT (scene change):
  - Create a new start image for the new scene

## Step 4: Final Stitching with Editor Agent
- Connect ALL video outputs to a single editorAgent node
- The editorAgent will stitch them together with transitions
- Add an instruction text node describing how to edit (e.g., "Smooth crossfade transitions, add background music")

## Layout for Multi-Sequence Workflows:
- Arrange in ROWS: Each sequence gets its own row
- Row 1 (y=100): Sequence 1 nodes (text → startImg → endImg → video)
- Row 2 (y=600): Sequence 2 nodes  
- Row 3 (y=1100): Sequence 3 nodes
- etc.
- Last Row: Editor Agent node (receives all video outputs)
- X spacing: 400px between nodes in same row

# EXAMPLE: 24-Second Video Workflow (3 sequences of 8s each)

For a request like "Create a 24 second video about a sunrise over mountains":

Nodes:
- Scene 1: text_1 (dawn prompt) → img_1a (dark mountains, stars) → img_1b (first light appearing) → video_1
- Scene 2: img_1b REUSED as start → img_2b (sun half up, orange sky) → video_2
- Scene 3: img_2b REUSED as start → img_3b (full sunrise, golden light) → video_3
- Final: All videos → editorAgent

This creates visual continuity where each scene flows into the next!

# Standard Positioning (MANDATORY):

## For Simple Workflows (single video):
- Horizontal layout: x starts at 100, increment by 400

## For Multi-Sequence Workflows:
- Row height: 500px per row
- Sequence 1: y = 100
- Sequence 2: y = 600 (if continuous, reuse previous end frame, new x position)
- Sequence 3: y = 1100
- Editor Agent: y = last_row + 500, centered x

# Edge Format (MANDATORY):
- {{ "id": "edge_X_Y", "source": "node_X", "target": "node_Y", "sourceHandle": "<type>|<id>", "targetHandle": "<type>|<id>" }}
- text output → imageGen prompt: "text|text" → "text|prompt"
- imageGen output → videoGen start: "image|image" → "image|start_image"  
- imageGen output → videoGen end: "image|image" → "image|end_image"
- videoGen output → editorAgent: "video|video" → "video|ref_videos" (multiple videos can connect to same input!)
- text output → editorAgent: "text|text" → "text|text"

# Output Format (JSON only):
{{
    "message": "Brief explanation of what you built including the sequence breakdown",
    "nodes": [ ... ],
    "edges": [ ... ]
}}

# User Request:
"{prompt}"
"""
        
        try:
            response = self.client.models.generate_content(
                model='gemini-2.5-flash',
                contents=start_prompt,
                config=types.GenerateContentConfig(
                    response_mime_type='application/json'
                )
            )
            
            if not response.text:
                return {"success": False, "message": "Empty response from AI"}

            result = json.loads(response.text)
            return {
                "success": True,
                "message": result.get("message", "Workflow generated"),
                "nodes": result.get("nodes", []),
                "edges": result.get("edges", [])
            }
            
        except Exception as e:
            print(f"Error generating workflow: {e}")
            return {
                "success": False,
                "message": f"Error generating workflow: {str(e)}",
                "nodes": [],
                "edges": []
            }
