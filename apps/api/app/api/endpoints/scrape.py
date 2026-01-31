"""Scrape endpoint - Extract content from websites."""

from pydantic import BaseModel, HttpUrl
from fastapi import APIRouter, HTTPException

from app.services.scraper import WebScraper
from app.agents.brand_analyzer import BrandAnalyzer
from app.models.project import BrandProfile

router = APIRouter()


class ScrapeRequest(BaseModel):
    url: HttpUrl
    brand_name: str | None = None


class ScrapeResponse(BaseModel):
    url: str
    title: str | None
    meta_description: str | None
    content_preview: str
    images_count: int
    brand_profile: BrandProfile | None = None


@router.post("", response_model=ScrapeResponse)
async def scrape_website(request: ScrapeRequest):
    """
    Scrape a website and optionally analyze brand.
    
    Returns basic content extraction and brand profile.
    """
    scraper = WebScraper()
    
    try:
        content = await scraper.scrape(str(request.url))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to scrape website: {str(e)}")
    
    # Analyze brand if we have content
    brand_profile = None
    if content.get("main_content"):
        try:
            analyzer = BrandAnalyzer()
            brand_profile = await analyzer.analyze(
                website_content=content["main_content"],
                website_url=str(request.url),
                brand_name=request.brand_name,
            )
        except Exception as e:
            print(f"Brand analysis failed: {e}")
            # Continue without brand profile
    
    return ScrapeResponse(
        url=content.get("url", str(request.url)),
        title=content.get("title"),
        meta_description=content.get("meta_description"),
        content_preview=content.get("main_content", "")[:500],
        images_count=len(content.get("images", [])),
        brand_profile=brand_profile,
    )


@router.post("/analyze")
async def analyze_brand(request: ScrapeRequest):
    """
    Full brand analysis from website.
    
    Scrapes website and performs deep brand analysis.
    """
    scraper = WebScraper()
    
    try:
        content = await scraper.scrape(str(request.url))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to scrape website: {str(e)}")
    
    if not content.get("main_content"):
        raise HTTPException(status_code=400, detail="No content found on website")
    
    analyzer = BrandAnalyzer()
    
    try:
        brand_profile = await analyzer.analyze(
            website_content=content["main_content"],
            website_url=str(request.url),
            brand_name=request.brand_name,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Brand analysis failed: {str(e)}")
    
    return {
        "url": content.get("url"),
        "brand_profile": brand_profile.model_dump(),
        "scraped_data": {
            "title": content.get("title"),
            "headings": content.get("headings", []),
            "images": content.get("images", []),
            "social_links": content.get("social_links", []),
        },
    }
