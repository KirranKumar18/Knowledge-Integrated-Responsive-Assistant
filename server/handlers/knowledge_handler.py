"""
knowledge_handler.py — KIRA Phase 4
Handles web search via Serper.dev (Google Search) and repository search via GitHub API.
"""

import os
import logging
from urllib.parse import urlparse
import httpx

log = logging.getLogger("kira-server.knowledge")

# Load API keys from environment
SERPER_API_KEY = os.getenv("SERPER_API_KEY")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

async def search_web(query: str, max_results: int = 2) -> str:
    """
    Search the web using Google Search via Serper.dev.
    Returns a spoken-friendly summary of the top results.
    """
    if not SERPER_API_KEY:
        log.warning("SERPER_API_KEY is not set. Web search is unavailable.")
        return "I cannot search the web because the Serper.dev API key is not configured on the server."

    log.info(f"Searching Google Search via Serper for: '{query}'")
    url = "https://google.serper.dev/search"
    headers = {
        "X-API-KEY": SERPER_API_KEY,
        "Content-Type": "application/json"
    }
    payload = {
        "q": query,
        "num": max_results
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, headers=headers, json=payload)
            
            if response.status_code == 403 or response.status_code == 401:
                log.error(f"Serper API key unauthorized: {response.status_code}")
                return "The Serper.dev API key is invalid or unauthorized."
            
            response.raise_for_status()
            data = response.json()
            
            results = data.get("organic", [])
            if not results:
                return f"I couldn't find any web results for '{query}'."

            spoken_parts = [f"Here are the top search results for {query}."]
            for i, res in enumerate(results):
                title = res.get("title", "Untitled page")
                raw_url = res.get("link", "")
                snippet = res.get("snippet", "").strip()
                
                # Extract clean domain name for speech friendliness
                domain = ""
                if raw_url:
                    try:
                        parsed = urlparse(raw_url)
                        domain = parsed.netloc
                        if domain.startswith("www."):
                            domain = domain[4:]
                    except Exception:
                        pass
                
                ordinal = "First" if i == 0 else "Second" if i == 1 else "Third"
                domain_phrase = f" on {domain}" if domain else ""
                
                # Clean up snippet text
                clean_snippet = snippet
                if len(clean_snippet) > 150:
                    clean_snippet = clean_snippet[:147] + "..."
                
                spoken_parts.append(f"{ordinal}, '{title}'{domain_phrase}. It mentions: {clean_snippet}")

            return " ".join(spoken_parts)

    except httpx.HTTPError as http_err:
        log.error(f"Serper search HTTP error: {http_err}")
        return "I encountered a network error while trying to search the web."
    except Exception as e:
        log.error(f"Error in search_web: {e}")
        return "I had trouble processing that web search."


async def search_github(query: str, language: str | None = None, max_results: int = 3) -> str:
    """
    Search GitHub repositories using the public search API.
    Returns a spoken-friendly list of top repositories.
    """
    log.info(f"Searching GitHub for: '{query}' (language: {language})")
    url = "https://api.github.com/search/repositories"
    
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "KIRA-Voice-Assistant"
    }
    
    # Add optional GitHub token for higher rate limits
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"

    # Build the query string
    q_parts = [query]
    if language:
        q_parts.append(f"language:{language}")
    
    params = {
        "q": " ".join(q_parts),
        "per_page": max_results,
        "sort": "stars",
        "order": "desc"
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, headers=headers, params=params)
            
            if response.status_code == 403:
                log.warning("GitHub API rate limit exceeded or forbidden.")
                return "I couldn't search GitHub because the rate limit was exceeded."
                
            response.raise_for_status()
            data = response.json()
            
            items = data.get("items", [])
            if not items:
                lang_phrase = f" in {language}" if language else ""
                return f"I couldn't find any repositories matching '{query}'{lang_phrase} on GitHub."

            spoken_parts = [f"I found {len(items)} repositories on GitHub matching '{query}'."]
            for i, item in enumerate(items):
                full_name = item.get("full_name", "")
                owner_name = item.get("owner", {}).get("login", "")
                repo_name = item.get("name", "")
                stars = item.get("stargazers_count", 0)
                description = item.get("description") or "No description available"
                repo_url = item.get("html_url", f"https://github.com/{full_name}")
                
                ordinal = "First" if i == 0 else "Second" if i == 1 else "Third"
                
                # Format name for better pronunciation
                spoken_name = f"{repo_name} by {owner_name}"
                
                clean_description = description
                if len(clean_description) > 120:
                    clean_description = clean_description[:117] + "..."
                
                spoken_parts.append(f"{ordinal}, {spoken_name} with {stars} stars. Link: {repo_url}. Description: {clean_description}.")

            return " ".join(spoken_parts)

    except httpx.HTTPError as http_err:
        log.error(f"GitHub API HTTP error: {http_err}")
        return "I encountered a network error while trying to search GitHub."
    except Exception as e:
        log.error(f"Error in search_github: {e}")
        return "I had trouble search GitHub repositories."
