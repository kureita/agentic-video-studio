"""Story strategy API endpoints."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional

from app.agents.story_strategist import StoryStrategistAgent, StoryStrategy

router = APIRouter(prefix="/strategy", tags=["strategy"])


class StrategyRequest(BaseModel):
    """Request for generating story strategy."""
    brand_name: str
    brand_description: str = ""
    trend_query: str
    trend_summary: str = ""
    inspiration_ideas: List[str] = []
    target_platform: str = "general"
    content_duration: int = 30
    target_audience: str = ""


# ============================================
# Endpoints
# ============================================

@router.post("/generate", response_model=StoryStrategy)
async def generate_story_strategy(request: StrategyRequest):
    """Generate a story strategy based on brand and trend context."""
    agent = StoryStrategistAgent()
    
    strategy = await agent.generate_strategy(
        brand_name=request.brand_name,
        brand_description=request.brand_description,
        trend_query=request.trend_query,
        trend_summary=request.trend_summary,
        inspiration_ideas=request.inspiration_ideas,
        target_platform=request.target_platform,
        content_duration=request.content_duration,
        target_audience=request.target_audience,
    )
    
    return strategy
