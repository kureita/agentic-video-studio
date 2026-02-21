import logging
import re
from typing import Dict, Any, List, Optional
from firecrawl.v1 import V1FirecrawlApp
from app.core.config import settings


logger = logging.getLogger(__name__)

# Regex to detect if the query looks like a bare domain or a full URL
# e.g. "regulify.ai", "https://regulify.ai", "www.example.com/page"
_URL_PATTERN = re.compile(
    r'^(https?://)?'               # optional scheme
    r'([a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}'  # domain
    r'(/[^\s]*)?$'                 # optional path
)

def _normalize_url(query: str) -> str:
    """Ensure the URL has a scheme so Firecrawl can scrape it."""
    query = query.strip()
    if not query.startswith(("http://", "https://")):
        return "https://" + query
    return query

class FirecrawlService:
    def __init__(self):
        self.api_key = settings.firecrawl_api_key
        self.app = None
        if self.api_key:
            try:
                self.app = V1FirecrawlApp(api_key=self.api_key)
            except Exception as e:
                logger.error(f"Failed to initialize V1FirecrawlApp: {e}")


    async def search_web(self, query: str) -> str:
        """
        Smart web lookup:
        - If the query looks like a URL / domain → scrape that page directly.
        - Otherwise → run a web search and summarize the top results.
        Returns a string summarizing the content for the LLM.
        """
        if not self.app:
            return "Web search is currently unavailable because the FIRECRAWL_API_KEY is not configured."

        query = query.strip()

        # ── CASE 1: Direct URL / domain scrape ────────────────────────────────
        if _URL_PATTERN.match(query):
            return await self._scrape_url(query)

        # ── CASE 2: General web search ─────────────────────────────────────────
        return await self._search(query)

    # ──────────────────────────────────────────────────────────────────────────
    # Private helpers
    # ──────────────────────────────────────────────────────────────────────────

    async def _scrape_url(self, url: str) -> str:
        """Scrape a single URL and return its markdown content."""
        url = _normalize_url(url)
        try:
            logger.info(f"Scraping URL with Firecrawl: {url}")
            result = self.app.scrape_url(url, formats=["markdown"])

            if not result:
                return f"Failed to scrape '{url}': empty response."

            # firecrawl-py v1+ returns a ScrapeResponse object
            if hasattr(result, "markdown"):
                markdown = result.markdown or ""
            elif isinstance(result, dict):
                markdown = result.get("markdown", "")
            else:
                markdown = str(result)

            if not markdown:
                return f"No content could be extracted from '{url}'."

            # Trim to keep context reasonable (~4 000 chars ≈ ~1 000 tokens)
            snippet = markdown[:4000] + "\n\n[content truncated...]" if len(markdown) > 4000 else markdown
            return f"Scraped content from {url}:\n\n{snippet}"

        except Exception as e:
            logger.error(f"Error scraping URL '{url}': {e}")
            return f"An error occurred while scraping '{url}': {str(e)}"

    async def _search(self, query: str) -> str:
        """Run a general web search and return a summary of top results."""
        try:
            logger.info(f"Searching web with Firecrawl for: {query}")
            result = self.app.search(query=query)

            if not result or not isinstance(result, dict):
                return f"No valid results found for '{query}'."

            if not result.get("success", False):
                return f"Search failed: {result.get('error', 'Unknown error')}"

            data = result.get("data", [])
            if not data:
                return f"No documents found for query '{query}'."

            # Compile top 3 results
            formatted_results = []
            for idx, item in enumerate(data[:3]):
                url = item.get("url", "Unknown URL")
                title = item.get("title", "No Title")
                description = item.get("description", "No description available.")
                markdown = item.get("markdown", "")

                snippet = (
                    markdown[:500] + "..."
                    if markdown and len(markdown) > 500
                    else markdown or description
                )
                formatted_results.append(
                    f"Result {idx+1}: [{title}]({url})\nContent snippet: {snippet}\n---"
                )

            return f"Top web search results for '{query}':\n\n" + "\n".join(formatted_results)

        except Exception as e:
            logger.error(f"Error executing web search: {e}")
            return f"An error occurred while trying to perform the web search: {str(e)}"
