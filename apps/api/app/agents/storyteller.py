"""Storyteller Agent - Creates compelling video narratives."""

import json
from typing import Optional

from openai import AsyncOpenAI

from app.core.config import settings
from app.models.project import Story, BrandProfile, VideoStyle


class Storyteller:
    """Creates compelling story concepts for promotional videos."""

    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = "gpt-4o"

    async def create_story(
        self,
        brand_profile: BrandProfile,
        video_duration: int,
        style: VideoStyle,
        target_audience: Optional[str] = None,
        additional_notes: Optional[str] = None,
    ) -> Story:
        """
        Create a story concept for the promotional video.
        
        Args:
            brand_profile: Extracted brand information
            video_duration: Target video length in seconds
            style: Visual style for the video
            target_audience: Description of target audience
            additional_notes: Any additional context from the user
            
        Returns:
            Story with narrative structure
        """
        system_prompt = """You are a creative director specializing in promotional video storytelling.
Create compelling, emotionally resonant story concepts for brand videos.

Return a JSON object with:
{
    "title": "Short, catchy story title (3-5 words)",
    "synopsis": "2-3 sentence overview of the video narrative",
    "key_messages": ["Message 1", "Message 2", "Message 3"],
    "target_emotion": "The primary emotion to evoke (e.g., excitement, trust, inspiration)",
    "call_to_action": "Clear CTA for the video ending"
}

Focus on:
- Emotional connection with the audience
- Clear value proposition
- Memorable messaging
- Strong opening hook
- Compelling call to action

CRITICAL INSTRUCTION:
You will be provided with specific STRATEGY, TREND RESEARCH, and INSPIRATION data in the "Additional Notes" or "Context" section.
You MUST incorporate these elements into the story concept.
- If a trend is provided, the story should leverage that trend explicitly.
- If a strategy objective is provided, the story must fulfill it.
- If viral hooks are provided, include them in the concept.
- Mention the brand name and USPs effectively."""

        user_prompt = f"""Create a story concept for a {video_duration}-second promotional video.

Brand Information:
- Name: {brand_profile.name}
- Tagline: {brand_profile.tagline or 'N/A'}
- Description: {brand_profile.description or 'N/A'}
- Tone: {brand_profile.tone}
- Products/Services: {', '.join(brand_profile.products) if brand_profile.products else 'N/A'}
- USPs: {', '.join(brand_profile.unique_selling_points) if brand_profile.unique_selling_points else 'N/A'}

Video Style: {style.value}
Target Audience: {target_audience or 'General audience'}
Video Style: {style.value}
Target Audience: {target_audience or 'General audience'}

CONTEXT & STRATEGY (IMPORTANT):
{additional_notes or 'None'}

Create a compelling story that showcases the brand's value proposition in {video_duration} seconds.
Ensure the story explicitly references the trends and strategy points mentioned in the Context."""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.7,
            )

            result = json.loads(response.choices[0].message.content)
            
            return Story(
                title=result.get("title", "Brand Story"),
                synopsis=result.get("synopsis", ""),
                key_messages=result.get("key_messages", []),
                target_emotion=result.get("target_emotion", "trust"),
                call_to_action=result.get("call_to_action", "Learn more"),
            )

        except Exception as e:
            print(f"Story creation error: {e}")
            return Story(
                title=f"{brand_profile.name} Story",
                synopsis=f"Discover {brand_profile.name} and what makes us unique.",
                key_messages=brand_profile.unique_selling_points[:3] if brand_profile.unique_selling_points else ["Quality", "Innovation", "Trust"],
                target_emotion="trust",
                call_to_action="Visit our website",
            )

