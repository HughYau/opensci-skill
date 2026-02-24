#!/usr/bin/env python3
"""
fetch-local-rst.py — opensci-skill
====================================
Converts a Sphinx documentation directory tree of .rst files to Markdown,
preserving subdirectory structure.  All output goes to assets/ inside the
target skill being built.

Also copies .md files found in the doc tree as-is (myst-parser sources used
by modern libraries that mix .rst and .md in one docs tree).

Usage
-----
    python fetch-local-rst.py --source <path/to/doc> [--output <path>]

Arguments
---------
    --source   Path to the Sphinx documentation root — the directory containing
               conf.py (e.g., doc/ or doc/source/) (required)
    --output   Output directory (default: assets/docs-cache/)

Output
------
    <output>/<relative/path>/<file>.md   — one .md per .rst (converted)
                                         — one .md per source .md (copied as-is)
    <output>/_manifest.txt               — list of all processed files

RST Constructs Handled
-----------------------
    Headings        : underline-only and overline+underline → ATX (#, ##, …)
    Directives      : .. code-block:: lang → fenced ```lang
    Directives      : .. note::, .. warning::, .. deprecated:: → blockquote
    Directives      : .. toctree::, .. automodule::, etc. → stripped
    Roles           : :ref:`…`, :class:`…`, :func:`…`, :meth:`…`, :attr:`…`,
                      :mod:`…`, :data:`…`, :doc:`…`, :py:…`  → backtick text
    Inline markup   : ``code`` → `code`,  *em* stays,  **strong** stays
    Hyperlinks      : `text <url>`_ and `text`_ reference blocks
    Field lists     : :param x:, :type x:, :returns:, :rtype: → kept as-is
    Substitutions   : |name| → (name)

Markdown sources (.md in doc tree)
-----------------------------------
    Source .md files (myst-parser) are copied as-is to the output tree.
    They are NOT re-converted; their paths are preserved and added to the
    manifest.  This handles libraries that mix .rst and .md in their Sphinx
    tree (e.g., doc/quickstart.md, doc/user_guide/*.md).
"""

import argparse
import os
import re
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Heading detection helpers
# ---------------------------------------------------------------------------

# Characters commonly used as RST heading adornments
_ADORNMENT_CHARS = set('!"#$%&\'()*+,-./:;<=>?@[\\]^_`{|}~')

def _is_adornment(line: str) -> bool:
    stripped = line.rstrip()
    return len(stripped) >= 2 and all(c in _ADORNMENT_CHARS for c in stripped)


# ---------------------------------------------------------------------------
# Main RST → Markdown converter
# ---------------------------------------------------------------------------

class RstConverter:
    """Convert a single RST file string to Markdown."""

    # Roles that map cleanly to backtick text
    _ROLE_PATTERN = re.compile(
        r':(?:ref|class|func|meth|attr|mod|data|doc|obj|exc|py:\w+|any):`([^`]*)`'
    )

    # ``code`` inline → `code`
    _INLINE_CODE = re.compile(r'``([^`]+)``')

    # Anonymous hyperlinks: `text <url>`__  or  `text <url>`_
    _ANON_LINK = re.compile(r'`([^`<]+)\s*<([^>]+)>`__?')

    # Named hyperlink reference: `text`_
    _NAMED_REF = re.compile(r'`([^`]+)`_(?!_)')

    # Hyperlink target definition: .. _name: url
    _LINK_TARGET = re.compile(r'^\.\. _([^:]+):\s*(.+)$')

    # Substitution reference: |name|
    _SUBSTITUTION_REF = re.compile(r'\|([^|]+)\|')

    # Directives we silently drop (body is also dropped via indented block skip)
    _DROP_DIRECTIVES = {
        'toctree', 'automodule', 'autoclass', 'autofunction', 'automethod',
        'autoattribute', 'autosummary', 'contents', 'index', 'only',
        'include', 'literalinclude', 'image', 'figure', 'csv-table',
        'list-table', 'math', 'testsetup', 'testcleanup', 'doctest',
        'rubric', 'highlight', 'default-domain', 'currentmodule',
        'tabularcolumns', 'centered', 'hlist', 'raw',
    }

    # Directives we convert to blockquotes with a bold label
    _NOTE_DIRECTIVES = {
        'note', 'warning', 'danger', 'important', 'tip', 'hint',
        'caution', 'attention', 'deprecated', 'versionadded',
        'versionchanged', 'seealso', 'todo',
    }

    def convert(self, rst: str) -> str:
        lines = rst.splitlines()
        output: list[str] = []
        i = 0
        heading_stack: list[str] = []  # tracks adornment chars in encounter order

        while i < len(lines):
            line = lines[i]

            # ----------------------------------------------------------------
            # Heading detection
            # ----------------------------------------------------------------
            # Pattern A: overline + title + underline
            if (
                i + 2 < len(lines)
                and _is_adornment(line)
                and not lines[i + 1].strip() == ''
                and _is_adornment(lines[i + 2])
                and lines[i][0] == lines[i + 2][0]
            ):
                char = line[0]
                title = lines[i + 1].strip()
                level = self._heading_level(char, heading_stack)
                output.append(f"{'#' * level} {title}")
                output.append('')
                i += 3
                continue

            # Pattern B: title + underline
            if (
                i + 1 < len(lines)
                and _is_adornment(lines[i + 1])
                and line.strip()
                and not _is_adornment(line)
            ):
                underline = lines[i + 1]
                # underline must be at least as long as title
                if len(underline.rstrip()) >= len(line.rstrip()):
                    char = underline[0]
                    title = line.strip()
                    level = self._heading_level(char, heading_stack)
                    output.append(f"{'#' * level} {title}")
                    output.append('')
                    i += 2
                    continue

            # ----------------------------------------------------------------
            # Directive detection
            # ----------------------------------------------------------------
            dir_match = re.match(r'^(\s*)\.\.\s+(\w[\w-]*)::(.*)$', line)
            if dir_match:
                indent_prefix = dir_match.group(1)
                directive = dir_match.group(2).lower()
                rest = dir_match.group(3).strip()

                # code-block / code / sourcecode → fenced code block
                if directive in ('code-block', 'code', 'sourcecode'):
                    lang = rest if rest else ''
                    # collect option lines (:linenos:, etc.) then blank, then body
                    i += 1
                    # skip option lines
                    while i < len(lines) and re.match(r'^\s+:\w', lines[i]):
                        i += 1
                    # skip blank line(s)
                    while i < len(lines) and lines[i].strip() == '':
                        i += 1
                    # collect indented body
                    body_lines = []
                    while i < len(lines) and (lines[i].startswith('   ') or lines[i].strip() == ''):
                        body_lines.append(lines[i])
                        i += 1
                    # strip trailing blank lines
                    while body_lines and body_lines[-1].strip() == '':
                        body_lines.pop()
                    # dedent by 3 (or common indent)
                    body = '\n'.join(l[3:] if l.startswith('   ') else l for l in body_lines)
                    output.append(f'```{lang}')
                    output.append(body)
                    output.append('```')
                    output.append('')
                    continue

                # note/warning etc. → blockquote
                if directive in self._NOTE_DIRECTIVES:
                    label = directive.upper()
                    i += 1
                    # collect indented body
                    body_lines = []
                    while i < len(lines) and (lines[i].startswith('   ') or lines[i].strip() == ''):
                        body_lines.append(lines[i])
                        i += 1
                    body = ' '.join(l.strip() for l in body_lines if l.strip())
                    if rest:
                        body = rest + (' ' + body if body else '')
                    output.append(f'> **{label}:** {body}')
                    output.append('')
                    continue

                # drop directives — consume their indented block
                if directive in self._DROP_DIRECTIVES:
                    i += 1
                    while i < len(lines) and (lines[i].startswith('   ') or lines[i].strip() == ''):
                        i += 1
                    continue

                # hyperlink target: .. _name: url
                lt = self._LINK_TARGET.match(line)
                if lt:
                    i += 1
                    continue  # drop link targets (references are inlined)

                # generic directive we don't recognise — drop it and its body
                i += 1
                while i < len(lines) and (lines[i].startswith('   ') or lines[i].strip() == ''):
                    i += 1
                continue

            # ----------------------------------------------------------------
            # Plain lines — apply inline transforms
            # ----------------------------------------------------------------
            line = self._transform_inline(line)
            output.append(line)
            i += 1

        return '\n'.join(output)

    # ----------------------------------------------------------------
    # Heading level tracker
    # ----------------------------------------------------------------
    def _heading_level(self, char: str, stack: list[str]) -> int:
        if char not in stack:
            stack.append(char)
        return stack.index(char) + 1

    # ----------------------------------------------------------------
    # Inline transforms
    # ----------------------------------------------------------------
    def _transform_inline(self, line: str) -> str:
        # Anonymous hyperlinks: `text <url>`_ → [text](url)
        line = self._ANON_LINK.sub(r'[\1](\2)', line)
        # Named refs: `text`_ → **text** (we can't resolve without target map)
        line = self._NAMED_REF.sub(r'**\1**', line)
        # Roles → backtick text (keep only the title part of cross-ref)
        def role_repl(m):
            text = m.group(1)
            # :ref:`Title <target>` → `Title`
            inner = re.match(r'^(.*?)\s*<[^>]+>$', text)
            if inner:
                text = inner.group(1).strip()
            return f'`{text}`'
        line = self._ROLE_PATTERN.sub(role_repl, line)
        # ``code`` → `code`
        line = self._INLINE_CODE.sub(r'`\1`', line)
        # Substitution refs: |name| → (name)
        line = self._SUBSTITUTION_REF.sub(r'(\1)', line)
        return line


# ---------------------------------------------------------------------------
# File walker
# ---------------------------------------------------------------------------

def process_rst_tree(source_dir: Path, output_dir: Path) -> list[str]:
    """Walk source_dir, convert every .rst → .md and copy every source .md in output_dir.

    .rst files are converted to Markdown via RstConverter.
    .md files found in the doc tree are copied as-is (myst-parser sources).
    Auto-generated directories (e.g., modules/generated/, api/generated/) that
    only exist after ``make html`` are silently skipped if absent — no error.
    """
    converter = RstConverter()
    manifest: list[str] = []

    rst_files = sorted(source_dir.rglob('*.rst'))
    md_files = sorted(source_dir.rglob('*.md'))

    if not rst_files and not md_files:
        print(f'[warn] No .rst or .md files found under {source_dir}', file=sys.stderr)
        return manifest

    # --- Process .rst files (convert to Markdown) ---
    for rst_path in rst_files:
        rel = rst_path.relative_to(source_dir)
        out_path = output_dir / rel.with_suffix('.md')
        out_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            rst_text = rst_path.read_text(encoding='utf-8', errors='replace')
        except OSError as e:
            print(f'[error] Cannot read {rst_path}: {e}', file=sys.stderr)
            continue

        md_text = converter.convert(rst_text)
        out_path.write_text(md_text, encoding='utf-8')

        rel_str = str(rel)
        manifest.append(rel_str)
        print(f'  converted: {rel_str}')

    # --- Process source .md files (copy as-is; myst-parser sources) ---
    for md_path in md_files:
        rel = md_path.relative_to(source_dir)
        out_path = output_dir / rel
        # Skip if the output path is identical to the source (output inside source tree)
        if out_path.resolve() == md_path.resolve():
            continue
        out_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            text = md_path.read_text(encoding='utf-8', errors='replace')
        except OSError as e:
            print(f'[error] Cannot read {md_path}: {e}', file=sys.stderr)
            continue

        out_path.write_text(text, encoding='utf-8')

        rel_str = str(rel)
        manifest.append(rel_str)
        print(f'  copied (md): {rel_str}')

    return manifest


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description='Convert Sphinx RST doc tree to Markdown for agent consumption.'
    )
    parser.add_argument(
        '--source', required=True,
        help='Path to Sphinx documentation root — the directory containing conf.py (e.g., doc/ or doc/source/)'
    )
    parser.add_argument(
        '--output', default='assets/docs-cache',
        help='Output directory (default: assets/docs-cache/)'
    )
    args = parser.parse_args()

    source_dir = Path(args.source).resolve()
    output_dir = Path(args.output).resolve()

    if not source_dir.is_dir():
        print(f'[error] Source directory not found: {source_dir}', file=sys.stderr)
        sys.exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)
    print(f'Source : {source_dir}')
    print(f'Output : {output_dir}')
    print()

    manifest = process_rst_tree(source_dir, output_dir)

    # Write manifest
    manifest_path = output_dir / '_manifest.txt'
    manifest_path.write_text('\n'.join(manifest) + '\n', encoding='utf-8')
    print()
    print(f'Processed {len(manifest)} file(s) (.rst converted, .md copied).')
    print(f'Manifest : {manifest_path}')


if __name__ == '__main__':
    main()
