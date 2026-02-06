"""Brand model for persistent brand profiles."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, HttpUrl


class BrandCreate(BaseModel):
    """Request model for creating a new brand."""
    name: str
    website_url: Optional[str] = None
    tagline: Optional[str] = None
    description: Optional[str] = None
    primary_colors: List[str] = []
    logo_url: Optional[str] = None
    tone: str = "professional"
    products: List[str] = []
    unique_selling_points: List[str] = []
    target_audience: Optional[str] = None


class BrandUpdate(BaseModel):
    """Request model for updating a brand."""
    name: Optional[str] = None
    website_url: Optional[str] = None
    tagline: Optional[str] = None
    description: Optional[str] = None
    primary_colors: Optional[List[str]] = None
    logo_url: Optional[str] = None
    tone: Optional[str] = None
    products: Optional[List[str]] = None
    unique_selling_points: Optional[List[str]] = None
    target_audience: Optional[str] = None


class Brand(BaseModel):
    """Full brand model with all fields."""
    id: str
    name: str
    website_url: Optional[str] = None
    tagline: Optional[str] = None
    description: Optional[str] = None
    primary_colors: List[str] = []
    logo_url: Optional[str] = None
    tone: str = "professional"
    products: List[str] = []
    unique_selling_points: List[str] = []
    target_audience: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class BrandAnalyzeRequest(BaseModel):
    """Request model for analyzing a website to create a brand."""
    website_url: HttpUrl


class BrandList(BaseModel):
    """Response model for listing brands."""
    brands: List[Brand]
    total: int
