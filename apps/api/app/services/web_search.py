"""Web search service for trend research using Tavily API."""

from typing import List, Optional
from pydantic import BaseModel

from app.core.config import settings

try:
    from tavily import TavilyClient
    TAVILY_AVAILABLE = True
except ImportError:
    TAVILY_AVAILABLE = False


class SearchResult(BaseModel):
    """Individual search result."""
    title: str
    url: str
    content: str
    score: float


class TrendResearchResult(BaseModel):
    """Complete trend research results."""
    query: str
    results: List[SearchResult]
    summary: Optional[str] = None


class WebSearchService:
    """Service for performing web searches for trend research."""
    
    def __init__(self):
        self.tavily_api_key = getattr(settings, 'tavily_api_key', '') or ''
        self.client = None
        
        if self.tavily_api_key and TAVILY_AVAILABLE:
            self.client = TavilyClient(api_key=self.tavily_api_key)
    
    async def search(
        self, 
        query: str, 
        max_results: int = 5,
        search_depth: str = "basic"
    ) -> TrendResearchResult:
        """
        Search the web for trend research.
        
        Args:
            query: Search query string
            max_results: Maximum number of results to return
            search_depth: "basic" or "advanced" for more thorough search
            
        Returns:
            TrendResearchResult with search results and optional summary
        """
        if not self.client:
            # Return mock results if no API key
            return TrendResearchResult(
                query=query,
                results=[
                    SearchResult(
                        title="No API key configured",
                        url="",
                        content="Please set TAVILY_API_KEY in your environment to enable web search.",
                        score=0.0
                    )
                ]
            )
        
        try:
            # Perform search with Tavily
            response = self.client.search(
                query=query,
                max_results=max_results,
                search_depth=search_depth,
                include_answer=True,
            )
            
            results = []
            for result in response.get("results", []):
                results.append(SearchResult(
                    title=result.get("title", ""),
                    url=result.get("url", ""),
                    content=result.get("content", ""),
                    score=result.get("score", 0.0),
                ))
            
            return TrendResearchResult(
                query=query,
                results=results,
                summary=response.get("answer"),
            )
            
        except Exception as e:
            return TrendResearchResult(
                query=query,
                results=[
                    SearchResult(
                        title="Search failed",
                        url="",
                        content=str(e),
                        score=0.0
                    )
                ]
            )
    
    async def search_viral_trends(
        self, 
        topic: str,
        platform: str = "general"
    ) -> TrendResearchResult:
        """
        Search for viral trends related to a topic.
        
        Args:
            topic: Topic to search for viral trends
            platform: Target platform (tiktok, instagram, youtube, general)
            
        Returns:
            TrendResearchResult with viral trend information
        """
        platform_queries = {
            "tiktok": f"{topic} viral TikTok trend 2024",
            "instagram": f"{topic} viral Instagram Reels trend 2024",
            "youtube": f"{topic} viral YouTube Shorts trend 2024",
            "general": f"{topic} viral social media trend 2024",
        }
        
        query = platform_queries.get(platform, platform_queries["general"])
        return await self.search(query, max_results=5, search_depth="advanced")
    
    async def search_content_inspiration(
        self,
        brand_name: str,
        industry: str,
        content_type: str = "video"
    ) -> TrendResearchResult:
        """
        Search for content inspiration based on brand and industry.
        
        Args:
            brand_name: Name of the brand
            industry: Industry/niche of the brand
            content_type: Type of content (video, image, post)
            
        Returns:
            TrendResearchResult with content inspiration
        """
        query = f"best {content_type} marketing examples {industry} brands 2024 viral successful"
        return await self.search(query, max_results=5, search_depth="advanced")
