#!/usr/bin/env python3
"""
extract-api-patterns.py — Extract public API signatures and docstrings from an
installed Python package. Outputs structured markdown for use when writing
opensci skill Quick Reference sections and references/ files.

Usage:
    python extract-api-patterns.py --package <library> --output assets/api-dump.md
    python extract-api-patterns.py --package <library> --output assets/api-dump.md --max-depth 2
    python extract-api-patterns.py --package <library>.<submodule> --output assets/api-dump.md

Output (markdown):
    assets/api-dump.md
        # <package> Public API
        ## <module>
        ### <ClassName>
        **Signature:** ...
        **Docstring (first 3 lines):** ...
        ### <function_name>
        ...

Dependencies:
    Standard library only (importlib, inspect, ast).
    The target package must be installed in the current Python environment.

Notes:
    - Do not install packages automatically. Confirm install permission and
      selected environment before running any install command.
    - If the package is only available as local source, install with:
        pip install -e /path/to/package
      before running this script.
    - If editable install fails due native build/toolchain constraints,
      install the published wheel instead:
        pip install <package>
      and continue with --package mode.
    - Import errors for individual submodules are recorded in the output
      as "*Import failed: <reason>*" and are expected for packages with
      heavy optional dependencies (e.g., SimNIBS, vtk, cuda-only modules).
    - For exhaustive dictionary-style symbol lookup, pair this script with
      build-symbol-index.py (symbol-index.jsonl + symbol-cards).
"""

import argparse
import importlib
import inspect
import pkgutil
import re
import sys
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Signature helpers
# ---------------------------------------------------------------------------


def get_signature(obj: Any) -> str:
    """Return a clean signature string, or empty string on failure."""
    try:
        sig = inspect.signature(obj)
        return str(sig)
    except (ValueError, TypeError):
        return ""


def first_lines(docstring: str | None, n: int = 3) -> str:
    """Return the first n non-empty lines of a docstring."""
    if not docstring:
        return ""
    lines = [l.rstrip() for l in docstring.strip().splitlines() if l.strip()]
    return "\n".join(lines[:n])


def is_public(name: str) -> bool:
    """True if name does not start with underscore."""
    return not name.startswith("_")


# ---------------------------------------------------------------------------
# Per-module extraction
# ---------------------------------------------------------------------------


def extract_module(mod: Any, module_name: str) -> list[str]:
    """Extract public classes and functions from a module. Returns markdown lines."""
    lines: list[str] = []
    entries: list[tuple[str, Any]] = []

    for name, obj in inspect.getmembers(mod):
        if not is_public(name):
            continue
        # Only include things defined in (or re-exported from) this module
        obj_module = getattr(obj, "__module__", None) or ""
        if not (
            obj_module == module_name
            or obj_module.startswith(module_name.split(".")[0])
        ):
            continue
        if inspect.isclass(obj) or inspect.isfunction(obj):
            entries.append((name, obj))

    if not entries:
        return []

    lines.append(f"\n## {module_name}\n")

    for name, obj in sorted(entries, key=lambda x: x[0].lower()):
        kind = "class" if inspect.isclass(obj) else "function"
        sig = get_signature(obj)
        doc = first_lines(inspect.getdoc(obj), 3)

        lines.append(f"### `{name}`  *({kind})*")
        if sig:
            lines.append(f"\n**Signature:** `{name}{sig}`\n")
        if doc:
            # Indent docstring as a blockquote
            doc_indented = "\n".join(f"> {l}" for l in doc.splitlines())
            lines.append(f"**Docstring:**\n{doc_indented}\n")
        else:
            lines.append("")

        # For classes: list public methods briefly
        if inspect.isclass(obj):
            methods = [
                (mname, mobj)
                for mname, mobj in inspect.getmembers(obj, predicate=inspect.isfunction)
                if is_public(mname)
            ]
            if methods:
                method_names = ", ".join(f"`{m[0]}`" for m in methods[:15])
                if len(methods) > 15:
                    method_names += f", ... ({len(methods) - 15} more)"
                lines.append(f"**Public methods:** {method_names}\n")

    return lines


# ---------------------------------------------------------------------------
# Package walker
# ---------------------------------------------------------------------------


def walk_package(package_name: str, max_depth: int) -> list[tuple[int, str]]:
    """Return (depth, module_name) pairs for all submodules up to max_depth."""
    results: list[tuple[int, str]] = []
    base_depth = package_name.count(".") + 1

    try:
        pkg = importlib.import_module(package_name)
    except ImportError as exc:
        print(f"ERROR: Cannot import '{package_name}': {exc}", file=sys.stderr)
        sys.exit(1)

    results.append((0, package_name))

    pkg_path = getattr(pkg, "__path__", None)
    if pkg_path is None:
        # Single module, not a package
        return results

    for finder, modname, is_pkg in pkgutil.walk_packages(
        path=pkg_path,
        prefix=package_name + ".",
        onerror=lambda name: None,
    ):
        depth = modname.count(".") - base_depth + 1
        if depth > max_depth:
            continue
        results.append((depth, modname))

    return results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def extract(package_name: str, output_path: Path, max_depth: int) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Extracting API from: {package_name}")
    print(f"Max submodule depth: {max_depth}")
    print(f"Output: {output_path}")
    print()

    all_lines: list[str] = [
        f"# `{package_name}` Public API\n",
        f"*Generated by extract-api-patterns.py*\n",
        "---\n",
    ]

    modules = walk_package(package_name, max_depth)
    total = len(modules)

    for i, (depth, modname) in enumerate(modules, 1):
        print(f"  [{i:>3}/{total}]  {modname}")
        try:
            mod = importlib.import_module(modname)
        except Exception as exc:
            all_lines.append(f"\n## {modname}\n\n*Import failed: {exc}*\n")
            continue

        mod_lines = extract_module(mod, modname)
        if mod_lines:
            all_lines.extend(mod_lines)

    output_path.write_text("\n".join(all_lines), encoding="utf-8")
    print()
    print(f"Done. Output written to: {output_path}")
    print(f"File size: {output_path.stat().st_size / 1024:.1f} KB")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract public API from an installed Python package.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--package",
        required=True,
        help="Installed package name (e.g., scipy, scanpy, package.submodule)",
    )
    parser.add_argument(
        "--output",
        default="assets/api-dump.md",
        help="Output markdown file path (default: assets/api-dump.md)",
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=1,
        help="Max submodule depth to recurse into (default: 1). "
        "0 = top-level only, 1 = one level of submodules, etc.",
    )

    args = parser.parse_args()
    extract(
        package_name=args.package,
        output_path=Path(args.output),
        max_depth=args.max_depth,
    )


if __name__ == "__main__":
    main()
