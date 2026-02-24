#!/usr/bin/env python3
"""
build-symbol-index.py — Build a dictionary-style API knowledge base.

Creates three artifacts for agent lookup:
  - assets/symbol-index.jsonl   (machine-readable, one symbol per line)
  - assets/symbol-index.md      (module-level navigation + lookup tips)
  - assets/symbol-cards/*.md    (per-module symbol cards)

Supports two discovery modes:
  1) Runtime mode (`--package`): imports modules and uses inspect/signatures.
  2) Source mode (`--source`): parses .py files with AST (no installs needed).

Usage:
    # Runtime mode (installed package)
    python build-symbol-index.py --package scipy --max-depth 2

    # Source mode (no install)
    python build-symbol-index.py --source /path/to/library/src/mypkg
"""

from __future__ import annotations

import argparse
import ast
import importlib
import inspect
import json
import pkgutil
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass
class SymbolRecord:
    symbol: str
    kind: str
    module: str
    signature: str
    summary: str
    source_file: str
    source_line: int | None
    verification: str  # runtime | ast


def first_nonempty_line(doc: str | None, limit: int = 220) -> str:
    if not doc:
        return ""
    for line in doc.splitlines():
        stripped = line.strip()
        if stripped:
            if len(stripped) <= limit:
                return stripped
            return stripped[: limit - 3] + "..."
    return ""


def safe_signature_runtime(name: str, obj: Any) -> str:
    try:
        return f"{name}{inspect.signature(obj)}"
    except (TypeError, ValueError):
        return f"{name}(...)"


def safe_source_runtime(
    obj: Any, root_hint: Path | None = None
) -> tuple[str, int | None]:
    source_file = "(unknown)"
    source_line: int | None = None
    try:
        file_path = inspect.getsourcefile(obj) or inspect.getfile(obj)
        if file_path:
            p = Path(file_path).resolve()
            if root_hint is not None:
                try:
                    source_file = str(p.relative_to(root_hint))
                except ValueError:
                    source_file = str(p)
            else:
                source_file = str(p)
    except (TypeError, OSError):
        pass

    try:
        source_line = inspect.getsourcelines(obj)[1]
    except (TypeError, OSError):
        source_line = None

    return source_file, source_line


def walk_installed_modules(package_name: str, max_depth: int) -> list[str]:
    modules: list[str] = []

    try:
        pkg = importlib.import_module(package_name)
    except Exception as exc:  # pragma: no cover - CLI error path
        print(f"ERROR: cannot import package '{package_name}': {exc}", file=sys.stderr)
        sys.exit(1)

    modules.append(package_name)
    pkg_path = getattr(pkg, "__path__", None)
    if pkg_path is None:
        return modules

    base_depth = package_name.count(".") + 1
    for importer, modname, ispkg in pkgutil.walk_packages(
        path=pkg_path,
        prefix=package_name + ".",
        onerror=lambda name: None,
    ):
        depth = modname.count(".") - base_depth + 1
        if depth > max_depth:
            continue
        modules.append(modname)

    return modules


def collect_runtime_records(
    package_name: str,
    max_depth: int,
    include_methods: bool,
) -> tuple[list[SymbolRecord], list[str]]:
    records: dict[str, SymbolRecord] = {}
    import_failures: list[str] = []

    modules = walk_installed_modules(package_name, max_depth)

    root_hint: Path | None = None
    try:
        pkg = importlib.import_module(package_name)
        pkg_file = getattr(pkg, "__file__", None)
        if pkg_file:
            root_hint = Path(pkg_file).resolve().parent
    except Exception:
        root_hint = None

    for modname in sorted(modules):
        try:
            mod = importlib.import_module(modname)
        except Exception as exc:
            import_failures.append(f"{modname}: {exc}")
            continue

        for name, obj in inspect.getmembers(mod):
            if name.startswith("_"):
                continue

            obj_module = getattr(obj, "__module__", "") or ""
            if not obj_module.startswith(package_name):
                continue

            if inspect.isfunction(obj):
                symbol = f"{modname}.{name}"
                source_file, source_line = safe_source_runtime(obj, root_hint)
                records[symbol] = SymbolRecord(
                    symbol=symbol,
                    kind="function",
                    module=modname,
                    signature=safe_signature_runtime(name, obj),
                    summary=first_nonempty_line(inspect.getdoc(obj)),
                    source_file=source_file,
                    source_line=source_line,
                    verification="runtime",
                )

            elif inspect.isclass(obj):
                symbol = f"{modname}.{name}"
                source_file, source_line = safe_source_runtime(obj, root_hint)
                records[symbol] = SymbolRecord(
                    symbol=symbol,
                    kind="class",
                    module=modname,
                    signature=safe_signature_runtime(name, obj),
                    summary=first_nonempty_line(inspect.getdoc(obj)),
                    source_file=source_file,
                    source_line=source_line,
                    verification="runtime",
                )

                if not include_methods:
                    continue

                for mname, mobj in inspect.getmembers(
                    obj, predicate=inspect.isfunction
                ):
                    if mname.startswith("_"):
                        continue
                    method_module = getattr(mobj, "__module__", "") or ""
                    if not method_module.startswith(package_name):
                        continue
                    msymbol = f"{modname}.{name}.{mname}"
                    msource_file, msource_line = safe_source_runtime(mobj, root_hint)
                    records[msymbol] = SymbolRecord(
                        symbol=msymbol,
                        kind="method",
                        module=modname,
                        signature=safe_signature_runtime(mname, mobj),
                        summary=first_nonempty_line(inspect.getdoc(mobj)),
                        source_file=msource_file,
                        source_line=msource_line,
                        verification="runtime",
                    )

    return sorted(records.values(), key=lambda r: r.symbol), import_failures


def module_name_from_source_path(pkg_root: Path, py_path: Path) -> str:
    rel = py_path.relative_to(pkg_root)
    pkg_name = pkg_root.name
    if rel.name == "__init__.py":
        if rel.parent == Path("."):
            return pkg_name
        return pkg_name + "." + ".".join(rel.parent.parts)
    return pkg_name + "." + ".".join(rel.with_suffix("").parts)


def source_file_for_record(pkg_root: Path, py_path: Path) -> str:
    return str(py_path.relative_to(pkg_root.parent))


def _default_to_text(node: ast.AST | None) -> str:
    if node is None:
        return "None"
    try:
        return ast.unparse(node)
    except Exception:
        return "..."


def signature_from_ast(
    fn_name: str,
    args: ast.arguments,
    drop_first_param: bool = False,
) -> str:
    tokens: list[str] = []

    posonly = list(args.posonlyargs)
    regular = list(args.args)
    all_regular = posonly + regular

    defaults = list(args.defaults)
    default_start = len(all_regular) - len(defaults)

    for idx, arg in enumerate(all_regular):
        if drop_first_param and idx == 0:
            continue
        token = arg.arg
        if idx >= default_start:
            default_idx = idx - default_start
            token += "=" + _default_to_text(defaults[default_idx])
        tokens.append(token)

    if posonly:
        pos_count = len(posonly)
        kept_pos = pos_count - (1 if drop_first_param else 0)
        if kept_pos > 0:
            insert_at = min(kept_pos, len(tokens))
            tokens.insert(insert_at, "/")

    if args.vararg is not None:
        tokens.append("*" + args.vararg.arg)
    elif args.kwonlyargs:
        tokens.append("*")

    for kwarg, kwdefault in zip(args.kwonlyargs, args.kw_defaults):
        token = kwarg.arg
        if kwdefault is not None:
            token += "=" + _default_to_text(kwdefault)
        tokens.append(token)

    if args.kwarg is not None:
        tokens.append("**" + args.kwarg.arg)

    return f"{fn_name}({', '.join(tokens)})"


def collect_ast_records(
    pkg_root: Path, include_methods: bool
) -> tuple[list[SymbolRecord], list[str]]:
    records: dict[str, SymbolRecord] = {}
    parse_failures: list[str] = []

    for py_path in sorted(pkg_root.rglob("*.py")):
        module = module_name_from_source_path(pkg_root, py_path)
        source_rel = source_file_for_record(pkg_root, py_path)

        try:
            src = py_path.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(src, filename=str(py_path))
        except Exception as exc:
            parse_failures.append(f"{module}: {exc}")
            continue

        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name.startswith("_"):
                    continue
                symbol = f"{module}.{node.name}"
                records[symbol] = SymbolRecord(
                    symbol=symbol,
                    kind="function",
                    module=module,
                    signature=signature_from_ast(node.name, node.args),
                    summary=first_nonempty_line(ast.get_docstring(node)),
                    source_file=source_rel,
                    source_line=node.lineno,
                    verification="ast",
                )

            elif isinstance(node, ast.ClassDef):
                if node.name.startswith("_"):
                    continue

                init_node: ast.FunctionDef | ast.AsyncFunctionDef | None = None
                for cnode in node.body:
                    if (
                        isinstance(cnode, (ast.FunctionDef, ast.AsyncFunctionDef))
                        and cnode.name == "__init__"
                    ):
                        init_node = cnode
                        break

                if init_node is not None:
                    class_sig = signature_from_ast(
                        node.name, init_node.args, drop_first_param=True
                    )
                else:
                    class_sig = f"{node.name}(...)"

                symbol = f"{module}.{node.name}"
                records[symbol] = SymbolRecord(
                    symbol=symbol,
                    kind="class",
                    module=module,
                    signature=class_sig,
                    summary=first_nonempty_line(ast.get_docstring(node)),
                    source_file=source_rel,
                    source_line=node.lineno,
                    verification="ast",
                )

                if not include_methods:
                    continue

                for cnode in node.body:
                    if not isinstance(cnode, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        continue
                    if cnode.name.startswith("_"):
                        continue

                    msymbol = f"{module}.{node.name}.{cnode.name}"
                    records[msymbol] = SymbolRecord(
                        symbol=msymbol,
                        kind="method",
                        module=module,
                        signature=signature_from_ast(
                            cnode.name, cnode.args, drop_first_param=True
                        ),
                        summary=first_nonempty_line(ast.get_docstring(cnode)),
                        source_file=source_rel,
                        source_line=cnode.lineno,
                        verification="ast",
                    )

    return sorted(records.values(), key=lambda r: r.symbol), parse_failures


def safe_card_filename(module: str) -> str:
    return module.replace(".", "__") + ".md"


def write_jsonl(records: list[SymbolRecord], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(asdict(record), ensure_ascii=True) + "\n")


def write_cards(records: list[SymbolRecord], cards_dir: Path) -> dict[str, str]:
    cards_dir.mkdir(parents=True, exist_ok=True)

    by_module: dict[str, list[SymbolRecord]] = {}
    for record in records:
        by_module.setdefault(record.module, []).append(record)

    module_to_card: dict[str, str] = {}
    for module in sorted(by_module):
        card_name = safe_card_filename(module)
        card_path = cards_dir / card_name
        module_to_card[module] = card_name

        lines: list[str] = []
        lines.append(f"# Module Card: `{module}`")
        lines.append("")
        lines.append(
            "> Generated by opensci-skill/scripts/build-symbol-index.py. "
            "Use as dictionary-style lookup before opening source files."
        )
        lines.append("")

        for rec in sorted(by_module[module], key=lambda r: r.symbol):
            lines.append(f"## `{rec.symbol}`")
            lines.append("")
            lines.append(f"- kind: `{rec.kind}`")
            lines.append(f"- signature: `{rec.signature}`")
            if rec.summary:
                lines.append(f"- summary: {rec.summary}")
            else:
                lines.append("- summary: [UNVERIFIED: no docstring summary available]")
            if rec.source_line is None:
                lines.append(f"- source: `{rec.source_file}`")
            else:
                lines.append(f"- source: `{rec.source_file}:L{rec.source_line}`")
            lines.append(f"- verification: `{rec.verification}`")
            lines.append("")

        card_path.write_text("\n".join(lines), encoding="utf-8")

    return module_to_card


def write_markdown_index(
    package_name: str,
    mode: str,
    records: list[SymbolRecord],
    failures: list[str],
    output_path: Path,
    module_to_card: dict[str, str],
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    total = len(records)
    functions = sum(1 for r in records if r.kind == "function")
    classes = sum(1 for r in records if r.kind == "class")
    methods = sum(1 for r in records if r.kind == "method")

    module_counts: dict[str, int] = {}
    for record in records:
        module_counts[record.module] = module_counts.get(record.module, 0) + 1

    lines: list[str] = []
    lines.append(f"# Symbol Index: `{package_name}`")
    lines.append("")
    lines.append(
        "> Generated by opensci-skill/scripts/build-symbol-index.py. "
        "Primary dictionary entrypoint for API lookup."
    )
    lines.append("")
    lines.append("## Coverage")
    lines.append("")
    lines.append(f"- discovery mode: `{mode}`")
    lines.append(f"- total symbols: `{total}`")
    lines.append(f"- functions: `{functions}`")
    lines.append(f"- classes: `{classes}`")
    lines.append(f"- methods: `{methods}`")
    lines.append("")
    lines.append("## Lookup Contract")
    lines.append("")
    lines.append("Use this order for retrieval before reading source files:")
    lines.append("1. query `assets/symbol-index.jsonl` for exact symbol names")
    lines.append("2. open the module card in `assets/symbol-cards/`")
    lines.append(
        "3. follow `source` anchors only when implementation details are needed"
    )
    lines.append("")
    lines.append("## Module Cards")
    lines.append("")
    lines.append("| Module | Symbols | Card |")
    lines.append("|--------|---------|------|")
    for module in sorted(module_counts):
        card_rel = Path("assets") / "symbol-cards" / module_to_card[module]
        lines.append(f"| `{module}` | {module_counts[module]} | `{card_rel}` |")
    lines.append("")

    if failures:
        lines.append("## Import / Parse Failures")
        lines.append("")
        lines.append(
            "The following modules could not be imported/parsing failed. "
            "Symbols from these modules may be missing."
        )
        lines.append("")
        for failure in failures:
            lines.append(f"- `{failure}`")
        lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build dictionary-style symbol index artifacts for a Python library."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--package",
        help="Installed package name for runtime introspection",
    )
    group.add_argument(
        "--source",
        help="Path to package root containing __init__.py for AST-only indexing",
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=2,
        help="Runtime mode: max submodule depth (default: 2)",
    )
    parser.add_argument(
        "--no-methods",
        action="store_true",
        help="Skip class method entries",
    )
    parser.add_argument(
        "--output-index",
        default="assets/symbol-index.md",
        help="Output markdown index path (default: assets/symbol-index.md)",
    )
    parser.add_argument(
        "--output-jsonl",
        default="assets/symbol-index.jsonl",
        help="Output JSONL path (default: assets/symbol-index.jsonl)",
    )
    parser.add_argument(
        "--cards-dir",
        default="assets/symbol-cards",
        help="Output directory for module cards (default: assets/symbol-cards)",
    )
    args = parser.parse_args()

    include_methods = not args.no_methods

    output_index = Path(args.output_index)
    output_jsonl = Path(args.output_jsonl)
    cards_dir = Path(args.cards_dir)

    if args.package:
        package_name = args.package
        records, failures = collect_runtime_records(
            package_name=package_name,
            max_depth=args.max_depth,
            include_methods=include_methods,
        )
        mode = "runtime"
    else:
        pkg_root = Path(args.source).resolve()
        if not pkg_root.is_dir():
            print(f"ERROR: source directory not found: {pkg_root}", file=sys.stderr)
            sys.exit(1)
        package_name = pkg_root.name
        records, failures = collect_ast_records(
            pkg_root=pkg_root,
            include_methods=include_methods,
        )
        mode = "ast"

    write_jsonl(records, output_jsonl)
    module_to_card = write_cards(records, cards_dir)
    write_markdown_index(
        package_name=package_name,
        mode=mode,
        records=records,
        failures=failures,
        output_path=output_index,
        module_to_card=module_to_card,
    )

    print(f"Package     : {package_name}")
    print(f"Mode        : {mode}")
    print(f"Symbols     : {len(records)}")
    print(f"Failures    : {len(failures)}")
    print(f"Index (md)  : {output_index}")
    print(f"Index (json): {output_jsonl}")
    print(f"Cards dir   : {cards_dir}")


if __name__ == "__main__":
    main()
