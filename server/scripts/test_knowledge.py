"""
test_knowledge.py — Verify the Serper.dev (Google Search) and GitHub search functionality.
Run from the 'server' directory: python scripts/test_knowledge.py
"""

import os
import sys
import asyncio
from pathlib import Path

# Add parent directory to Python path to import handlers
sys.path.append(str(Path(__file__).parent.parent))

# Import .env manually
_env_path = Path(__file__).parent.parent / "config" / ".env"
if _env_path.exists():
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _key, _val = _line.split("=", 1)
                os.environ.setdefault(_key.strip(), _val.strip())

from handlers.knowledge_handler import search_web, search_github

async def main():
    print("=" * 60)
    print("Testing KIRA Phase 4 Knowledge Handlers")
    print("=" * 60)

    # 1. Test GitHub Search
    print("\n[GitHub Test] Test 1: GitHub Search ('fastapi-boilerplate')")
    try:
        gh_result = await search_github("fastapi-boilerplate")
        print("\n--- GitHub Response ---")
        print(gh_result)
        print("-----------------------")
        if "fastapi" in gh_result.lower() or "boilerplate" in gh_result.lower():
            print("GitHub search looks successful!")
        else:
            print("GitHub search did not return expected results.")
    except Exception as e:
        print(f"GitHub Search failed with exception: {e}")

    # 2. Test Serper.dev Web Search
    print("\n[Web Test] Test 2: Serper.dev Web Search ('distance to the moon')")
    serper_key = os.getenv("SERPER_API_KEY")
    if not serper_key:
        print("Serper.dev API Key not set. Testing fallback message:")
        result = await search_web("distance to the moon")
        print(f"Response: {result}")
        if "configured" in result.lower():
            print("Handled missing API key correctly.")
        else:
            print("Unexpected handler behavior for missing API key.")
    else:
        print("Found Serper.dev API key. Executing web query...")
        try:
            web_result = await search_web("distance to the moon")
            print("\n--- Serper.dev Web Response ---")
            print(web_result)
            print("--------------------------")
            if "moon" in web_result.lower() or "distance" in web_result.lower():
                print("Serper.dev search looks successful!")
            else:
                print("Serper.dev search did not return expected results.")
        except Exception as e:
            print(f"Serper.dev Search failed with exception: {e}")

    print("\n" + "=" * 60)
    print("Tests Completed")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())
