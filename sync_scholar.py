#!/usr/bin/env python3
"""
sync_scholar.py — Discover new papers from Google Scholar.

Usage:
    python sync_scholar.py                # Check for new papers (fast, titles only)
    python sync_scholar.py --limit 20     # Only check the 20 most recent papers
    python sync_scholar.py --proxy        # Use free proxy to avoid rate-limiting
    python sync_scholar.py --add          # Check and offer to add new papers
    python sync_scholar.py --list-known   # List all known paper titles

This script fetches your Google Scholar profile and compares against
papers.json to find papers you haven't added to your website yet.

Requirements:
    pip install scholarly

Note: Google Scholar scraping can be rate-limited. If you encounter issues,
wait a few minutes and try again, or use a VPN.
"""

import json
import os
import sys
import re
from difflib import SequenceMatcher

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PAPERS_JSON = "papers.json"
# Google Scholar author ID (from your profile URL)
SCHOLAR_ID = "MEz23joAAAAJ"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_papers():
    """Load papers.json."""
    with open(PAPERS_JSON, "r") as f:
        return json.load(f)


def normalize_title(title):
    """Normalize a title for fuzzy matching."""
    title = title.lower().strip()
    title = re.sub(r'[^\w\s]', '', title)  # remove punctuation
    title = re.sub(r'\s+', ' ', title)     # normalize whitespace
    return title


def title_match(title1, title2, threshold=0.85):
    """Check if two titles are similar enough to be the same paper."""
    n1 = normalize_title(title1)
    n2 = normalize_title(title2)
    # Exact match after normalization
    if n1 == n2:
        return True
    # Fuzzy match
    ratio = SequenceMatcher(None, n1, n2).ratio()
    return ratio >= threshold


def get_known_titles(data):
    """Get set of known paper titles from papers.json."""
    return [p["title"] for p in data.get("papers", [])]


# ---------------------------------------------------------------------------
# Google Scholar fetching
# ---------------------------------------------------------------------------

def _setup_scholarly_proxy():
    """Try to set up a proxy for scholarly to avoid rate-limiting."""
    from scholarly import scholarly
    try:
        from scholarly import ProxyGenerator
        pg = ProxyGenerator()
        # Try free proxies first
        success = pg.FreeProxies()
        if success:
            scholarly.use_proxy(pg)
            print("  Using free proxy to avoid rate-limiting")
            return True
    except Exception:
        pass
    return False


def fetch_scholar_papers(scholar_id, limit=None, use_proxy=False):
    """
    Fetch papers from Google Scholar using the scholarly library.

    This only fetches the profile-level metadata (title, year, venue,
    citation count) — NO per-paper fill calls, which makes it fast
    (~1 request instead of N+1).

    Args:
        scholar_id: Google Scholar author ID.
        limit: If set, only return the N most recent papers.
        use_proxy: If True, route through free proxies to avoid blocks.
    """
    try:
        from scholarly import scholarly
    except ImportError:
        print("ERROR: 'scholarly' package not installed.")
        print("Install it with: pip install scholarly")
        _offer_browser_fallback(scholar_id)
        sys.exit(1)

    print(f"Fetching Google Scholar profile: {scholar_id}")
    if limit:
        print(f"(Checking most recent {limit} papers...)")
    else:
        print("(Fetching all papers...)")

    # Set up proxy if requested or as retry
    if use_proxy:
        _setup_scholarly_proxy()

    print()

    try:
        author = scholarly.search_author_id(scholar_id)
        # sortby="pubdate" gets newest first; only fetch publication list
        author = scholarly.fill(author, sections=["publications"], sortby="pubdate")
    except Exception as e:
        if not use_proxy:
            # Retry once with proxy
            print(f"  Direct fetch failed: {e}")
            print("  Retrying with free proxy...\n")
            return fetch_scholar_papers(scholar_id, limit=limit, use_proxy=True)
        else:
            print(f"ERROR: Could not fetch Scholar profile: {e}")
            print("Google is rate-limiting requests.")
            _offer_browser_fallback(scholar_id)
            sys.exit(1)

    publications = author.get("publications", [])
    if limit:
        publications = publications[:limit]

    papers = []
    for pub in publications:
        info = pub.get("bib", {})
        title = info.get("title", "")
        year = info.get("pub_year", "")
        venue = info.get("citation", "")
        citations = pub.get("num_citations", 0)
        authors = info.get("author", "")

        # Skip patents
        if "patent" in venue.lower():
            continue

        # Skip entries with no year
        if not year:
            continue

        papers.append({
            "title": title,
            "authors": authors,
            "year": year,
            "venue": venue,
            "citations": citations,
            "scholar_url": pub.get("author_pub_id", ""),
        })

    # Sort by year descending
    papers.sort(key=lambda p: p.get("year", "0"), reverse=True)
    print(f"  Found {len(papers)} papers on Scholar")
    return papers


def _offer_browser_fallback(scholar_id):
    """Open the Scholar page in the browser as a fallback."""
    url = f"https://scholar.google.com/citations?user={scholar_id}&hl=en&sortby=pubdate"
    print(f"\n  You can manually check your Scholar page (sorted by date):")
    print(f"  {url}")
    try:
        import webbrowser
        print("\n  Opening in browser...")
        webbrowser.open(url)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Comparison and reporting
# ---------------------------------------------------------------------------

def find_missing_papers(scholar_papers, known_titles):
    """Find papers from Scholar that are not in papers.json."""
    missing = []
    matched = []

    for sp in scholar_papers:
        found = False
        for kt in known_titles:
            if title_match(sp["title"], kt):
                found = True
                matched.append((sp["title"], kt))
                break
        if not found:
            missing.append(sp)

    return missing, matched


def report_results(missing, matched, scholar_papers):
    """Print comparison results."""
    print(f"Scholar papers found: {len(scholar_papers)}")
    print(f"Already on website:   {len(matched)}")
    print(f"Missing from website: {len(missing)}")
    print()

    if missing:
        print("=" * 70)
        print("PAPERS NOT ON YOUR WEBSITE:")
        print("=" * 70)
        for i, p in enumerate(missing):
            year = p.get("year", "?")
            citations = p.get("citations", 0)
            venue = p.get("venue", "")[:50]
            print(f"\n  {i+1}. [{year}] {p['title']}")
            if venue:
                print(f"     Venue: {venue}")
            print(f"     Citations: {citations}")
            if p.get("authors"):
                authors = p["authors"]
                if len(authors) > 80:
                    authors = authors[:80] + "..."
                print(f"     Authors: {authors}")
        print()
    else:
        print("✓ All Scholar papers are on your website!")


def offer_to_add(missing):
    """Offer to add missing papers using add_paper.py."""
    print("\nWould you like to add any of these papers?")
    print("Enter paper numbers separated by commas (or 'q' to quit):")
    choice = input("> ").strip()

    if choice.lower() in ("q", "quit", ""):
        return

    try:
        indices = [int(x.strip()) - 1 for x in choice.split(",")]
    except ValueError:
        print("Invalid input.")
        return

    for idx in indices:
        if 0 <= idx < len(missing):
            paper = missing[idx]
            print(f"\n--- Adding: {paper['title']} ---")
            print("Launching interactive mode...")
            print("(Tip: If it has an arXiv link, use 'python add_paper.py --arxiv <id>' instead)")
            os.system("python3 add_paper.py")
        else:
            print(f"Invalid index: {idx + 1}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    if "--help" in sys.argv or "-h" in sys.argv:
        print(__doc__)
        return

    data = load_papers()
    known_titles = get_known_titles(data)

    if "--list-known" in sys.argv:
        print(f"\nKnown papers ({len(known_titles)}):\n")
        for i, t in enumerate(known_titles):
            print(f"  {i+1}. {t}")
        return

    # Parse --limit flag
    limit = None
    for i, arg in enumerate(sys.argv[1:], 1):
        if arg == "--limit" and i < len(sys.argv) - 1:
            try:
                limit = int(sys.argv[i + 1])
            except ValueError:
                print(f"ERROR: Invalid --limit value: {sys.argv[i + 1]}")
                sys.exit(1)

    # Fetch from Scholar
    use_proxy = "--proxy" in sys.argv
    scholar_papers = fetch_scholar_papers(SCHOLAR_ID, limit=limit, use_proxy=use_proxy)

    # Compare
    missing, matched = find_missing_papers(scholar_papers, known_titles)

    # Report
    report_results(missing, matched, scholar_papers)

    # Offer to add
    if missing and "--add" in sys.argv:
        offer_to_add(missing)


if __name__ == "__main__":
    main()
