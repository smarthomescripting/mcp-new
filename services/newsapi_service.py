"""NewsAPI search service for MCP."""
from __future__ import annotations

from typing import Any

from fastmcp import FastMCP
from newsapi import NewsApiClient

from mcp_framework import log_interaction


API_KEY = "14c58d3767904740bae0385bd524b702"


def _summarize_article(article: dict[str, Any]) -> dict[str, Any]:
    source = article.get("source")
    source_name = source.get("name") if isinstance(source, dict) else source

    return {
        "title": article.get("title"),
        "description": article.get("description"),
        "url": article.get("url"),
        "published_at": article.get("publishedAt"),
        "source": source_name,
    }


def register_newsapi_service(mcp: FastMCP) -> None:
    """Register a NewsAPI search tool on the provided MCP instance."""

    client = NewsApiClient(api_key=API_KEY)

    @mcp.tool()
    def search_news(
        query: str,
        *,
        language: str = "en",
        sort_by: str = "relevancy",
        page_size: int = 5,
    ) -> dict[str, Any]:
        """Search for recent articles matching the provided keywords."""

        trimmed_query = query.strip()
        if not trimmed_query:
            raise ValueError("Query must not be empty.")

        bounded_page_size = max(1, min(page_size, 100))

        try:
            response = client.get_everything(
                q=trimmed_query,
                language=language,
                sort_by=sort_by,
                page_size=bounded_page_size,
            )
        except Exception as exc:
            log_interaction(
                "search_news_error",
                {
                    "query": trimmed_query,
                    "language": language,
                    "sort_by": sort_by,
                    "page_size": bounded_page_size,
                },
                {"error": str(exc), "type": exc.__class__.__name__},
            )
            raise

        articles = [_summarize_article(article) for article in response.get("articles", [])]
        result = {
            "query": trimmed_query,
            "language": language,
            "sort_by": sort_by,
            "page_size": bounded_page_size,
            "total_results": response.get("totalResults", len(articles)),
            "articles": articles,
        }

        log_interaction(
            "search_news",
            {
                "query": trimmed_query,
                "language": language,
                "sort_by": sort_by,
                "page_size": bounded_page_size,
            },
            {"total_results": result["total_results"], "article_count": len(articles)},
        )

        return result
