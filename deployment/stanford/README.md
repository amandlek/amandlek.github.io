# Stanford homepage redirect

The new website is **https://amandlek.github.io/**. This directory contains:

- `index.html`: an immediate HTML redirect, a canonical link, and a visible link
  to the new site. It works without access to Apache configuration.
- `.htaccess.example`: an optional HTTP 301 redirect for the old homepage and
  `index.html`. It leaves Stanford-hosted PDFs, images, and other paths available.
  Merge it into existing configuration only if Stanford supports these directives.

## Install manually

Run the following from the root of the local `amandlek.github.io` checkout.
Authenticate to Stanford in your own Terminal when prompted. The SSH server is
`xenon.stanford.edu`; the web directory is
`/afs/cs.stanford.edu/u/amandlek/www/`.

First upload the redirect under a staging filename:

```bash
scp deployment/stanford/index.html \
  amandlek@xenon.stanford.edu:/afs/cs.stanford.edu/u/amandlek/www/index.html.github-redirect
```

Then back up the old homepage and install the redirect:

```bash
ssh amandlek@xenon.stanford.edu 'set -e
cd /afs/cs.stanford.edu/u/amandlek/www
cp -p index.html "index.html.before-github-redirect.$(date -u +%Y%m%dT%H%M%SZ)"
chmod 644 index.html.github-redirect
mv index.html.github-redirect index.html'
```

The timestamped backup allows restoration of the original homepage. These
commands retain the existing assets and configuration. Do not copy this entire
repository into the Stanford web directory, because the main `index.html` in the
repository is the full website, not the redirect.

If Stanford permits Apache `mod_alias` rules in `.htaccess`, merge the line in
`.htaccess.example` into the web directory's `.htaccess`, retaining existing
configuration. A server-side 301 is preferred; the HTML file provides a fallback
if those directives are unavailable. Test the old homepage after changing server
configuration and restore the previous configuration if it causes an error.

The older `https://web.stanford.edu/~amandlek/` site previously redirected to the
AI site. If you still have access to its separate `WWW` directory, replace its
homepage with this same redirect to send visitors straight to GitHub Pages.

## Verify

While connected to the Stanford network or VPN, open
`https://ai.stanford.edu/~amandlek/` in a browser and confirm it immediately sends
you to `https://amandlek.github.io/`. Also test from outside the Stanford network
when that endpoint is reachable again. With the optional 301 installed, check:

```bash
curl -I 'https://ai.stanford.edu/~amandlek/'
```

The expected response is HTTP 301 with a `Location` header pointing to the new
homepage. The HTML fallback instead returns HTTP 200 and redirects in the browser.

A redirect cannot help visitors while the old server is unreachable: their
browsers must first reach Stanford to receive it. Installing it now will help
visitors if public access is restored. Update profile and project links directly
in the meantime.

Google's guidance:
[server and HTML redirects](https://developers.google.com/search/docs/crawling-indexing/301-redirects).
