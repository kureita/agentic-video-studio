"""Web Scraper Service - Extracts content from websites."""

import re
from typing import Optional
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup


class WebScraper:
    """Scrapes and extracts content from websites."""

    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

    async def scrape(self, url: str) -> dict:
        """
        Scrape a website and extract relevant content.
        
        Args:
            url: The URL to scrape
            
        Returns:
            Dictionary with extracted content
        """
        async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
            try:
                response = await client.get(url, headers=self.headers)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.text, "lxml")
                
                # Extract various content
                result = {
                    "url": str(response.url),
                    "title": self._extract_title(soup),
                    "meta_description": self._extract_meta_description(soup),
                    "headings": self._extract_headings(soup),
                    "main_content": self._extract_main_content(soup),
                    "images": self._extract_images(soup, str(response.url)),
                    "links": self._extract_important_links(soup, str(response.url)),
                    "contact_info": self._extract_contact_info(soup),
                    "social_links": self._extract_social_links(soup),
                }
                
                return result
                
            except httpx.HTTPStatusError as e:
                raise Exception(f"HTTP error {e.response.status_code}: {str(e)}")
            except httpx.RequestError as e:
                raise Exception(f"Request error: {str(e)}")

    def _extract_title(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract page title."""
        # Try og:title first
        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            return og_title["content"]
        
        # Fall back to title tag
        title = soup.find("title")
        if title:
            return title.get_text(strip=True)
        
        return None

    def _extract_meta_description(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract meta description."""
        # Try og:description first
        og_desc = soup.find("meta", property="og:description")
        if og_desc and og_desc.get("content"):
            return og_desc["content"]
        
        # Fall back to meta description
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc and meta_desc.get("content"):
            return meta_desc["content"]
        
        return None

    def _extract_headings(self, soup: BeautifulSoup) -> list[str]:
        """Extract all headings (h1-h3)."""
        headings = []
        for tag in ["h1", "h2", "h3"]:
            for heading in soup.find_all(tag):
                text = heading.get_text(strip=True)
                if text and len(text) > 2:
                    headings.append(text)
        return headings[:20]  # Limit to 20 headings

    def _extract_main_content(self, soup: BeautifulSoup) -> str:
        """Extract main text content."""
        # Remove script and style elements
        for element in soup(["script", "style", "nav", "footer", "header", "aside"]):
            element.decompose()
        
        # Try to find main content area
        main = soup.find("main") or soup.find("article") or soup.find("body")
        
        if main:
            # Get text from paragraphs
            paragraphs = main.find_all("p")
            text = " ".join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))
            
            # Clean up whitespace
            text = re.sub(r"\s+", " ", text)
            
            return text[:10000]  # Limit to 10k chars
        
        return ""

    def _extract_images(self, soup: BeautifulSoup, base_url: str) -> list[dict]:
        """Extract important images."""
        images = []
        
        # Get og:image
        og_image = soup.find("meta", property="og:image")
        if og_image and og_image.get("content"):
            images.append({
                "url": og_image["content"],
                "type": "og_image",
            })
        
        # Get logo
        logo = soup.find("img", class_=re.compile(r"logo", re.I))
        if logo and logo.get("src"):
            images.append({
                "url": urljoin(base_url, logo["src"]),
                "type": "logo",
            })
        
        # Get other prominent images
        for img in soup.find_all("img", src=True)[:10]:
            src = img.get("src", "")
            if src and not any(skip in src.lower() for skip in ["icon", "pixel", "tracking"]):
                images.append({
                    "url": urljoin(base_url, src),
                    "type": "image",
                    "alt": img.get("alt", ""),
                })
        
        return images[:15]  # Limit to 15 images

    def _extract_important_links(self, soup: BeautifulSoup, base_url: str) -> list[dict]:
        """Extract important internal links."""
        links = []
        seen = set()
        
        important_keywords = ["about", "product", "service", "feature", "pricing", "contact"]
        
        for a in soup.find_all("a", href=True):
            href = a.get("href", "")
            text = a.get_text(strip=True)
            
            if not href or href.startswith("#") or href in seen:
                continue
            
            full_url = urljoin(base_url, href)
            
            # Only include internal links with important keywords
            if urlparse(full_url).netloc == urlparse(base_url).netloc:
                if any(kw in href.lower() or kw in text.lower() for kw in important_keywords):
                    links.append({"url": full_url, "text": text})
                    seen.add(href)
        
        return links[:10]

    def _extract_contact_info(self, soup: BeautifulSoup) -> dict:
        """Extract contact information."""
        contact = {}
        
        # Email
        email_match = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", soup.get_text())
        if email_match:
            contact["email"] = email_match.group()
        
        # Phone
        phone_match = re.search(r"[\+]?[(]?[0-9]{1,3}[)]?[-\s.]?[0-9]{1,4}[-\s.]?[0-9]{1,4}[-\s.]?[0-9]{1,9}", soup.get_text())
        if phone_match:
            contact["phone"] = phone_match.group()
        
        return contact

    def _extract_social_links(self, soup: BeautifulSoup) -> list[dict]:
        """Extract social media links."""
        social_platforms = {
            "facebook.com": "facebook",
            "twitter.com": "twitter",
            "x.com": "twitter",
            "linkedin.com": "linkedin",
            "instagram.com": "instagram",
            "youtube.com": "youtube",
            "tiktok.com": "tiktok",
        }
        
        socials = []
        seen = set()
        
        for a in soup.find_all("a", href=True):
            href = a.get("href", "")
            for domain, platform in social_platforms.items():
                if domain in href and platform not in seen:
                    socials.append({"platform": platform, "url": href})
                    seen.add(platform)
                    break
        
        return socials

