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
- Visual prompts should be detailed: include camera angles, lighting, mood, movement
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

Create a compelling, visually rich script that tells this story effectively."""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.6,
            )

            result = json.loads(response.choices[0].message.content)
            scenes_data = result.get("scenes", [])
            
            scenes = []
            for scene_data in scenes_data:
                scenes.append(Scene(
                    id=scene_data.get("id", len(scenes) + 1),
                    start_time=scene_data.get("start_time", 0),
                    end_time=scene_data.get("end_time", 0),
                    description=scene_data.get("description", ""),
                    visual_prompt=scene_data.get("visual_prompt", ""),
                    voiceover_text=scene_data.get("voiceover_text"),
                    on_screen_text=scene_data.get("on_screen_text"),
                ))
            
            return scenes

        except Exception as e:
            print(f"Script creation error: {e}")
            # Return basic 3-scene structure on error
            scene_duration = video_duration / 3
            return [
                Scene(
                    id=1,
                    start_time=0,
                    end_time=scene_duration,
                    description="Opening hook",
                    visual_prompt=f"Cinematic opening shot, {style.value} style, professional lighting",
                ),
                Scene(
                    id=2,
                    start_time=scene_duration,
                    end_time=scene_duration * 2,
                    description="Main message",
                    visual_prompt=f"Product showcase, {style.value} style, dynamic camera movement",
                    voiceover_text=story.synopsis,
                ),
                Scene(
                    id=3,
                    start_time=scene_duration * 2,
                    end_time=video_duration,
                    description="Call to action",
                    visual_prompt=f"Brand logo reveal, {style.value} style",
                    on_screen_text=story.call_to_action,
                ),
            ]

