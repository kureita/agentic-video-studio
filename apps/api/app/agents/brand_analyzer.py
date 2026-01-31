"""Brand Analyzer Agent - Analyzes websites to extract brand information."""

import json
from typing import Optional

from openai import AsyncOpenAI

from app.core.config import settings
from app.models.project import BrandProfile


class BrandAnalyzer:
    """Analyzes website content to extract brand profile information."""

    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = "gpt-4o"

    async def analyze(
        self,
        website_content: str,
        website_url: str,
        brand_name: Optional[str] = None,
    ) -> BrandProfile:
        """
        Analyze website content and extract brand profile.
        
        Args:
            website_content: Scraped text content from the website
            website_url: The URL of the website
            brand_name: Optional pre-provided brand name
            
        Returns:
            BrandProfile with extracted information
        """
        system_prompt = """You are a brand analyst expert. Analyze the provided website content and extract key brand information.

Return a JSON object with the following structure:
{
    "name": "Brand name",
    "tagline": "Brand tagline or slogan if found",
    "description": "Brief description of what the brand/company does",
    "primary_colors": ["#hex1", "#hex2"],
    "tone": "professional|casual|luxury|playful|technical|friendly",
    "products": ["Product or service 1", "Product or service 2"],
    "unique_selling_points": ["USP 1", "USP 2", "USP 3"]
}

Be concise but comprehensive. If information is not found, use null or empty arrays."""

        user_prompt = f"""Analyze this website content and extract brand information:

Website URL: {website_url}
{f'Known Brand Name: {brand_name}' if brand_name else ''}

Website Content:
{website_content[:8000]}  # Limit content length
"""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.3,
            )

            result = json.loads(response.choices[0].message.content)
            
            return BrandProfile(
                name=result.get("name") or brand_name or "Unknown Brand",
                tagline=result.get("tagline"),
                description=result.get("description"),
                primary_colors=result.get("primary_colors", []),
                tone=result.get("tone", "professional"),
                products=result.get("products", []),
                unique_selling_points=result.get("unique_selling_points", []),
            )

        except Exception as e:
            print(f"Brand analysis error: {e}")
            # Return minimal profile on error
            return BrandProfile(
                name=brand_name or "Unknown Brand",
                tone="professional",
            )

