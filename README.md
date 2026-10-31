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

### GitHub Pages setup

The site can be served directly as static files; no server or GitHub Actions
build workflow is required. The root `.nojekyll` file disables Jekyll processing.
Run `python build.py` locally whenever `papers.json` changes, and commit the
generated `index.html` along with the paper data.

To publish at **https://amandlek.github.io/**, the repository must be named
**`amandlek.github.io`** and owned by **`amandlek`**. The simplest migration is
to rename the existing repository, preserving its Git history:

1. Sign in to GitHub as an account with admin access to
   [amandlek/personal_website](https://github.com/amandlek/personal_website).
   In **Settings > General > Repository name**, rename it to
   `amandlek.github.io`. First check whether that repository already exists;
   an account can have only one user Pages site.
2. If local Git commands report that the Xcode license has not been accepted,
   run `sudo xcodebuild -license` in Terminal, review the license, and accept
   it to restore Git access.
3. In this local checkout, review `git status` and `git diff`, then run:

   ```bash
   python build.py --check
   git remote set-url origin git@github.com:amandlek/amandlek.github.io.git
   git add .nojekyll README.md
   git commit -m "Prepare website for GitHub Pages"
   git push origin master
   ```

   Also review and commit any other intended website updates before publishing;
   only committed and pushed files will appear on the live site. The push uses
   the existing GitHub SSH authentication for this checkout.
4. In the renamed repository's **Settings > Pages**, select:
   - **Source:** Deploy from a branch
   - **Branch:** `master`
   - **Folder:** `/(root)`

   Click **Save**. GitHub Free supports Pages from public repositories; private
   repositories require a plan that supports private-repository Pages.
5. Check the deployment in the repository's **Actions** tab. Once it succeeds,
   open https://amandlek.github.io/ and verify the profile photo, publication
   thumbnails, and [CV](https://amandlek.github.io/assets/resume/Resume.pdf).
   Publishing can take up to ten minutes. Enable **Enforce HTTPS** in Pages
   settings if it is not already enabled. No custom domain or DNS setup is
   needed for the `github.io` address.

After setup, normal updates are: edit the site, run `python build.py` when paper
data changes, commit the intended files, and push to `master`. GitHub Pages
publishes the pushed files automatically.

If you want to keep the repository name `personal_website`, enable Pages from
`master` and `/(root)` in that repository instead. Its default address will be
**https://amandlek.github.io/personal_website/**. To keep that repository name
while using the root `https://amandlek.github.io/` address, create a separate
`amandlek.github.io` repository and keep its published files synchronized.

GitHub documentation:
[Pages quickstart](https://docs.github.com/en/pages/quickstart),
[publishing sources](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site),
and [renaming a repository](https://docs.github.com/en/repositories/creating-and-managing-repositories/renaming-a-repository).

### Stanford hosting and optional redirect

After the GitHub Pages site is live and verified, the Stanford homepage can
optionally be replaced with a redirect to `https://amandlek.github.io/`.
This requires access to the Stanford web directory below. Existing deep links
to Stanford-hosted PDFs and other assets will still need those files, so keep
them available unless you also arrange redirects for their individual URLs.

The following commands describe the existing Stanford deployment process.

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
