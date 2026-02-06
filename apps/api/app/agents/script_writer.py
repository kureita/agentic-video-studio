"""Script Writer Agent - Creates detailed video scripts with scene breakdowns."""

import json
from typing import List

from openai import AsyncOpenAI

from app.core.config import settings
from app.models.project import Story, BrandProfile, VideoStyle, Scene


class ScriptWriter:
    """Creates detailed scripts and scene breakdowns for promotional videos."""

    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = "gpt-4o"

    async def create_script(
        self,
        story: Story,
        brand_profile: BrandProfile,
        video_duration: int,

        style: VideoStyle,
        additional_context: str = None,
    ) -> List[Scene]:
        """
        Create a detailed script with scene breakdowns.
        
        Args:
            story: The story concept
            brand_profile: Brand information
            video_duration: Target duration in seconds
            style: Visual style
            
        Returns:
            List of Scene objects with timing and content
        """
        # Calculate number of scenes based on duration
        num_scenes = max(3, video_duration // 8)  # ~8 seconds per scene
        
        system_prompt = f"""You are a professional video scriptwriter.
Create a detailed scene-by-scene breakdown for a {video_duration}-second promotional video.

Return a JSON object with a "scenes" array. Each scene should have:
{{
    "id": 1,
    "start_time": 0.0,
    "end_time": 5.0,
    "description": "Brief description of what happens visually",
    "visual_prompt": "Detailed prompt for AI video generation (Veo 3.1) - be specific about shots, lighting, mood",
    "voiceover_text": "Exact narration text for this scene (or null if no voiceover)",
    "on_screen_text": "Any text overlays (or null if none)"
}}

Guidelines:
- Start with a hook in the first 3 seconds
- Build emotional connection in the middle
- End with clear CTA
- CRITICAL: VISUAL CONSISTENCY & SUBJECT CONTINUITY
  - IDENTIFY THE MAIN SUBJECT (e.g., "The Penguin", "The Athlete").
  - The Main Subject MUST appear in scenes unless explicitly stated otherwise.
  - DO NOT change the subject arbitrarily (e.g., if the story is about a penguin, do not switch to a "generic client" in an office).
  - If the location changes, show the Main Subject ENTERING or EXISTING in the new location.
  - Example Bad: "Cut to a doctor in an office." (Where is the penguin?)
  - Example Good: "Cut to the office where the Penguin sits across from the doctor."
- CRITICAL: Visual prompts must be VERY DETAILED and BRAND-SPECIFIC. 
  - ALWAYS include the Brand Name and Product logic in the prompt.
  - Describe the lighting, color palette (using brand colors), camera angle, and movement.
  - State the narrative purpose of the shot (e.g., "Showcasing speed", "Evoking trust").
  - Example: "Cinematic medium shot of [Brand Name] running shoes on a wet track, golden hour lighting, slow motion water splashes, conveying durability and determination."
- NARRATIVE CONTINUITY:
  - Treat scenes as sequential chapters of ONE story.
  - Ensure visual flow: if Scene 1 is in a kitchen, Scene 2 should likely be in the same kitchen (unless a cut is needed).
  - Use transitional phrases in descriptions (e.g., "Continuing from previous shot...", "Cut to reaction shot...").
- Keep voiceover concise and impactful
- Total duration must equal {video_duration} seconds
- Create exactly {num_scenes} scenes"""

        user_prompt = f"""Create a script for this promotional video:

Story Title: {story.title}
Synopsis: {story.synopsis}
Key Messages: {', '.join(story.key_messages)}
Target Emotion: {story.target_emotion}
Call to Action: {story.call_to_action}

Brand: {brand_profile.name}
Tone: {brand_profile.tone}
Style: {style.value}

Duration: {video_duration} seconds
Number of Scenes: {num_scenes}

Create a compelling, visually rich script that tells this story effectively.

CONTEXT & STRATEGY:
{additional_context or 'None'}

Ensure the visual prompts and script align with the context provided."""

        # Iterative Generation for strict continuity
        scenes = []
        previous_context = "Start of video."
        current_time = 0
        scene_duration = video_duration / num_scenes
        
        for i in range(num_scenes):
            is_last = (i == num_scenes - 1)
            
            scene_system_prompt = f"""You are a professional video scriptwriter.
Create Scene {i+1} of {num_scenes} for a promotional video.

STORY CONTEXT:
Title: {story.title}
Synopsis: {story.synopsis}
Brand: {brand_profile.name} (Tone: {brand_profile.tone})

PREVIOUS SCENE CONTEXT:
{previous_context}

CRITICAL INSTRUCTIONS:
1. MAINTAIN SUBJECT CONTINUITY: If the previous scene had a specific subject (e.g., "The Penguin"), this scene MUST continue with them unless a clear transition occurs.
2. VISUAL FLOW: Describe how the visual connects to the previous shot.
3. BRAND SPECIFICITY: Include {brand_profile.name} elements/colors naturally.

Return JSON for THIS SCENE ONLY:
{{
    "visual_prompt": "Detailed AI prompt including subject, action, lighting, brand context.",
    "description": "Brief narrative description.",
    "voiceover_text": "Narration (optional).",
    "on_screen_text": "Overlay text (optional)."
}}"""

            try:
                scene_response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "system", "content": scene_system_prompt}],
                    response_format={"type": "json_object"},
                    temperature=0.7,
                )
                
                scene_data = json.loads(scene_response.choices[0].message.content)
                
                # Update context for next iteration
                previous_context = f"Scene {i+1}: {scene_data.get('description')} (Visual: {scene_data.get('visual_prompt')})"
                
                scenes.append(Scene(
                    id=i + 1,
                    start_time=current_time,
                    end_time=current_time + scene_duration,
                    description=scene_data.get("description", ""),
                    visual_prompt=scene_data.get("visual_prompt", ""),
                    voiceover_text=scene_data.get("voiceover_text"),
                    on_screen_text=scene_data.get("on_screen_text"),
                ))
                
                current_time += scene_duration
                
            except Exception as e:
                print(f"Error generating scene {i+1}: {e}")
                # Fallback
                scenes.append(Scene(
                    id=i + 1,
                    start_time=current_time,
                    end_time=current_time + scene_duration,
                    description=f"Scene {i+1}",
                    visual_prompt=f"Cinematic shot for {brand_profile.name}, continuing story.",
                ))
                current_time += scene_duration

        return scenes



