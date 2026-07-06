README

## Website Maintenance

The publications section of the website is generated from `papers.json` using Python scripts. Everything else (bio, news, miscellaneous sections) is edited directly in `index.html`.

### File Structure

| File | Purpose |
|---|---|
| `index.html` | The website. Papers section is auto-generated between `<!-- BEGIN_PAPERS -->` and `<!-- END_PAPERS -->` markers. Everything else can be edited by hand. |
| `stylesheet.css` | Styles for the website. |
| `papers.json` | **Source of truth** for all publications. Edit this file to change paper data. |
| `build.py` | Reads `papers.json` and regenerates the papers section of `index.html`. |
| `add_paper.py` | CLI tool for adding new papers (supports arXiv auto-fetch). |
| `sync_scholar.py` | Compares Google Scholar profile against `papers.json` to find missing papers. |
| `gen_resume.py` | Generates a formatted list of highlighted publications for your resume (RTF/plain text). |
| `gen_resume_pdf.py` | Generates the complete resume PDF and can refresh the website CV asset. |
| `assets/` | Images, thumbnails, PDFs, and other static files. |
| `deprecated/` | Old jemdoc-based website files (kept for reference). |

### Common Tasks

**Add a paper from arXiv:**
```bash
python add_paper.py --arxiv 2505.24853
```
Fetches title and authors automatically. Prompts for venue, links, thumbnail, and highlight status. Tries to suggest thumbnails from project pages.

**Add a paper interactively (no arXiv):**
```bash
python add_paper.py
```

**View current papers:**
```bash
python add_paper.py --show
```

**Rebuild the site after editing `papers.json`:**
```bash
python build.py
```

**Check if `index.html` is up-to-date:**
```bash
python build.py --check
```

**Discover papers missing from your website via Google Scholar:**
```bash
pip install scholarly   # one-time setup
python sync_scholar.py
```

### Editing `papers.json`

Each paper entry looks like this:

```json
{
  "id": "DexMachina",
  "title": "DexMachina: Functional Retargeting for Bimanual Dexterous Manipulation",
  "title_url": "https://mandizhao.github.io/dexmachina/",
  "authors": "Mandi Zhao, Yifan Hou, Dieter Fox, Yashraj Narang, Ajay Mandlekar†, Shuran Song†",
  "venue": "Under Review",
  "year": null,
  "venue_note": "",
  "thumbnail": "assets/dexmachina/thumbnail.png",
  "highlighted": true,
  "awards": [],
  "links": {
    "arXiv": "https://arxiv.org/abs/2505.24853",
    "website": "https://mandizhao.github.io/dexmachina/",
    "code": "https://github.com/MandiZhao/dexmachina"
  },
  "section": "preprint"
}
```

**Key fields:**

- **`authors`**: Your name (`Ajay Mandlekar`) is auto-bolded by the build script. Use `*` after a name for equal contribution, `†` for equal advising (rendered as superscript dagger).
- **`awards`**: A list. Each entry is `{"text": "..."}`. Use markdown-style links for linked portions: `{"text": "Best Paper at [Workshop Name](https://url)"}`.
- **`venue_note`**: Optional parenthetical appended after the year, e.g. `"Datasets and Benchmarks Track"` renders as `NeurIPS 2022 (Datasets and Benchmarks Track)`.
- **`section`**: `"preprint"` or `"publication"`. Controls grouping and where new papers are inserted.
- **`highlighted`**: Set to `true` to give the entry a yellow background.

**Paper ordering** is determined by array order in `papers.json`. New papers added via `add_paper.py` are inserted at the top of their section.

### Updating Resume Publications

The `gen_resume.py` script auto-generates a formatted list of highlighted publications for your resume from `papers.json`.

**Generate an RTF file (for Pages):**
```bash
python gen_resume.py --rtf
```
Opens `resume_pubs.rtf` in Pages, then copy-paste into your resume. The RTF includes:
- **Times New Roman** font (size 11) to match your resume
- *Italic* titles, **bold** venue, **bold** self-name
- Superscript `*` and `†` markers
- Clickable blue hyperlinks for all paper links
- **Bold red** award text

**Other output options:**
```bash
python gen_resume.py              # Print plain text + copy to clipboard
python gen_resume.py --txt        # Save plain text to resume_pubs.txt
python gen_resume.py --all        # Generate both .rtf and .txt
```

Only papers with `"highlighted": true` in `papers.json` are included. To change which papers appear in the resume, toggle the `highlighted` field and re-run the script.

**Generate the complete PDF and refresh the website CV:**
```bash
python -m pip install reportlab  # one-time setup
python gen_resume_pdf.py --website
```

This writes an inspectable PDF to `output/pdf/Resume.pdf` and copies the same
file to `assets/resume/Resume.pdf`, which is the CV linked from the website.

### Editing Non-Paper Sections

Bio, Recent News, PhD Thesis, and Miscellaneous sections are edited directly in `index.html`. Just don't modify anything between the `<!-- BEGIN_PAPERS -->` and `<!-- END_PAPERS -->` markers — that content is overwritten by `build.py`.

---

## Deploying the website

Note: to update the website at `https://ai.stanford.edu/~amandlek/` (especially post-graduation), run the following in the home directory to manually transfer all files

```
scp -r * xenon.stanford.edu:/afs/cs.stanford.edu/u/amandlek/www/
```

Note: can also try rsync to avoid transferring everything, e.g.:

```
rsync -azvP --exclude='.git' * xenon.stanford.edu:/afs/cs.stanford.edu/u/amandlek/www/
```

Note: for password, check LastPass (xenon).

(See [this link](https://cs.stanford.edu/computing-guide/web-pages) for more information)

NOTE: the below is out of date - I've replaced the below website with a redirect to the above link, using an index.html file with the tag `<meta http-equiv="refresh" content="0;URL=https://ai.stanford.edu/~amandlek/">`

Note: to update the website at `web.stanford.edu/~amandlek`, run the following in the home directory to manually transfer all files

```
scp -r * rice:/home/amandlek/afs-home/WWW
```
