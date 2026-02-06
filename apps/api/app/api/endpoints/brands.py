"""Brand CRUD endpoints for persistent brand management."""

from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.database import get_database
from app.models.brand import Brand, BrandCreate, BrandUpdate, BrandList, BrandAnalyzeRequest
from app.services.scraper import WebScraper
from app.agents.brand_analyzer import BrandAnalyzer

router = APIRouter(prefix="/brands", tags=["brands"])


# ============================================
# Helper Functions
# ============================================

def brand_from_doc(doc: dict) -> Brand:
    """Convert MongoDB document to Brand model."""
    return Brand(
        id=str(doc["_id"]),
        name=doc.get("name", ""),
        website_url=doc.get("website_url"),
        tagline=doc.get("tagline"),
        description=doc.get("description"),
        primary_colors=doc.get("primary_colors", []),
        logo_url=doc.get("logo_url"),
        tone=doc.get("tone", "professional"),
        products=doc.get("products", []),
        unique_selling_points=doc.get("unique_selling_points", []),
        target_audience=doc.get("target_audience"),
        created_at=doc.get("created_at", datetime.now(timezone.utc)),
        updated_at=doc.get("updated_at", datetime.now(timezone.utc)),
    )


def get_brands_collection():
    """Get the brands collection."""
    return get_database().brands


# ============================================
# Endpoints
# ============================================

@router.get("", response_model=BrandList)
async def list_brands(skip: int = 0, limit: int = 50):
    """List all saved brands."""
    brands_coll = get_brands_collection()
    cursor = brands_coll.find().sort("updated_at", -1).skip(skip).limit(limit)
    brands = []
    async for doc in cursor:
        brands.append(brand_from_doc(doc))
    
    total = await brands_coll.count_documents({})
    return BrandList(brands=brands, total=total)


@router.post("", response_model=Brand)
async def create_brand(request: BrandCreate):
    """Create a new brand profile."""
    now = datetime.now(timezone.utc)
    
    brand_doc = {
        "name": request.name,
        "website_url": request.website_url,
        "tagline": request.tagline,
        "description": request.description,
        "primary_colors": request.primary_colors,
        "logo_url": request.logo_url,
        "tone": request.tone,
        "products": request.products,
        "unique_selling_points": request.unique_selling_points,
        "target_audience": request.target_audience,
        "created_at": now,
        "updated_at": now,
    }
    
    brands_coll = get_brands_collection()
    result = await brands_coll.insert_one(brand_doc)
    brand_doc["_id"] = result.inserted_id
    
    return brand_from_doc(brand_doc)


@router.get("/{brand_id}", response_model=Brand)
async def get_brand(brand_id: str):
    """Get a specific brand by ID."""
    brands_coll = get_brands_collection()
    try:
        doc = await brands_coll.find_one({"_id": ObjectId(brand_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid brand ID format")
    
    if not doc:
        raise HTTPException(status_code=404, detail="Brand not found")
    
    return brand_from_doc(doc)


@router.put("/{brand_id}", response_model=Brand)
async def update_brand(brand_id: str, request: BrandUpdate):
    """Update an existing brand."""
    try:
        oid = ObjectId(brand_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid brand ID format")
    
    # Build update dict with only provided fields
    update_data = {"updated_at": datetime.now(timezone.utc)}
    for field, value in request.model_dump(exclude_unset=True).items():
        if value is not None:
            update_data[field] = value
    
    brands_coll = get_brands_collection()
    result = await brands_coll.update_one(
        {"_id": oid},
        {"$set": update_data}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Brand not found")
    
    doc = await brands_coll.find_one({"_id": oid})
    return brand_from_doc(doc)


@router.delete("/{brand_id}")
async def delete_brand(brand_id: str):
    """Delete a brand."""
    try:
        oid = ObjectId(brand_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid brand ID format")
    
    brands_coll = get_brands_collection()
    result = await brands_coll.delete_one({"_id": oid})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Brand not found")
    
    return {"message": "Brand deleted successfully"}


@router.post("/analyze-website", response_model=Brand)
async def analyze_website_for_brand(request: BrandAnalyzeRequest):
    """
    Analyze a website and create a brand profile from it.
    Uses web scraping + LLM analysis to extract brand information.
    """
    website_url = str(request.website_url)
    
    # Scrape website
    scraper = WebScraper()
    scraped_data = await scraper.scrape(website_url)
    
    if not scraped_data:
        raise HTTPException(status_code=400, detail="Failed to scrape website")
    
    # Analyze with LLM
    analyzer = BrandAnalyzer()
    # Scraper returns a dict, we need to pass the text content
    content_text = scraped_data.get("main_content", "") or scraped_data.get("description", "") or "No content found"
    brand_profile = await analyzer.analyze(content_text, website_url=website_url)
    
    if not brand_profile:
        raise HTTPException(status_code=500, detail="Failed to analyze brand")
    
    # Create brand in database
    now = datetime.now(timezone.utc)
    
    brand_doc = {
        "name": brand_profile.name,
        "website_url": website_url,
        "tagline": brand_profile.tagline,
        "description": brand_profile.description,
        "primary_colors": brand_profile.primary_colors,
        "logo_url": brand_profile.logo_url,
        "tone": brand_profile.tone,
        "products": brand_profile.products,
        "unique_selling_points": brand_profile.unique_selling_points,
        "target_audience": None,  # Can be updated later
        "created_at": now,
        "updated_at": now,
    }
    
    brands_coll = get_brands_collection()
    result = await brands_coll.insert_one(brand_doc)
    brand_doc["_id"] = result.inserted_id
    
    return brand_from_doc(brand_doc)
