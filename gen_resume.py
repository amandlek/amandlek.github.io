#!/usr/bin/env python3
"""
gen_resume.py — Generate the "Selected Publications" section for your resume
from highlighted papers in papers.json.

Usage:
    python gen_resume.py              # Print plain text to terminal
    python gen_resume.py --rtf        # Generate resume_pubs.rtf (open in Pages)
    python gen_resume.py --txt        # Generate resume_pubs.txt
    python gen_resume.py --all        # Generate both .rtf and .txt

The RTF file preserves formatting (bold, italic, colored awards) and can
be opened directly in Pages — just copy the content into your resume.
"""

import json
import os
import re
import sys

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PAPERS_JSON = "papers.json"
OUTPUT_RTF = "resume_pubs.rtf"
OUTPUT_TXT = "resume_pubs.txt"

# Resume heading
HEADING = "Selected Publications (see website for full list)"

# RTF color table indices (defined in header):
#   0 = black, 1 = red (for awards)
# RTF font table: 0 = Helvetica

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_highlighted_papers():
    """Load papers.json and return only highlighted papers, in order."""
    with open(PAPERS_JSON, "r") as f:
        data = json.load(f)
    self_name = data["settings"]["self_name"]
    papers = [p for p in data["papers"] if p.get("highlighted")]
    return self_name, papers


# ---------------------------------------------------------------------------
# Author formatting (shared logic with build.py)
# ---------------------------------------------------------------------------

def parse_authors(authors_str, self_name):
    """
    Parse authors string into a list of (name, is_self, markers) tuples.

    Markers: * = equal contribution, † = equal advising
    """
    parts = [a.strip() for a in authors_str.split(",")]
    result = []

    for part in parts:
        clean = part

        # Remove ** wrapper if present
        is_bold = False
        if clean.startswith("**") and clean.endswith("**"):
            clean = clean[2:-2]
            is_bold = True

        # Extract trailing markers
        trailing = ""
        while clean and clean[-1] in ("*", "†"):
            trailing = clean[-1] + trailing
            clean = clean[:-1]

        is_self = (clean == self_name) or is_bold
        result.append((clean, is_self, trailing))

    return result


# ---------------------------------------------------------------------------
# Plain text output
# ---------------------------------------------------------------------------

def format_venue_text(paper):
    """Format venue + year as plain text."""
    venue = paper.get("venue", "")
    year = paper.get("year")
    venue_note = paper.get("venue_note", "")
    parts = []
    if venue:
        parts.append(venue)
    if year:
        parts.append(str(year))
    result = " ".join(parts)
    if venue_note:
        result += f" ({venue_note})"
    return result


def format_links_text(paper):
    """Format links as [label] [label] plain text."""
    links = paper.get("links", {})
    if not links:
        return ""
    return " ".join(f"[{label}]" for label in links)


def format_awards_text(paper):
    """Format awards as plain text (strip markdown links)."""
    awards = paper.get("awards", [])
    lines = []
    for award in awards:
        text = award.get("text", "") if isinstance(award, dict) else award
        # Strip markdown links: [text](url) -> text
        text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
        lines.append(text)
    return lines


def generate_plain_text(self_name, papers):
    """Generate the full plain-text publications section."""
    lines = [HEADING, ""]

    for paper in papers:
        authors = parse_authors(paper["authors"], self_name)
        authors_str = ", ".join(
            f"{name}{markers}" for name, is_self, markers in authors
        )

        venue = format_venue_text(paper)
        awards = format_awards_text(paper)
        links = format_links_text(paper)

        # Title
        lines.append(f"• {paper['title']}")
        # Authors
        lines.append(f"  {authors_str}")
        # Venue
        if venue:
            lines.append(f"  {venue}")
        # Awards
        for award in awards:
            lines.append(f"  {award}")
        # Links
        if links:
            lines.append(f"  {links}")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# RTF output (for Pages)
# ---------------------------------------------------------------------------

def rtf_escape(text):
    """Escape special RTF characters."""
    text = text.replace("\\", "\\\\")
    text = text.replace("{", "\\{")
    text = text.replace("}", "\\}")
    # Handle Unicode characters
    result = []
    for ch in text:
        code = ord(ch)
        if code > 127:
            result.append(f"\\u{code}?")
        else:
            result.append(ch)
    return "".join(result)


def rtf_bold(text):
    """Wrap text in RTF bold."""
    return f"\\b {rtf_escape(text)}\\b0 "


def rtf_italic(text):
    """Wrap text in RTF italic."""
    return f"\\i {rtf_escape(text)}\\i0 "


def rtf_superscript(text):
    """Wrap text in RTF superscript."""
    return f"{{\\super {rtf_escape(text)}}}"


def rtf_red(text):
    """Wrap text in red color (color index 1)."""
    return f"\\cf1 {rtf_escape(text)}\\cf0 "


def rtf_hyperlink(url, display_text, bold=False):
    """Create a clickable RTF hyperlink. Optionally bold the display text."""
    escaped_text = rtf_escape(display_text)
    if bold:
        escaped_text = f"\\b {escaped_text}\\b0 "
    # Use RTF field for clickable hyperlink; color index 2 = blue
    return (
        f"{{\\field{{\\*\\fldinst{{HYPERLINK \"{url}\"}}}}"
        f"{{\\fldrslt \\cf2 {escaped_text}}}}}"
    )


def rtf_red_with_link(text):
    """
    Format award text in red, converting markdown links to clickable
    RTF hyperlinks (in red).
    """
    # Find markdown links: [text](url)
    parts = re.split(r'(\[[^\]]+\]\([^)]+\))', text)
    result = "\\b \\cf1 "
    for part in parts:
        m = re.match(r'\[([^\]]+)\]\(([^)]+)\)', part)
        if m:
            link_text, url = m.group(1), m.group(2)
            # Red bold clickable link
            result += (
                f"{{\\field{{\\*\\fldinst{{HYPERLINK \"{url}\"}}}}"
                f"{{\\fldrslt \\b \\cf1 {rtf_escape(link_text)}\\b0 }}}}"
            )
        else:
            result += rtf_escape(part)
    result += "\\cf0 \\b0 "
    return result


def format_links_rtf(paper):
    """Format links as clickable RTF hyperlinks: [label] [label] ..."""
    links = paper.get("links", {})
    if not links:
        return ""
    parts = []
    for label, url in links.items():
        parts.append(rtf_hyperlink(url, f"[{label}]"))
    return " ".join(parts)


def format_author_rtf(name, is_self, markers):
    """Format a single author with optional bold and superscript markers."""
    escaped_name = rtf_escape(name)
    # Build marker string with superscript
    marker_rtf = ""
    if markers:
        marker_rtf = rtf_superscript(markers)

    if is_self:
        return f"\\b {escaped_name}\\b0 {marker_rtf}"
    else:
        return f"{escaped_name}{marker_rtf}"


def generate_rtf(self_name, papers):
    """Generate RTF content for the publications section."""

    # RTF header
    # Font table: 0 = Times New Roman
    # Color table: 0 = auto (black), 1 = red (awards), 2 = blue (links)
    header = (
        "{\\rtf1\\ansi\\deff0\n"
        "{\\fonttbl"
        "{\\f0\\froman Times New Roman;}"
        "}\n"
        "{\\colortbl;"
        "\\red220\\green53\\blue69;"   # index 1 = salmon red (awards)
        "\\red0\\green0\\blue200;"     # index 2 = blue (links)
        "}\n"
        "\\f0\\fs22\n"  # default font: Times New Roman 11pt (fs22 = 11pt)
    )

    # Heading
    body = f"\\pard\\qc\\sb200\\sa100\\fs28\\b {rtf_escape(HEADING)}\\b0\\fs22\\par\n"
    body += "\\pard\\ql\\sa0\\sb0\n"

    for paper in papers:
        authors = parse_authors(paper["authors"], self_name)
        venue = format_venue_text(paper)
        awards_list = format_awards_text(paper)
        links_rtf = format_links_rtf(paper)

        # Bullet + Title (italic)
        body += f"\\pard\\li360\\fi-180\\sb120\\sa0 \\bullet  "
        body += rtf_italic(paper["title"])
        body += "\\line\n"

        # Authors (self name in bold, markers as superscript)
        author_parts = []
        for name, is_self, markers in authors:
            author_parts.append(format_author_rtf(name, is_self, markers))
        body += ", ".join(author_parts)
        body += "\\line\n"

        # Venue (bold)
        if venue:
            body += rtf_bold(venue)
            body += "\\line\n"

        # Awards (red, with clickable links)
        for award in awards_list:
            body += rtf_red_with_link(award)
            body += "\\line\n"

        # Links (clickable hyperlinks)
        if links_rtf:
            body += links_rtf
            body += "\\line\n"

        body += "\\par\n"

    footer = "}"
    return header + body + footer


# ---------------------------------------------------------------------------
# Clipboard helper (macOS)
# ---------------------------------------------------------------------------

def copy_to_clipboard(text):
    """Copy text to macOS clipboard."""
    try:
        import subprocess
        process = subprocess.Popen(
            ["pbcopy"], stdin=subprocess.PIPE, env={"LANG": "en_US.UTF-8"}
        )
        process.communicate(text.encode("utf-8"))
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    if "--help" in sys.argv or "-h" in sys.argv:
        print(__doc__)
        return

    self_name, papers = load_highlighted_papers()
    print(f"Found {len(papers)} highlighted papers\n")

    gen_rtf = "--rtf" in sys.argv or "--all" in sys.argv
    gen_txt = "--txt" in sys.argv or "--all" in sys.argv
    gen_any = gen_rtf or gen_txt

    # Always print plain text to terminal
    plain = generate_plain_text(self_name, papers)
    print(plain)

    if gen_rtf:
        rtf = generate_rtf(self_name, papers)
        with open(OUTPUT_RTF, "w") as f:
            f.write(rtf)
        print(f"✓ Generated {OUTPUT_RTF} (open in Pages to copy formatted text)")

    if gen_txt:
        with open(OUTPUT_TXT, "w") as f:
            f.write(plain)
        print(f"✓ Generated {OUTPUT_TXT}")

    if not gen_any:
        # Copy to clipboard for easy paste
        if copy_to_clipboard(plain):
            print("✓ Plain text copied to clipboard (⌘V to paste into Pages)")
        else:
            print("  (Tip: use --rtf to generate a formatted file for Pages)")


if __name__ == "__main__":
    main()
