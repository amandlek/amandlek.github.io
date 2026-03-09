#!/usr/bin/env python3
"""
add_paper.py — Add a new paper entry to papers.json.

Usage:
    python add_paper.py --arxiv 2505.24853         # Auto-fetch from arXiv
    python add_paper.py --arxiv 2505.24853 --build  # Fetch + rebuild site
    python add_paper.py                              # Interactive mode
    python add_paper.py --show                       # Show current papers list

The script fetches metadata from arXiv (title, authors, abstract) and tries
to find thumbnail images from project websites. You fill in the rest
(thumbnail path, links, highlight status, etc.).
"""

import json
import os
import re
import sys
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urljoin

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PAPERS_JSON = "papers.json"
ARXIV_API = "http://export.arxiv.org/api/query?id_list={}"
ASSETS_DIR = "assets"


# ---------------------------------------------------------------------------
# arXiv API
# ---------------------------------------------------------------------------

def fetch_arxiv(arxiv_id):
    """Fetch paper metadata from the arXiv API."""
    # Clean arxiv ID (handle full URLs)
    arxiv_id = arxiv_id.strip()
    for prefix in ["https://arxiv.org/abs/", "http://arxiv.org/abs/",
                    "https://arxiv.org/pdf/", "http://arxiv.org/pdf/"]:
        if arxiv_id.startswith(prefix):
            arxiv_id = arxiv_id[len(prefix):]
    arxiv_id = arxiv_id.rstrip("/").replace(".pdf", "")

    url = ARXIV_API.format(arxiv_id)
    print(f"Fetching arXiv metadata for: {arxiv_id}")

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "add_paper/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read()
    except (urllib.error.URLError, TimeoutError) as e:
        print(f"  ERROR: Could not fetch arXiv data: {e}")
        return None

    root = ET.fromstring(data)
    ns = {"atom": "http://www.w3.org/2005/Atom"}

    entry = root.find("atom:entry", ns)
    if entry is None:
        print("  ERROR: No entry found in arXiv response")
        return None

    title = entry.findtext("atom:title", "", ns).strip()
    title = re.sub(r"\s+", " ", title)  # normalize whitespace

    # Get authors
    authors = []
    for author in entry.findall("atom:author", ns):
        name = author.findtext("atom:name", "", ns).strip()
        authors.append(name)

    # Get abstract (first paragraph)
    abstract = entry.findtext("atom:summary", "", ns).strip()

    # Get links
    pdf_url = f"https://arxiv.org/abs/{arxiv_id}"

    print(f"  Title: {title}")
    print(f"  Authors: {', '.join(authors[:5])}{'...' if len(authors) > 5 else ''}")

    return {
        "arxiv_id": arxiv_id,
        "title": title,
        "authors": authors,
        "abstract": abstract,
        "arxiv_url": pdf_url,
    }


# ---------------------------------------------------------------------------
# Paper ID generation
# ---------------------------------------------------------------------------

def generate_paper_id(title):
    """Generate a short paper ID from the title (lowercase for consistent paths)."""
    # If title has a colon, use the part before it
    if ":" in title:
        short = title.split(":")[0].strip()
    else:
        short = " ".join(title.split()[:3])
    # Clean: keep alphanumeric, replace spaces with hyphens, lowercase
    paper_id = re.sub(r'[^a-zA-Z0-9\s-]', '', short)
    paper_id = re.sub(r'\s+', '-', paper_id.strip())
    paper_id = paper_id.lower()
    # Truncate
    if len(paper_id) > 40:
        paper_id = paper_id[:40].rstrip('-')
    return paper_id


# ---------------------------------------------------------------------------
# arXiv HTML helpers (for author markers & figure extraction)
# ---------------------------------------------------------------------------

def fetch_arxiv_html(arxiv_id):
    """
    Fetch the arXiv HTML rendering (ar5iv / latexml) of a paper.
    Returns (html_string, final_url) or (None, None).
    """
    url = f"https://arxiv.org/html/{arxiv_id}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "add_paper/1.0"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.read().decode("utf-8", errors="ignore"), resp.url
    except Exception as e:
        print(f"  (Could not fetch arXiv HTML: {e})")
        return None, None


def _get_author_block(html):
    """Extract just the author block from arXiv HTML to avoid false matches."""
    # Look for ltx_authors div
    start = html.find('class="ltx_authors"')
    if start == -1:
        start = html.find('ltx_authors')
    if start == -1:
        return html[:15000]  # fallback: use first 15k chars

    # Find the end of the author block (next major section or abstract)
    end = len(html)
    for marker in ['class="ltx_abstract"', 'class="ltx_section"',
                    'class="ltx_para"', '<section', 'id="S1"']:
        idx = html.find(marker, start + 100)
        if idx != -1 and idx < end:
            end = idx
    return html[max(0, start - 200):end]


def _extract_sup_content(author_block, name, ambiguous_last_names=None):
    """
    Extract the full superscript content for an author name, handling
    arXiv HTML's nested <span>, <math>, and LaTeX notation.

    Searches within the author block only to avoid false matches in the
    paper body. Skips last-name-only fallback if the last name is shared
    by another author (to avoid misattribution when arXiv API and HTML
    use different name orderings, e.g. "Yen-Chen Lin" vs "Lin Yen-Chen").

    Returns a flat string of all marker characters (e.g. "1,2,*,†").
    """
    if ambiguous_last_names is None:
        ambiguous_last_names = set()

    # Build list of name variants to try
    parts = name.split()
    last_name = parts[-1] if parts else name
    first_name = parts[0] if len(parts) > 1 else ""

    candidates = [name]
    # Try reversed name order (handles "Yen-Chen Lin" vs "Lin Yen-Chen")
    if len(parts) >= 2:
        reversed_name = f"{last_name} {' '.join(parts[:-1])}"
        candidates.append(reversed_name)
    # Only fall back to last name if it's unambiguous
    if last_name != name and last_name not in ambiguous_last_names:
        candidates.append(last_name)

    sup_html = None
    for candidate in candidates:
        escaped = re.escape(candidate)
        sup_match = re.search(
            rf'{escaped}\s*<sup[^>]*>(.*?)</sup>',
            author_block, re.DOTALL
        )
        if sup_match:
            sup_html = sup_match.group(1)
            break

    if not sup_html:
        return ""

    # Extract all text content, stripping tags
    text = re.sub(r'<[^>]+>', ' ', sup_html)
    # Also grab any \dagger from LaTeX annotations
    if '\\dagger' in sup_html or '†' in sup_html:
        text += ' †'
    if '*' in sup_html or '∗' in sup_html or '⋆' in sup_html:
        text += ' *'

    return text


def infer_author_markers(html, authors_list):
    """
    Best-effort inference of equal contribution (*) and equal advising (†)
    markers from the arXiv HTML rendering.

    Strategy:
      1. Look for textual evidence of "equal contribution" / "equal advising"
         in footnotes or text.
      2. Parse per-author superscript markers from the HTML, handling both
         plain text and LaTeX math notation (e.g. \\dagger, <math>†</math>).
      3. Fall back to heuristics: scan from front/back of the author list
         to find the boundary where markers stop appearing.

    Returns the authors string with markers appended.
    """
    if not html:
        return ", ".join(authors_list)

    # Step 1: Detect whether equal contribution / equal advising exist
    has_ec = bool(re.search(
        r'(?:equal\s+contribution|contributed\s+equally|equal\s+contributions)',
        html, re.IGNORECASE
    ))
    has_ea = bool(re.search(
        r'(?:equal\s+advising|co-?senior|co-?last|joint\s+(?:senior|last)|equal\s+supervision|project\s+lead)',
        html, re.IGNORECASE
    ))

    if not has_ec and not has_ea:
        return ", ".join(authors_list)

    detected = []
    if has_ec:
        detected.append("equal contribution")
    if has_ea:
        detected.append("equal advising")
    print(f"  Auto-detected: {', '.join(detected)}")

    # Step 2: Parse per-author markers from the author block only
    ec_authors = set()
    ea_authors = set()
    author_block = _get_author_block(html)

    # Detect ambiguous last names (shared by multiple authors)
    last_names = [n.split()[-1] if n.split() else n for n in authors_list]
    from collections import Counter
    ln_counts = Counter(last_names)
    ambiguous_last_names = {ln for ln, cnt in ln_counts.items() if cnt > 1}

    for name in authors_list:
        sup_text = _extract_sup_content(author_block, name, ambiguous_last_names)
        if not sup_text:
            continue
        # Check for equal contribution markers: *, ∗, ⋆
        if has_ec and any(c in sup_text for c in ['*', '∗', '⋆']):
            ec_authors.add(name)
        # Check for equal advising markers: †, ‡, §, or \dagger
        if has_ea and any(c in sup_text for c in ['†', '‡', '§']):
            ea_authors.add(name)

    # Step 3: Fallback heuristics — scan from the edges of the author list
    # to find natural groups (first N for equal contrib, last N for advising)
    if has_ec and not ec_authors:
        # Guess: contiguous block from the start
        for name in authors_list:
            sup_text = _extract_sup_content(author_block, name, ambiguous_last_names)
            if sup_text and any(c in sup_text for c in ['*', '∗', '⋆']):
                ec_authors.add(name)
            else:
                break
        if not ec_authors:
            # Last resort: assume first 2
            ec_authors = set(authors_list[:2])
        print(f"  (Guessing equal contribution for: {', '.join(n for n in authors_list if n in ec_authors)})")

    if has_ea and not ea_authors:
        # Guess: contiguous block from the end
        for name in reversed(authors_list):
            sup_text = _extract_sup_content(author_block, name, ambiguous_last_names)
            if sup_text and any(c in sup_text for c in ['†', '‡', '§']):
                ea_authors.add(name)
            else:
                break
        if not ea_authors:
            # Last resort: assume last 2
            ea_authors = set(authors_list[-2:])
        print(f"  (Guessing equal advising for: {', '.join(n for n in authors_list if n in ea_authors)})")

    if ec_authors:
        print(f"  Equal contribution ({len(ec_authors)}): {', '.join(n for n in authors_list if n in ec_authors)}")
    if ea_authors:
        print(f"  Equal advising ({len(ea_authors)}): {', '.join(n for n in authors_list if n in ea_authors)}")

    # Build author string with markers
    result = []
    for name in authors_list:
        suffix = ""
        if name in ec_authors:
            suffix += "*"
        if name in ea_authors:
            suffix += "†"
        result.append(f"{name}{suffix}")

    marked_str = ", ".join(result)
    return marked_str


def fetch_figure1_url(html, base_url):
    """
    Extract the URL of the first figure image from arXiv HTML rendering.
    Returns an absolute URL string, or None.
    """
    if not html or not base_url:
        return None

    # Ensure base_url ends with '/' so relative paths resolve correctly
    # e.g. https://arxiv.org/html/2505.12705 + x1.png -> .../html/x1.png (WRONG)
    #      https://arxiv.org/html/2505.12705/ + x1.png -> .../html/2505.12705/x1.png (CORRECT)
    if not base_url.endswith("/"):
        base_url = base_url + "/"

    # Strategy 1: Find <figure> elements with <img> tags
    figures = re.finditer(
        r'<figure\b[^>]*>(.*?)</figure>',
        html, re.DOTALL | re.IGNORECASE
    )
    for fig in figures:
        fig_content = fig.group(1)
        img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', fig_content)
        if not img_match:
            continue
        img_src = img_match.group(1)
        # Skip SVGs and tiny images
        if img_src.lower().endswith('.svg'):
            continue
        if any(skip in img_src.lower() for skip in ["logo", "icon", "badge", "favicon"]):
            continue
        return urljoin(base_url, img_src)

    # Strategy 2: Find images that look like paper figures (outside <figure> tags)
    img_matches = re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', html)
    for img_src in img_matches:
        if img_src.lower().endswith('.svg'):
            continue
        if any(skip in img_src.lower() for skip in ["logo", "icon", "badge", "favicon", "ltx_", "ar5iv"]):
            continue
        if any(hint in img_src.lower() for hint in ["extract", "figure", "fig", ".png", ".jpg", ".jpeg"]):
            return urljoin(base_url, img_src)

    return None


# ---------------------------------------------------------------------------
# Thumbnail helpers
# ---------------------------------------------------------------------------

def suggest_thumbnail_urls(title_url=None, arxiv_id=None):
    """Suggest possible thumbnail URLs from project websites."""
    suggestions = []

    if title_url:
        # Try to fetch og:image from the project page
        try:
            req = urllib.request.Request(title_url, headers={"User-Agent": "add_paper/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                html = resp.read().decode("utf-8", errors="ignore")

            # Look for og:image
            og_match = re.search(r'<meta\s+(?:property|name)="og:image"\s+content="([^"]+)"', html, re.IGNORECASE)
            if not og_match:
                og_match = re.search(r'content="([^"]+)"\s+(?:property|name)="og:image"', html, re.IGNORECASE)
            if og_match:
                img_url = og_match.group(1)
                if not img_url.startswith("http"):
                    img_url = urljoin(title_url, img_url)
                suggestions.append(("og:image from project page", img_url))

            # Look for first prominent image
            img_matches = re.findall(r'<img[^>]+src="([^"]+)"', html)
            for img in img_matches[:3]:
                if any(skip in img.lower() for skip in ["logo", "icon", "avatar", "badge", "button"]):
                    continue
                if not img.startswith("http"):
                    img = urljoin(title_url, img)
                suggestions.append(("image from project page", img))

        except Exception as e:
            print(f"  (Could not fetch project page for thumbnails: {e})")

    if arxiv_id:
        suggestions.append(("arXiv paper page", f"https://arxiv.org/abs/{arxiv_id}"))

    return suggestions


def download_thumbnail(url, paper_id):
    """Download a thumbnail image to assets/<paper_id>/thumbnail.<ext>."""
    # Determine extension
    ext = "png"
    for e in ["jpg", "jpeg", "gif", "png", "webp"]:
        if url.lower().endswith(f".{e}"):
            ext = e
            break

    dest_dir = os.path.join(ASSETS_DIR, paper_id)
    os.makedirs(dest_dir, exist_ok=True)
    dest_path = os.path.join(dest_dir, f"thumbnail.{ext}")

    print(f"  Downloading thumbnail to {dest_path}...")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "add_paper/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            with open(dest_path, "wb") as f:
                f.write(resp.read())
        print(f"  ✓ Saved to {dest_path}")
        return dest_path
    except Exception as e:
        print(f"  ERROR downloading thumbnail: {e}")
        return None


# ---------------------------------------------------------------------------
# Interactive helpers
# ---------------------------------------------------------------------------

def prompt(msg, default=""):
    """Prompt for input with optional default."""
    if default:
        result = input(f"  {msg} [{default}]: ").strip()
        return result if result else default
    else:
        return input(f"  {msg}: ").strip()


def prompt_yn(msg, default=True):
    """Prompt for yes/no. Default is shown in uppercase."""
    if default:
        suffix = "[Y/n]"
    else:
        suffix = "[y/N] (press Enter for No)"
    result = input(f"  {msg} {suffix}: ").strip().lower()
    if not result:
        return default
    return result in ("y", "yes")


def prompt_links():
    """Interactively collect paper links."""
    links = {}
    print("  Enter links (empty label to finish):")
    while True:
        label = input("    Link label (e.g., arXiv, website, code, video, blog): ").strip()
        if not label:
            break
        url = input(f"    URL for '{label}': ").strip()
        if url:
            links[label] = url
    return links


def prompt_awards():
    """Interactively collect awards."""
    awards = []
    print("  Enter awards (empty to finish). Use [text](url) for linked portions:")
    while True:
        text = input("    Award text: ").strip()
        if not text:
            break
        awards.append({"text": text})
    return awards


# ---------------------------------------------------------------------------
# Main add flow
# ---------------------------------------------------------------------------

def load_papers():
    """Load papers.json."""
    with open(PAPERS_JSON, "r") as f:
        return json.load(f)


def save_papers(data):
    """Save papers.json."""
    with open(PAPERS_JSON, "w") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    print(f"✓ Saved to {PAPERS_JSON}")


def show_papers():
    """Display current papers list."""
    data = load_papers()
    papers = data.get("papers", [])
    print(f"\nCurrent papers ({len(papers)} total):\n")
    current_section = None
    for i, p in enumerate(papers):
        section = p.get("section", "publication")
        if section != current_section:
            label = "PREPRINTS" if section == "preprint" else "PUBLICATIONS"
            print(f"  --- {label} ---")
            current_section = section
        marker = "★" if p.get("highlighted") else " "
        year = p.get("year", "")
        print(f"  {marker} {i:3d}. [{p['id']}] {p['title'][:65]} ({year})")
    print()


def add_from_arxiv(arxiv_id, auto_build=False):
    """
    Add a paper by fetching metadata from arXiv (minimal prompts).

    Only 3 interactive prompts:
      1. Duplicate check (if paper ID already exists)
      2. Whether to highlight the paper
      3. Thumbnail selection

    Everything else is auto-populated with sensible defaults.
    Edit papers.json afterwards to refine (venue, links, title_url, etc.).
    """
    arxiv_data = fetch_arxiv(arxiv_id)
    if not arxiv_data:
        sys.exit(1)

    data = load_papers()
    self_name = data["settings"]["self_name"]

    # Auto-generate paper ID from title
    paper_id = generate_paper_id(arxiv_data["title"])
    print(f"  Paper ID: {paper_id}")

    # --- PROMPT 1: Duplicate check ---
    existing_ids = {p["id"] for p in data["papers"]}
    if paper_id in existing_ids:
        print(f"  WARNING: Paper ID '{paper_id}' already exists!")
        if not prompt_yn("Continue anyway?", False):
            return

    # Fetch arXiv HTML for author marker detection and Figure 1 thumbnail
    print("\n  Fetching arXiv HTML for auto-detection...")
    html, html_url = fetch_arxiv_html(arxiv_data["arxiv_id"])

    # Auto-infer equal contribution / equal advising markers
    authors_str = infer_author_markers(html, arxiv_data["authors"])
    if self_name not in authors_str:
        print(f"  NOTE: '{self_name}' not found in author list — remember to check.")

    # --- PROMPT 2: Highlight ---
    highlighted = prompt_yn("Highlight this paper?", False)

    # --- PROMPT 3: Thumbnail ---
    print(f"\n  --- Thumbnail ---")
    thumbnail_path = ""
    suggestions = []

    # Try Figure 1 from arXiv HTML
    fig1_url = fetch_figure1_url(html, html_url)
    if fig1_url:
        suggestions.append(("Figure 1 from arXiv HTML", fig1_url))

    # Also show arXiv page link for reference
    suggestions.append(("arXiv paper page (not an image)", f"https://arxiv.org/abs/{arxiv_data['arxiv_id']}"))

    if suggestions:
        print("  Thumbnail options:")
        for i, (desc, url) in enumerate(suggestions):
            display_url = url if len(url) < 80 else url[:77] + "..."
            print(f"    {i+1}. {desc}: {display_url}")
        default_choice = "1" if fig1_url else "skip"
        choice = prompt("Download which? (number, or 'skip')", default_choice)
        if choice.isdigit() and 1 <= int(choice) <= len(suggestions):
            url = suggestions[int(choice) - 1][1]
            thumbnail_path = download_thumbnail(url, paper_id) or ""

    if not thumbnail_path:
        thumbnail_path = f"assets/{paper_id}/thumbnail.png"
        print(f"  Using placeholder path: {thumbnail_path}")
        print(f"  (Add the actual image file later)")

    # Build entry with defaults
    paper = {
        "id": paper_id,
        "title": arxiv_data["title"],
        "title_url": "",
        "authors": authors_str,
        "venue": "Under Review",
        "year": None,
        "thumbnail": thumbnail_path,
        "highlighted": highlighted,
        "awards": [],
        "links": {
            "arXiv": f"https://arxiv.org/abs/{arxiv_data['arxiv_id']}"
        },
        "section": "preprint",
    }

    # Show summary
    print(f"\n--- Paper Entry ---")
    print(json.dumps(paper, indent=4, ensure_ascii=False))

    # Insert at top of preprints section
    insert_idx = 0
    for i, p in enumerate(data["papers"]):
        if p.get("section") == "preprint":
            insert_idx = i
            break
    data["papers"].insert(insert_idx, paper)
    save_papers(data)

    # Auto-rebuild
    print("\n  Rebuilding index.html...")
    os.system("python3 build.py")

    print("\n  TIP: Edit papers.json to refine venue, title_url, links, etc.")


def add_interactive():
    """Add a paper interactively (no arXiv)."""
    data = load_papers()
    self_name = data["settings"]["self_name"]

    print("\n--- Add Paper (Interactive Mode) ---\n")

    paper_id = prompt("Paper ID (short identifier)")
    title = prompt("Title")
    print(f"  Enter authors separated by commas.")
    print(f"  Use * for equal contribution, † for equal advising.")
    print(f"  '{self_name}' will be auto-bolded.")
    authors = prompt("Authors")

    venue = prompt("Venue (e.g., CoRL, ICRA, Under Review)")
    year = prompt("Year (or empty)")
    year = int(year) if year else None
    venue_note = prompt("Venue note (or empty)", "")
    section = prompt("Section (preprint / publication)", "preprint" if venue == "Under Review" else "publication")
    highlighted = prompt_yn("Highlight this paper?", False)
    title_url = prompt("Title URL (project page, or empty)", "")

    print("\n  Links:")
    links = prompt_links()
    if title_url and "website" not in links:
        links["website"] = title_url

    thumbnail_path = prompt("Thumbnail path", f"assets/{paper_id}/thumbnail.png")
    awards = prompt_awards()

    paper = {
        "id": paper_id,
        "title": title,
        "title_url": title_url,
        "authors": authors,
        "venue": venue,
        "year": year,
        "thumbnail": thumbnail_path,
        "highlighted": highlighted,
        "awards": awards,
        "links": links,
        "section": section,
    }
    if venue_note:
        paper["venue_note"] = venue_note

    print(f"\n--- Paper Summary ---")
    print(json.dumps(paper, indent=4, ensure_ascii=False))

    if prompt_yn("\nAdd this paper?", True):
        insert_idx = 0
        for i, p in enumerate(data["papers"]):
            if p.get("section") == section:
                insert_idx = i
                break
        data["papers"].insert(insert_idx, paper)
        save_papers(data)

        if prompt_yn("Rebuild index.html now?", True):
            os.system("python3 build.py")
    else:
        print("Cancelled.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    if "--show" in sys.argv:
        show_papers()
        return

    if "--help" in sys.argv or "-h" in sys.argv:
        print(__doc__)
        return

    arxiv_id = None
    auto_build = "--build" in sys.argv

    for i, arg in enumerate(sys.argv[1:], 1):
        if arg == "--arxiv" and i < len(sys.argv) - 1:
            arxiv_id = sys.argv[i + 1]

    if arxiv_id:
        add_from_arxiv(arxiv_id, auto_build)
    else:
        add_interactive()


if __name__ == "__main__":
    main()
