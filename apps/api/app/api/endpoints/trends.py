"""Trend research API endpoints."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional

from app.services.web_search import WebSearchService, TrendResearchResult, SearchResult

router = APIRouter(prefix="/trends", tags=["trends"])


class TrendSearchRequest(BaseModel):
    """Request for trend search."""
    query: str
    max_results: int = 5


class ViralTrendRequest(BaseModel):
    """Request for viral trend search."""
    topic: str
    platform: str = "general"  # tiktok, instagram, youtube, general


class ContentInspirationRequest(BaseModel):
    """Request for content inspiration search."""
    brand_name: str
    industry: str
    content_type: str = "video"


class InspirationBrief(BaseModel):
    """Creative inspiration brief combining brand + trend."""
    brand_name: str
    trend_summary: str
    key_elements: List[str]
    suggested_angles: List[str]
    viral_hooks: List[str]
    content_ideas: List[str]


# ============================================
# Endpoints
# ============================================

@router.post("/search", response_model=TrendResearchResult)
async def search_trends(request: TrendSearchRequest):
    """Search the web for trend information."""
    service = WebSearchService()
    return await service.search(query=request.query, max_results=request.max_results)


@router.post("/viral", response_model=TrendResearchResult)
async def search_viral_trends(request: ViralTrendRequest):
    """Search for viral trends on a specific topic."""
    service = WebSearchService()
    return await service.search_viral_trends(
        topic=request.topic,
        platform=request.platform
    )


@router.post("/inspiration", response_model=TrendResearchResult)
async def search_content_inspiration(request: ContentInspirationRequest):
    """Search for content inspiration based on brand and industry."""
    service = WebSearchService()
    return await service.search_content_inspiration(
        brand_name=request.brand_name,
        industry=request.industry,
        content_type=request.content_type
    )


@router.post("/brief", response_model=InspirationBrief)
async def generate_inspiration_brief(
    brand_name: str,
    brand_description: str,
    trend_query: str
):
    """
    Generate a creative brief combining brand context with trend research.
    Uses web search + LLM to create actionable content ideas.
    """
    service = WebSearchService()
    
    # Search for trends
    trend_results = await service.search(trend_query, max_results=5, search_depth="advanced")
    
    # For now, extract key elements from search results
    # In future, this would use an LLM to synthesize the brief
    key_elements = []
    viral_hooks = []
    
    for result in trend_results.results[:3]:
        if result.content:
            # Extract first sentence as a key element
            sentences = result.content.split(".")
            if sentences:
                key_elements.append(sentences[0].strip()[:200])
    
    # Generate basic brief (would use LLM in production)
    brief = InspirationBrief(
        brand_name=brand_name,
        trend_summary=trend_results.summary or f"Research on: {trend_query}",
        key_elements=key_elements or ["Trending content found"],
        suggested_angles=[
            f"Apply {trend_query} concept to {brand_name}",
            f"Create educational content about {trend_query}",
            f"Behind-the-scenes take on {trend_query}",
        ],
        viral_hooks=[
            "Hook with surprising statistic",
            "Start with relatable problem",
            "Use trending audio/format",
        ],
        content_ideas=[
            f"{brand_name} takes on the {trend_query} trend",
            f"Why {trend_query} matters for your industry",
            f"Our unique spin on {trend_query}",
        ]
    )
    
    return brief
