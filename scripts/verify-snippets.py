#!/usr/bin/env python3
"""
verify-snippets.py — Execute fenced Python snippets in a generated skill.

Scans:
  - <root>/SKILL.md
  - <root>/references/*.md

Runs every fenced block tagged as python/py/python3 in an isolated subprocess
using the current interpreter, then reports pass/fail with file and line info.

Usage:
    python verify-snippets.py --root <library-skill-dir>
    python verify-snippets.py --root <library-skill-dir> --fail-fast
    python verify-snippets.py --root <library-skill-dir> --timeout 45
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


PYTHON_FENCE_LANGS = {"python", "py", "python3"}


@dataclass
class Snippet:
    file_path: Path
    start_line: int
    code: str


@dataclass
class SnippetResult:
    snippet: Snippet
    status: str  # pass | fail | timeout
    duration_sec: float
    returncode: int | None
    stdout: str
    stderr: str


def collect_markdown_files(root: Path) -> list[Path]:
    skill_md = root / "SKILL.md"
    if not skill_md.exists():
        raise FileNotFoundError(f"Missing required file: {skill_md}")

    files = [skill_md]
    ref_dir = root / "references"
    if ref_dir.exists():
        files.extend(sorted(ref_dir.glob("*.md")))
    return files


def extract_python_snippets(md_path: Path) -> list[Snippet]:
    snippets: list[Snippet] = []
    lines = md_path.read_text(encoding="utf-8", errors="replace").splitlines()

    in_fence = False
    fence_lang = ""
    fence_start = 0
    buffer: list[str] = []

    for lineno, line in enumerate(lines, start=1):
        stripped = line.strip()

        if not in_fence:
            if stripped.startswith("```"):
                fence_lang = stripped[3:].strip().lower()
                in_fence = True
                fence_start = lineno + 1
                buffer = []
            continue

        if stripped.startswith("```"):
            if fence_lang in PYTHON_FENCE_LANGS:
                code = "\n".join(buffer).strip()
                if code:
                    snippets.append(
                        Snippet(file_path=md_path, start_line=fence_start, code=code)
                    )
            in_fence = False
            fence_lang = ""
            buffer = []
            continue

        buffer.append(line)

    return snippets


def run_snippet(snippet: Snippet, cwd: Path, timeout_sec: float) -> SnippetResult:
    started = time.perf_counter()
    try:
        proc = subprocess.run(
            [sys.executable, "-c", snippet.code],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout_sec,
        )
    except subprocess.TimeoutExpired as exc:
        duration = time.perf_counter() - started
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        return SnippetResult(
            snippet=snippet,
            status="timeout",
            duration_sec=duration,
            returncode=None,
            stdout=stdout,
            stderr=stderr,
        )

    duration = time.perf_counter() - started
    status = "pass" if proc.returncode == 0 else "fail"
    return SnippetResult(
        snippet=snippet,
        status=status,
        duration_sec=duration,
        returncode=proc.returncode,
        stdout=proc.stdout,
        stderr=proc.stderr,
    )


def short_error(text: str, max_lines: int = 4) -> str:
    lines = [ln for ln in text.strip().splitlines() if ln.strip()]
    if not lines:
        return "(no stderr)"
    if len(lines) <= max_lines:
        return " | ".join(lines)
    return " | ".join(lines[:max_lines]) + " | ..."


def render_report(
    report_path: Path, root: Path, results: list[SnippetResult], total_snippets: int
) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")

    passed = sum(1 for r in results if r.status == "pass")
    failed = sum(1 for r in results if r.status == "fail")
    timed_out = sum(1 for r in results if r.status == "timeout")

    lines: list[str] = []
    lines.append("# Snippet Verification Report")
    lines.append("")
    lines.append(f"- Generated: `{now}`")
    lines.append(f"- Root: `{root}`")
    lines.append(f"- Total snippets: `{total_snippets}`")
    lines.append(f"- Passed: `{passed}`")
    lines.append(f"- Failed: `{failed}`")
    lines.append(f"- Timed out: `{timed_out}`")
    lines.append("")
    lines.append("| Status | Location | Duration (s) | Details |")
    lines.append("|--------|----------|--------------|---------|")

    for result in results:
        rel = result.snippet.file_path.relative_to(root)
        loc = f"`{rel}:{result.snippet.start_line}`"
        duration = f"{result.duration_sec:.2f}"
        if result.status == "pass":
            details = "ok"
        elif result.status == "timeout":
            details = "timeout"
        else:
            details = short_error(result.stderr)
        lines.append(f"| {result.status} | {loc} | {duration} | {details} |")

    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Execute fenced Python snippets in SKILL.md and references/*.md"
    )
    parser.add_argument(
        "--root",
        required=True,
        help="Path to the generated library skill directory",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="Per-snippet timeout in seconds (default: 30)",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop immediately on first failed or timed-out snippet",
    )
    parser.add_argument(
        "--report",
        default="assets/snippet-verification.md",
        help="Markdown report path relative to --root (use '-' to disable)",
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"ERROR: skill directory not found: {root}", file=sys.stderr)
        sys.exit(1)

    try:
        md_files = collect_markdown_files(root)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    snippets: list[Snippet] = []
    for md_file in md_files:
        snippets.extend(extract_python_snippets(md_file))

    if not snippets:
        print("ERROR: no fenced Python snippets found.", file=sys.stderr)
        sys.exit(1)

    print(f"Skill root : {root}")
    print(f"Markdown   : {len(md_files)} files")
    print(f"Snippets   : {len(snippets)}")
    print(f"Timeout    : {args.timeout:.1f}s")
    print()

    results: list[SnippetResult] = []
    failures = 0

    for idx, snippet in enumerate(snippets, start=1):
        rel = snippet.file_path.relative_to(root)
        result = run_snippet(snippet, cwd=root, timeout_sec=args.timeout)
        results.append(result)

        if result.status == "pass":
            print(
                f"PASS [{idx}/{len(snippets)}] {rel}:{snippet.start_line} "
                f"({result.duration_sec:.2f}s)"
            )
            continue

        failures += 1
        if result.status == "timeout":
            print(
                f"TIMEOUT [{idx}/{len(snippets)}] {rel}:{snippet.start_line} "
                f"({result.duration_sec:.2f}s)"
            )
        else:
            err = short_error(result.stderr)
            code = result.returncode if result.returncode is not None else "?"
            print(
                f"FAIL [{idx}/{len(snippets)}] {rel}:{snippet.start_line} "
                f"(exit={code}, {result.duration_sec:.2f}s)"
            )
            print(f"  stderr: {err}")

        if args.fail_fast:
            break

    if args.report != "-":
        report_path = Path(args.report)
        if not report_path.is_absolute():
            report_path = root / report_path
        render_report(report_path, root, results, len(snippets))
        print()
        print(f"Report     : {report_path}")

    passed = sum(1 for r in results if r.status == "pass")
    failed = sum(1 for r in results if r.status == "fail")
    timed_out = sum(1 for r in results if r.status == "timeout")

    print()
    print(f"Summary: {passed} passed, {failed} failed, {timed_out} timed out")

    if failures > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
