#!/usr/bin/env python3
"""Generate the complete website resume PDF from papers.json.

Usage:
    python gen_resume_pdf.py
    python gen_resume_pdf.py --website
    python gen_resume_pdf.py --output path/to/Resume.pdf

The selected publications are the entries marked ``highlighted`` in
papers.json. ``--website`` also refreshes assets/resume/Resume.pdf.
"""

import argparse
import html
import os
import re
import shutil
import sys

from gen_resume import (
    format_awards_text,
    format_venue_text,
    load_highlighted_papers,
    parse_authors,
)

try:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import (
        HRFlowable,
        KeepTogether,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
    )
except ImportError:
    print("reportlab is required: python -m pip install reportlab", file=sys.stderr)
    sys.exit(1)


DEFAULT_OUTPUT = "output/pdf/Resume.pdf"
WEBSITE_OUTPUT = "assets/resume/Resume.pdf"
FONT_DIR = "/System/Library/Fonts/Supplemental"

SELECTED_TALKS = [
    {
        "title": "Removing the Barriers to Simulation Adoption with Automated Environment Construction and Synthetic Data Generation",
        "title_url": "https://youtu.be/cPFO9-W3J18",
        "venue": "ICRA 2026 Generative Digital Twins Workshop",
        "venue_url": "https://awesomedigitaltwin.github.io/2026_ICRA.html",
        "date": "June 2026",
    },
    {
        "title": "Scaling Synthetic Data Generation for Robotics with Point-Based Representations",
        "title_url": "https://youtu.be/L_45qnUVhEM?si=Sz93LPF-dRbGNwKL&t=3982",
        "venue": "CoRL 2025 GenPriors Workshop",
        "venue_url": "https://corl25-genpriors.github.io/",
        "date": "September 2025",
    },
    {
        "title": "Moving from Data Collection to Data Generation: Addressing the Need for Data in Robotics",
        "title_url": "https://cornell.box.com/s/s8k3ocn6fko97h1xv6xr22186gvjuk9j",
        "venue": "Cornell Robotics Seminar",
        "venue_url": "https://www.cs.cornell.edu/events/robotics-seminar",
        "date": "December 2024",
    },
]


def ascii_hyphens(text):
    """Normalize dash-like Unicode characters to an ASCII hyphen."""
    return str(text).translate(str.maketrans({"–": "-", "—": "-", "‑": "-", "−": "-"}))


def register_fonts():
    """Register the Times New Roman family used by the existing resume."""
    font_files = {
        "ResumeTimes": "Times New Roman.ttf",
        "ResumeTimes-Bold": "Times New Roman Bold.ttf",
        "ResumeTimes-Italic": "Times New Roman Italic.ttf",
        "ResumeTimes-BoldItalic": "Times New Roman Bold Italic.ttf",
    }
    for name, filename in font_files.items():
        path = os.path.join(FONT_DIR, filename)
        if not os.path.exists(path):
            raise FileNotFoundError(f"Missing resume font: {path}")
        pdfmetrics.registerFont(TTFont(name, path))
    pdfmetrics.registerFontFamily(
        "ResumeTimes",
        normal="ResumeTimes",
        bold="ResumeTimes-Bold",
        italic="ResumeTimes-Italic",
        boldItalic="ResumeTimes-BoldItalic",
    )


def esc(text):
    return html.escape(ascii_hyphens(text), quote=True)


def author_markup(paper, self_name):
    authors = []
    for name, is_self, markers in parse_authors(paper["authors"], self_name):
        formatted = esc(name)
        if is_self:
            formatted = f"<b>{formatted}</b>"
        if markers:
            formatted += f'<super rise="3" size="7">{esc(markers)}</super>'
        authors.append(formatted)
    return ", ".join(authors)


def award_markup(award):
    """Convert the resume's markdown-style award links to PDF markup."""
    text = ascii_hyphens(award)
    parts = re.split(r"(\[[^\]]+\]\([^)]+\))", text)
    result = []
    for part in parts:
        match = re.fullmatch(r"\[([^\]]+)\]\(([^)]+)\)", part)
        if match:
            label, url = match.groups()
            result.append(f'<a href="{esc(url)}" color="#dc3545">{esc(label)}</a>')
        else:
            result.append(esc(part))
    return "".join(result)


def paper_flowables(paper, self_name, styles):
    title = Paragraph(
        f"<i>{esc(paper['title'])}</i>",
        styles["PublicationTitle"],
        bulletText="•",
    )
    items = [title, Paragraph(author_markup(paper, self_name), styles["PublicationBody"])]

    venue = format_venue_text(paper)
    if venue:
        items.append(Paragraph(f"<b>{esc(venue)}</b>", styles["PublicationBody"]))

    for award in format_awards_text(paper):
        items.append(
            Paragraph(
                f'<font color="#dc3545"><b>{award_markup(award)}</b></font>',
                styles["PublicationBody"],
            )
        )

    links = []
    for label, url in paper.get("links", {}).items():
        links.append(f'<a href="{esc(url)}" color="#0000cc">[{esc(label)}]</a>')
    if links:
        items.append(Paragraph(" ".join(links), styles["PublicationBody"]))

    items.append(Spacer(1, 5.5))
    return KeepTogether(items)


def talk_flowable(talk, styles):
    """Format one selected talk with clickable title and venue links."""
    markup = (
        f'<i><a href="{esc(talk["title_url"])}" color="#0000cc">'
        f'&ldquo;{esc(talk["title"])}&rdquo;</a></i> - '
        f'<a href="{esc(talk["venue_url"])}" color="#0000cc">'
        f'{esc(talk["venue"])}</a>, {esc(talk["date"])}'
    )
    return Paragraph(markup, styles["ResumeBullet"], bulletText="•")


def build_styles():
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            "ResumeName",
            parent=styles["Normal"],
            fontName="ResumeTimes-Bold",
            fontSize=16,
            leading=17,
            alignment=TA_CENTER,
            spaceAfter=0,
        )
    )
    styles.add(
        ParagraphStyle(
            "ResumeContact",
            parent=styles["Normal"],
            fontName="ResumeTimes",
            fontSize=9.5,
            leading=10.5,
            alignment=TA_CENTER,
            spaceAfter=0,
        )
    )
    styles.add(
        ParagraphStyle(
            "ResumeSection",
            parent=styles["Heading2"],
            fontName="ResumeTimes-Bold",
            fontSize=14,
            leading=16,
            alignment=TA_CENTER,
            spaceBefore=10,
            spaceAfter=9,
            keepWithNext=True,
        )
    )
    styles.add(
        ParagraphStyle(
            "ResumeBody",
            parent=styles["Normal"],
            fontName="ResumeTimes",
            fontSize=10.25,
            leading=12.25,
            alignment=TA_JUSTIFY,
            spaceAfter=7,
        )
    )
    styles.add(
        ParagraphStyle(
            "PublicationTitle",
            parent=styles["Normal"],
            fontName="ResumeTimes",
            fontSize=9.5,
            leading=10.7,
            leftIndent=12,
            firstLineIndent=0,
            bulletIndent=0,
            spaceAfter=0,
        )
    )
    styles.add(
        ParagraphStyle(
            "PublicationBody",
            parent=styles["Normal"],
            fontName="ResumeTimes",
            fontSize=9.5,
            leading=10.7,
            leftIndent=12,
            alignment=TA_LEFT,
            spaceAfter=0,
        )
    )
    styles.add(
        ParagraphStyle(
            "ResumeBullet",
            parent=styles["Normal"],
            fontName="ResumeTimes",
            fontSize=10.25,
            leading=12.25,
            leftIndent=12,
            bulletIndent=0,
            spaceAfter=2,
        )
    )
    return styles


def build_resume(output_path):
    register_fonts()
    styles = build_styles()
    self_name, papers = load_highlighted_papers()
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        rightMargin=0.72 * inch,
        leftMargin=0.72 * inch,
        topMargin=0.58 * inch,
        bottomMargin=0.55 * inch,
        title="Ajay Mandlekar - Resume",
        author="Ajay Mandlekar",
        subject="Research resume",
    )

    story = [
        Paragraph("Ajay Mandlekar", styles["ResumeName"]),
        Paragraph(
            '<b>Email:</b> <a href="mailto:amandlekar@nvidia.com" color="#000000">amandlekar@nvidia.com</a>',
            styles["ResumeContact"],
        ),
        Paragraph(
            '<b>Website:</b> <a href="http://ai.stanford.edu/~amandlek/" color="#000000">http://ai.stanford.edu/~amandlek/</a>',
            styles["ResumeContact"],
        ),
        Spacer(1, 4),
        HRFlowable(width="100%", thickness=0.8, color=colors.black, spaceBefore=0, spaceAfter=8),
        Paragraph("Overview", styles["ResumeSection"]),
        Paragraph(
            "I am a Staff Research Scientist at NVIDIA AI in the GEAR lab. I obtained my Ph.D. "
            "in Electrical Engineering from Stanford University (2016-2022) advised by Silvio "
            "Savarese and Fei-Fei Li.",
            styles["ResumeBody"],
        ),
        Paragraph(
            "I lead simulation-based research on the GEAR team, with a focus on making simulation "
            "a scalable method for training humanoid foundation models. Our research encompasses "
            "many different directions, such as synthetic data generation, real-to-sim and "
            "sim-to-real methods, extending simulation platforms to new applications such as "
            "deformable manipulation and loco-manipulation, and learning algorithms leveraging "
            "imitation learning, reinforcement learning, and planning, in simulation.",
            styles["ResumeBody"],
        ),
        Paragraph("Selected Publications (see website for full list)", styles["ResumeSection"]),
    ]

    for paper in papers:
        story.append(paper_flowables(paper, self_name, styles))

    story.extend(
        [
            Paragraph("Research Community Engagement", styles["ResumeSection"]),
            Paragraph("<b>Selected Talks</b>", styles["ResumeBody"]),
        ]
    )
    for talk in SELECTED_TALKS:
        story.append(talk_flowable(talk, styles))
    story.extend(
        [
            Spacer(1, 3),
            Paragraph("<b>Workshop Organization</b>", styles["ResumeBody"]),
            Paragraph("Data Generation for Robotics, RSS 2024", styles["ResumeBullet"], bulletText="•"),
            Paragraph("Overlooked Aspects of Imitation Learning, RSS 2022", styles["ResumeBullet"], bulletText="•"),
            Paragraph(
                "Advances and Challenges in Imitation Learning for Robotics, RSS 2020",
                styles["ResumeBullet"],
                bulletText="•",
            ),
            Spacer(1, 3),
            Paragraph("<b>Academic Service</b>", styles["ResumeBody"]),
            Paragraph("Area Chair for CoRL 2025, CoRL 2026", styles["ResumeBullet"], bulletText="•"),
            Paragraph(
                "Reviewer for CoRL, RSS, ICRA, IROS, ICLR, NeurIPS, ICML, CVPR, IEEE T-RO",
                styles["ResumeBullet"],
                bulletText="•",
            ),
            Paragraph("Work Experience and Education", styles["ResumeSection"]),
            Paragraph(
                "<b>Research Scientist</b>, NVIDIA GEAR Lab, July 2025 - Present",
                styles["ResumeBody"],
            ),
            Paragraph(
                "<b>Research Scientist</b>, NVIDIA Seattle Robotics Lab, Jan 2022 - June 2025",
                styles["ResumeBody"],
            ),
            Paragraph(
                "<b>Ph.D., Electrical Engineering</b>, Stanford University, 2016 - 2022<br/>"
                "NDSEG Fellow",
                styles["ResumeBody"],
            ),
            Paragraph(
                "<b>M.S., Computer Science</b>, Stanford University, 2018<br/>GPA: 4.1",
                styles["ResumeBody"],
            ),
            Paragraph(
                "<b>B.S., Electrical Engineering &amp; Computer Science (dual major)</b>, Caltech, 2016<br/>"
                "GPA: 4.1<br/>Officer of Tau Beta Pi Engineering Honor Society",
                styles["ResumeBody"],
            ),
            Paragraph("<b>Monta Vista High School</b>, Cupertino, CA", styles["ResumeBody"]),
        ]
    )

    doc.build(story)
    return len(papers)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="Generated PDF path")
    parser.add_argument(
        "--website",
        action="store_true",
        help=f"Also refresh {WEBSITE_OUTPUT}",
    )
    args = parser.parse_args()

    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    count = build_resume(args.output)
    print(f"Generated {args.output} with {count} selected publications")

    if args.website:
        os.makedirs(os.path.dirname(WEBSITE_OUTPUT), exist_ok=True)
        shutil.copyfile(args.output, WEBSITE_OUTPUT)
        print(f"Updated {WEBSITE_OUTPUT}")


if __name__ == "__main__":
    main()
