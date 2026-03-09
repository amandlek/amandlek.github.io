#!/usr/bin/env python3
"""
build.py — Generate the publications section of index.html from papers.json.

Usage:
    python build.py              # Rebuild index.html from papers.json
    python build.py --check      # Check if index.html is up-to-date (no write)
    python build.py --dry-run    # Print generated HTML without writing
"""

import json
import re
import sys
import os

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PAPERS_JSON = "papers.json"
INDEX_HTML = "index.html"
BEGIN_MARKER = "<!-- BEGIN_PAPERS -->"
END_MARKER = "<!-- END_PAPERS -->"

# Indentation for generated HTML (matches existing style)
INDENT = "          "  # 10 spaces


# ---------------------------------------------------------------------------
# Author formatting
# ---------------------------------------------------------------------------

def format_authors(authors_str, self_name):
    """
    Convert plain-text author string to HTML.

    Markers:
        **Name**  →  not used (auto-detected via self_name)
        Name*     →  equal contribution (asterisk)
        Name†     →  equal advising (superscript dagger)

    The self_name is automatically bolded wherever it appears.
    """
    # Split authors by comma
    parts = [a.strip() for a in authors_str.split(",")]
    html_parts = []

    for part in parts:
        # Check for markers at end of name
        markers_suffix = ""
        clean = part

        # Remove ** wrapper if present (legacy format)
        is_bold = False
        if clean.startswith("**") and clean.endswith("**"):
            clean = clean[2:-2]
            is_bold = True

        # Extract trailing markers (†, *)
        trailing = ""
        while clean and clean[-1] in ("*", "†"):
            trailing = clean[-1] + trailing
            clean = clean[:-1]

        # Build HTML suffix for markers
        for ch in trailing:
            if ch == "*":
                markers_suffix += "*"
            elif ch == "†":
                markers_suffix += "<sup>&dagger;</sup>"

        # Check if this is the self author
        if clean == self_name or is_bold:
            html_parts.append(f"<strong>{clean}{markers_suffix}</strong>")
        else:
            html_parts.append(f"{clean}{markers_suffix}")

    return ", ".join(html_parts)


# ---------------------------------------------------------------------------
# Paper HTML generation
# ---------------------------------------------------------------------------

def markdown_links_to_html(text):
    """Convert markdown-style [text](url) links to HTML <a> tags."""
    return re.sub(
        r'\[([^\]]+)\]\(([^)]+)\)',
        r'<a href="\2">\1</a>',
        text
    )


def generate_paper_html(paper, self_name):
    """Generate HTML for a single paper entry."""
    pid = paper["id"]
    highlighted = paper.get("highlighted", False)
    thumbnail = paper.get("thumbnail", "")
    title = paper["title"]
    title_url = paper.get("title_url", "")
    authors_str = paper["authors"]
    venue = paper.get("venue", "")
    venue_note = paper.get("venue_note", "")
    year = paper.get("year", None)
    awards = paper.get("awards", [])
    links = paper.get("links", {})

    # Build bgcolor
    bgcolor = ' bgcolor="#ffffd0"' if highlighted else ""

    # Build authors HTML
    authors_html = format_authors(authors_str, self_name)

    # Build venue + year string
    # Format: <em>Venue</em> Year (Note)
    venue_year = ""
    if venue:
        venue_year = f"<em>{venue}</em>"
        if year:
            venue_year += f" {year}"
        if venue_note:
            venue_year += f" ({venue_note})"

    # Build links
    links_html = ""
    for label, url in links.items():
        links_html += f'\n{INDENT}    [<a href="{url}">{label}</a>]'

    # Build awards (supports markdown-style [text](url) links)
    awards_html = ""
    for award in awards:
        if isinstance(award, dict):
            text = award.get("text", "")
        else:
            text = award
        # Convert markdown links to HTML
        text_html = markdown_links_to_html(text)
        awards_html += f'\n{INDENT}    <p style="color:red; margin:0;">{text_html}</p>'

    # Build title link
    if title_url:
        title_html = f'<a href="{title_url}">\n{INDENT}      <span class="papertitle">{title}</span>\n{INDENT}    </a>'
    else:
        title_html = f'<span class="papertitle">{title}</span>'

    # Assemble the full paper entry
    html = f"""
{INDENT}<!-- {pid} -->
{INDENT}<tr{bgcolor}>
{INDENT}  <td style="padding:16px;width:20%;vertical-align:middle">
{INDENT}    <div class="one">
{INDENT}      <img src='{thumbnail}' width=100%>
{INDENT}    </div>
{INDENT}  </td>
{INDENT}  <td style="padding:8px;width:80%;vertical-align:middle">
{INDENT}    {title_html}
{INDENT}    <br>
{INDENT}    {authors_html}
{INDENT}    <br>
{INDENT}    {venue_year}"""

    if awards_html:
        html += f"\n{INDENT}    <br>"
        html += awards_html
        # Links follow directly after awards (no extra <br>)
        html += f"\n{INDENT}    {links_html.strip()}"
    else:
        html += f"\n{INDENT}    <br>{links_html}"

    html += f"""
{INDENT}    <p></p>
{INDENT}  </td>
{INDENT}</tr>"""

    return html


# ---------------------------------------------------------------------------
# Main build logic
# ---------------------------------------------------------------------------

def load_papers():
    """Load papers.json and return (settings, papers)."""
    with open(PAPERS_JSON, "r") as f:
        data = json.load(f)
    return data.get("settings", {}), data.get("papers", [])


def generate_all_papers_html(settings, papers):
    """Generate the full HTML block for all papers."""
    self_name = settings.get("self_name", "")
    parts = []
    current_section = None

    for paper in papers:
        section = paper.get("section", "publication")
        if section != current_section:
            section_label = "Preprints" if section == "preprint" else "Publications"
            parts.append(f"\n{INDENT}<!-- ===== {section_label} ===== -->\n")
            current_section = section
        parts.append(generate_paper_html(paper, self_name))

    return "\n".join(parts) + "\n"


def inject_into_html(papers_html):
    """Replace the content between BEGIN/END markers in index.html."""
    with open(INDEX_HTML, "r") as f:
        content = f.read()

    # Find markers
    begin_idx = content.find(BEGIN_MARKER)
    end_idx = content.find(END_MARKER)

    if begin_idx == -1:
        print(f"ERROR: Could not find '{BEGIN_MARKER}' in {INDEX_HTML}")
        sys.exit(1)
    if end_idx == -1:
        print(f"ERROR: Could not find '{END_MARKER}' in {INDEX_HTML}")
        sys.exit(1)

    # Replace content between markers (keep markers themselves)
    before = content[:begin_idx + len(BEGIN_MARKER)]
    after = content[end_idx:]

    new_content = before + "\n" + papers_html + INDENT + after

    return new_content


def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    check_only = "--check" in sys.argv
    dry_run = "--dry-run" in sys.argv

    # Load data
    settings, papers = load_papers()
    print(f"Loaded {len(papers)} papers from {PAPERS_JSON}")

    # Generate HTML
    papers_html = generate_all_papers_html(settings, papers)

    if dry_run:
        print("\n--- Generated HTML ---")
        print(papers_html)
        return

    # Inject into index.html
    new_content = inject_into_html(papers_html)

    if check_only:
        with open(INDEX_HTML, "r") as f:
            current = f.read()
        if current == new_content:
            print("✓ index.html is up-to-date")
        else:
            print("✗ index.html is out of date — run 'python build.py' to update")
            sys.exit(1)
        return

    # Write output
    with open(INDEX_HTML, "w") as f:
        f.write(new_content)

    highlighted = sum(1 for p in papers if p.get("highlighted"))
    print(f"✓ Generated {INDEX_HTML} with {len(papers)} papers ({highlighted} highlighted)")


if __name__ == "__main__":
    main()
