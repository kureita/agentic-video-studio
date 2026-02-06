"""Story Strategist Agent for creating content strategy documents."""

from typing import List, Optional
from pydantic import BaseModel
import os

try:
    from google import genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False


class StrategyMetrics(BaseModel):
    """Metrics analyzed for story strategy."""
    target_audience: str
    platform: str
    content_duration: int
    tone: str
    brand_alignment_score: float
    viral_potential_score: float


class StoryHook(BaseModel):
    """A hook for capturing audience attention."""
    type: str  # question, statistic, story, challenge, etc.
    content: str
    placement: str  # opening, middle, closing


class ContentBeat(BaseModel):
    """A structural beat in the content."""
    name: str
    description: str
    duration_seconds: int
    purpose: str


class StoryStrategy(BaseModel):
    """Complete story strategy document."""
    objective: str
    key_message: str
    emotional_arc: str
    hooks: List[StoryHook]
    content_structure: List[ContentBeat]
    call_to_action: str
    metrics: StrategyMetrics
    ai_recommendations: List[str]


class StoryStrategistAgent:
    """Agent that creates strategic content plans based on brand + trend + inspiration."""
    
    def __init__(self):
        self.api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        self.client = None
        
        if self.api_key and GENAI_AVAILABLE:
            self.client = genai.Client(api_key=self.api_key)
    
    async def generate_strategy(
        self,
        brand_name: str,
        brand_description: str,
        trend_query: str,
        trend_summary: str,
        inspiration_ideas: List[str],
        target_platform: str = "general",
        content_duration: int = 30,
        target_audience: str = "",
    ) -> StoryStrategy:
        """
        Generate a story strategy based on brand, trend, and inspiration.
        
        Args:
            brand_name: Name of the brand
            brand_description: Description of the brand
            trend_query: The trend being leveraged
            trend_summary: Summary of the trend research
            inspiration_ideas: Content ideas from inspiration brief
            target_platform: Target social platform
            content_duration: Target video duration in seconds
            target_audience: Target audience description
            
        Returns:
            StoryStrategy with hooks, beats, and recommendations
        """
        if not self.client:
            # Return mock strategy if no API key
            return self._generate_mock_strategy(
                brand_name, trend_query, target_platform, content_duration
            )
        
        try:
            prompt = self._build_strategy_prompt(
                brand_name, brand_description, trend_query, trend_summary,
                inspiration_ideas, target_platform, content_duration, target_audience
            )
            
            response = self.client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
            )
            
            # Parse the response and create strategy
            # In production, this would use structured output or JSON parsing
            return self._parse_strategy_response(
                response.text, brand_name, target_platform, content_duration
            )
            
        except Exception as e:
            print(f"Strategy generation failed: {e}")
            return self._generate_mock_strategy(
                brand_name, trend_query, target_platform, content_duration
            )
    
    def _build_strategy_prompt(
        self,
        brand_name: str,
        brand_description: str,
        trend_query: str,
        trend_summary: str,
        inspiration_ideas: List[str],
        target_platform: str,
        content_duration: int,
        target_audience: str,
    ) -> str:
        ideas_text = "\n".join(f"- {idea}" for idea in inspiration_ideas[:5])
        
        return f"""You are a viral content strategist. Create a detailed story strategy for a short-form video.

BRAND CONTEXT:
- Brand: {brand_name}
- Description: {brand_description}
- Target Audience: {target_audience or "General audience"}

TREND CONTEXT:
- Trending Topic: {trend_query}
- Trend Insights: {trend_summary}

CONTENT IDEAS:
{ideas_text}

CONSTRAINTS:
- Platform: {target_platform}
- Duration: {content_duration} seconds
- Must be authentic to brand
- Must leverage the trend naturally

Create a strategy with:
1. Clear objective and key message
2. Emotional arc (how viewers should feel)
3. 3 attention hooks (opening, middle, closing)
4. Content structure with timed beats
5. Strong call to action
6. AI recommendations for optimization

Be specific and actionable. Focus on what makes content go viral."""

    def _parse_strategy_response(
        self,
        response_text: str,
        brand_name: str,
        target_platform: str,
        content_duration: int,
    ) -> StoryStrategy:
        """Parse AI response into StoryStrategy. Simplified parsing for now."""
        # In production, use structured output or better parsing
        return StoryStrategy(
            objective=f"Create viral content for {brand_name} leveraging current trends",
            key_message="Extracted from AI response",
            emotional_arc="Curiosity → Engagement → Action",
            hooks=[
                StoryHook(type="question", content="Hook extracted from AI", placement="opening"),
                StoryHook(type="story", content="Story hook from AI", placement="middle"),
                StoryHook(type="challenge", content="CTA hook from AI", placement="closing"),
            ],
            content_structure=[
                ContentBeat(name="Hook", description="Attention grabber", duration_seconds=3, purpose="Capture attention"),
                ContentBeat(name="Problem", description="Relatable challenge", duration_seconds=5, purpose="Build connection"),
                ContentBeat(name="Solution", description="Brand's approach", duration_seconds=12, purpose="Deliver value"),
                ContentBeat(name="Proof", description="Results/testimonial", duration_seconds=7, purpose="Build trust"),
                ContentBeat(name="CTA", description="Call to action", duration_seconds=3, purpose="Drive action"),
            ],
            call_to_action="Follow for more",
            metrics=StrategyMetrics(
                target_audience="General",
                platform=target_platform,
                content_duration=content_duration,
                tone="engaging",
                brand_alignment_score=0.85,
                viral_potential_score=0.75,
            ),
            ai_recommendations=[
                "Start with a pattern interrupt",
                "Use trending audio if available",
                "Add captions for accessibility",
                "Post during peak hours",
            ]
        )
    
    def _generate_mock_strategy(
        self,
        brand_name: str,
        trend_query: str,
        target_platform: str,
        content_duration: int,
    ) -> StoryStrategy:
        """Generate mock strategy when no API key is available."""
        # Calculate beat durations based on content duration
        hook_duration = max(2, content_duration // 10)
        main_duration = content_duration - (hook_duration * 3)
        
        return StoryStrategy(
            objective=f"Create engaging content for {brand_name} inspired by '{trend_query}'",
            key_message=f"Discover how {brand_name} is innovating",
            emotional_arc="Curiosity → Understanding → Inspiration → Action",
            hooks=[
                StoryHook(
                    type="question",
                    content=f"What if {trend_query} was the key to success?",
                    placement="opening"
                ),
                StoryHook(
                    type="insight",
                    content=f"Here's what most people miss about {trend_query}",
                    placement="middle"
                ),
                StoryHook(
                    type="challenge",
                    content=f"Ready to try this yourself?",
                    placement="closing"
                ),
            ],
            content_structure=[
                ContentBeat(
                    name="Hook",
                    description="Pattern interrupt to stop the scroll",
                    duration_seconds=hook_duration,
                    purpose="Capture attention in first 2 seconds"
                ),
                ContentBeat(
                    name="Context",
                    description="Set up the problem or opportunity",
                    duration_seconds=main_duration // 4,
                    purpose="Create relevance"
                ),
                ContentBeat(
                    name="Value",
                    description="Deliver the main insight or story",
                    duration_seconds=main_duration // 2,
                    purpose="Provide authentic value"
                ),
                ContentBeat(
                    name="Proof",
                    description="Show results or social proof",
                    duration_seconds=main_duration // 4,
                    purpose="Build credibility"
                ),
                ContentBeat(
                    name="CTA",
                    description="Clear next step for viewers",
                    duration_seconds=hook_duration,
                    purpose="Drive engagement/conversion"
                ),
            ],
            call_to_action=f"Follow @{brand_name.lower().replace(' ', '')} for more",
            metrics=StrategyMetrics(
                target_audience="Social media users interested in " + trend_query,
                platform=target_platform,
                content_duration=content_duration,
                tone="authentic and engaging",
                brand_alignment_score=0.8,
                viral_potential_score=0.7,
            ),
            ai_recommendations=[
                "Use trending audio to boost discoverability",
                "Add on-screen text for silent viewing",
                "Include a hook in the first 1-2 seconds",
                "End with a question to encourage comments",
                f"Optimal posting time: Peak hours for {target_platform}",
            ]
        )
