#!/usr/bin/env python3
"""
fetch-docs.py — Crawl a library's official documentation site and save pages
as local markdown files for use when writing opensci skills.

Usage:
    python fetch-docs.py --url https://<docs-host>/<docs-path>/ --lib <library>
    python fetch-docs.py --url https://<docs-host>/<docs-path>/ --lib <library> --max-pages 80
    python fetch-docs.py --url https://<docs-host>/<docs-path>/ --lib <library> --require-html2text

Output:
    assets/docs-cache/<lib>/
        index.md
        api--Raw.md
        tutorials--preprocessing.md
        ...
    assets/docs-cache/<lib>/_manifest.txt   (list of all crawled URLs)

Dependencies:
    requests (required)
    html2text (optional but recommended — falls back to basic tag stripping)

Install:
    pip install requests html2text
"""

import argparse
import os
import re
import sys
import time
import urllib.parse
from pathlib import Path
from typing import Any

try:
    import requests
except ImportError:
    print(
        "ERROR: requests is required. Install with: pip install requests",
        file=sys.stderr,
    )
    sys.exit(1)

html2text: Any = None

try:
    import html2text as _html2text

    html2text = _html2text
    HAS_HTML2TEXT = True
except ImportError:
    HAS_HTML2TEXT = False
    print("WARNING: html2text not installed. Falling back to basic tag stripping.")
    print("         Install for better output: pip install html2text")


# ---------------------------------------------------------------------------
# HTML → Markdown conversion
# ---------------------------------------------------------------------------


def html_to_markdown(html: str, base_url: str) -> str:
    """Convert HTML string to markdown. Uses html2text if available."""
    if HAS_HTML2TEXT:
        h = html2text.HTML2Text()
        h.ignore_links = False
        h.ignore_images = True
        h.ignore_tables = False
        h.body_width = 0  # no line wrapping
        h.protect_links = True
        h.baseurl = base_url
        return h.handle(html)
    else:
        # Basic fallback: strip tags
        text = re.sub(
            r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE
        )
        text = re.sub(
            r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE
        )
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"&nbsp;", " ", text)
        text = re.sub(r"&lt;", "<", text)
        text = re.sub(r"&gt;", ">", text)
        text = re.sub(r"&amp;", "&", text)
        text = re.sub(r"&quot;", '"', text)
        text = re.sub(r" {2,}", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()


# ---------------------------------------------------------------------------
# URL utilities
# ---------------------------------------------------------------------------


def normalize_url(url: str) -> str:
    """Strip fragment and trailing slash for deduplication."""
    parsed = urllib.parse.urlparse(url)
    path = parsed.path.rstrip("/")
    return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, path, "", "", ""))


def url_to_filename(url: str, base_url: str) -> str:
    """Convert a URL to a safe local filename (without extension)."""
    parsed = urllib.parse.urlparse(url)
    base_parsed = urllib.parse.urlparse(base_url)
    # Strip base path prefix
    path = parsed.path
    base_path = base_parsed.path.rstrip("/")
    if path.startswith(base_path):
        path = path[len(base_path) :]
    path = path.strip("/")
    if not path:
        return "index"
    # Replace path separators and special chars with --
    name = re.sub(r"[/\\]", "--", path)
    name = re.sub(r"[^a-zA-Z0-9_\-.]", "_", name)
    name = re.sub(r"_+", "_", name).strip("_")
    return name or "index"


def extract_links(html: str, base_url: str, allowed_prefix: str) -> list[str]:
    """Extract absolute links from HTML that start with allowed_prefix."""
    hrefs = re.findall(r'href=["\']([^"\'#?][^"\']*)["\']', html)
    links = []
    for href in hrefs:
        abs_url = urllib.parse.urljoin(base_url, href)
        abs_url = normalize_url(abs_url)
        if abs_url.startswith(allowed_prefix):
            links.append(abs_url)
    return links


# ---------------------------------------------------------------------------
# Main crawler
# ---------------------------------------------------------------------------


def crawl(
    base_url: str, lib: str, max_pages: int, delay: float, output_dir: Path
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    session.headers["User-Agent"] = "opensci-skill-fetch-docs/1.0 (educational crawler)"

    # Normalize base URL for prefix matching
    base_norm = normalize_url(base_url)
    if not base_norm.endswith("/"):
        allowed_prefix = base_norm + "/"
    else:
        allowed_prefix = base_norm

    visited: set[str] = set()
    queue: list[str] = [base_norm]
    manifest: list[str] = []
    skipped = 0

    print(f"Crawling: {base_url}")
    print(f"Output:   {output_dir}")
    print(f"Max pages: {max_pages}")
    print()

    while queue and len(visited) < max_pages:
        url = queue.pop(0)
        if url in visited:
            continue

        # Skip non-HTML resources
        if re.search(r"\.(pdf|zip|tar|gz|png|jpg|svg|css|js|woff|ico)$", url, re.I):
            skipped += 1
            continue

        visited.add(url)

        try:
            resp = session.get(url, timeout=15)
            resp.raise_for_status()
        except Exception as exc:
            print(f"  SKIP  {url}  ({exc})")
            continue

        content_type = resp.headers.get("Content-Type", "")
        if "html" not in content_type:
            skipped += 1
            continue

        html = resp.text
        markdown = html_to_markdown(html, url)

        # Save file
        filename = url_to_filename(url, base_url) + ".md"
        out_path = output_dir / filename
        out_path.write_text(markdown, encoding="utf-8")

        manifest.append(url)
        print(f"  [{len(visited):>3}/{max_pages}]  {url}")

        # Enqueue new links
        new_links = extract_links(html, url, allowed_prefix)
        for link in new_links:
            if link not in visited and link not in queue:
                queue.append(link)

        if delay > 0:
            time.sleep(delay)

    # Write manifest
    manifest_path = output_dir / "_manifest.txt"
    manifest_path.write_text("\n".join(manifest), encoding="utf-8")

    print()
    print(f"Done. {len(visited)} pages saved, {skipped} non-HTML skipped.")
    print(f"Manifest: {manifest_path}")
    print(f"Cache dir: {output_dir}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Crawl a library docs site and save pages as markdown.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--url", required=True, help="Root URL of the docs site")
    parser.add_argument(
        "--lib", required=True, help="Library name (used as cache subdirectory)"
    )
    parser.add_argument(
        "--max-pages", type=int, default=100, help="Max pages to crawl (default: 100)"
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.3,
        help="Seconds between requests (default: 0.3)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output directory (default: assets/docs-cache/<lib>)",
    )
    parser.add_argument(
        "--require-html2text",
        action="store_true",
        help="Fail if html2text is not installed (recommended for high-fidelity markdown).",
    )

    args = parser.parse_args()

    if args.require_html2text and not HAS_HTML2TEXT:
        print(
            "ERROR: --require-html2text was set but html2text is not installed. "
            "Install with: pip install html2text",
            file=sys.stderr,
        )
        sys.exit(1)

    output_dir = (
        Path(args.output) if args.output else Path("assets/docs-cache") / args.lib
    )

    crawl(
        base_url=args.url,
        lib=args.lib,
        max_pages=args.max_pages,
        delay=args.delay,
        output_dir=output_dir,
    )


if __name__ == "__main__":
    main()
