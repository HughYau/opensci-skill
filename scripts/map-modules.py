#!/usr/bin/env python3
"""
map-modules.py — opensci-skill
=================================
Builds a structured module map of a Python package and writes it to
assets/module-map.md (or a custom output path).

The map is optimised for agent consumption: it answers "what lives where"
before any code is read, and flags large files that need special attention.

Usage
-----
    # Installed package
    python map-modules.py --package <name> [--output <path>]

    # Local source tree (no install needed)
    python map-modules.py --source <path/to/pkg_root> [--output <path>]

Arguments
---------
    --package   Importable package name  (mutually exclusive with --source)
    --source    Path to the package root directory containing __init__.py
    --output    Output markdown file  (default: assets/module-map.md)

Output sections
---------------
    ## Package Overview       — name, version, location, Python
    ## __init__.py Analysis   — eager imports, lazy __getattr__, __all__
                                OR lazy_loader stub analysis (see below)
    ## Module Inventory       — all submodules with line count + [LARGE] flag
    ## Dependency Hints       — top-level imports found in __init__.py

lazy_loader detection
---------------------
    Some packages (especially large scientific libraries) use the third-party
    `lazy_loader` package via `lazy_loader.attach_stub(__name__, __file__)`.
    In this pattern __init__.py contains almost nothing; the public API is
    declared in a companion __init__.pyi stub file.

    This script detects that pattern automatically:
      - If `attach_stub` call is found in __init__.py, it looks for
        __init__.pyi in the same directory.
      - If found, it parses the .pyi with the standard AST (valid Python)
        to extract __all__ and all imported symbol names.
      - The rendered output notes "lazy_loader detected" and lists the
        symbols sourced from the .pyi stub.
"""

import argparse
import ast
import importlib
import pkgutil
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LARGE_THRESHOLD = 500   # lines; modules above this get [LARGE] tag


# ---------------------------------------------------------------------------
# AST helpers for __init__.py analysis
# ---------------------------------------------------------------------------

def _ast_parse_safe(path: Path) -> ast.Module | None:
    try:
        src = path.read_text(encoding='utf-8', errors='replace')
        return ast.parse(src, filename=str(path))
    except SyntaxError as e:
        print(f'[warn] AST parse failed for {path}: {e}', file=sys.stderr)
        return None
    except OSError as e:
        print(f'[warn] Cannot read {path}: {e}', file=sys.stderr)
        return None


def _extract_init_info(init_path: Path) -> dict:
    """
    Returns a dict with keys:
        eager_star_imports   : list[str]   — 'from .sub import *'
        eager_named_imports  : list[str]   — 'from .sub import Foo, Bar'
        lazy_getattr_keys    : list[str]   — string keys in __getattr__
        all_list             : list[str]   — __all__ contents
        version              : str | None  — __version__ value
        top_level_imports    : list[str]   — 'import X' or 'from X import Y' (non-relative)
        lazy_loader_mode     : bool        — True if lazy_loader.attach_stub detected
        stub_file            : str | None  — path to __init__.pyi if found
        stub_symbols         : list[str]   — symbols parsed from .pyi stub
    """
    info = {
        'eager_star_imports': [],
        'eager_named_imports': [],
        'lazy_getattr_keys': [],
        'all_list': [],
        'version': None,
        'top_level_imports': [],
        'lazy_loader_mode': False,
        'stub_file': None,
        'stub_symbols': [],
    }

    tree = _ast_parse_safe(init_path)
    if tree is None:
        return info

    for node in ast.walk(tree):
        # from .sub import *
        if isinstance(node, ast.ImportFrom) and node.names[0].name == '*':
            module = node.module or ''
            prefix = '.' * (node.level or 0)
            info['eager_star_imports'].append(f'{prefix}{module}')

        # from .sub import Foo, Bar  (non-star relative)
        elif isinstance(node, ast.ImportFrom) and node.level and node.level > 0:
            module = node.module or ''
            prefix = '.' * node.level
            names = ', '.join(a.name for a in node.names)
            info['eager_named_imports'].append(f'{prefix}{module} → {names}')

        # top-level absolute imports (dependency hints)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split('.')[0]
                if top not in info['top_level_imports']:
                    info['top_level_imports'].append(top)
        elif isinstance(node, ast.ImportFrom) and (node.level == 0):
            if node.module:
                top = node.module.split('.')[0]
                if top not in info['top_level_imports']:
                    info['top_level_imports'].append(top)

    # __all__ assignment
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Assign)
            and any(
                isinstance(t, ast.Name) and t.id == '__all__'
                for t in node.targets
            )
        ):
            if isinstance(node.value, (ast.List, ast.Tuple)):
                for elt in node.value.elts:
                    if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                        info['all_list'].append(elt.value)

    # __all__ augmented assignment: __all__ += ['foo', 'bar']
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.AugAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == '__all__'
            and isinstance(node.value, (ast.List, ast.Tuple))
        ):
            for elt in node.value.elts:
                if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                    if elt.value not in info['all_list']:
                        info['all_list'].append(elt.value)
    # __all__.extend(['foo', 'bar'])
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == '__all__'
            and node.func.attr == 'extend'
            and node.args
            and isinstance(node.args[0], (ast.List, ast.Tuple))
        ):
            for elt in node.args[0].elts:
                if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                    if elt.value not in info['all_list']:
                        info['all_list'].append(elt.value)

    # __version__ assignment
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Assign)
            and any(
                isinstance(t, ast.Name) and t.id == '__version__'
                for t in node.targets
            )
            and isinstance(node.value, ast.Constant)
        ):
            info['version'] = str(node.value.value)

    # __getattr__ function — collect string keys (subscript or compare)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == '__getattr__':
            for child in ast.walk(node):
                # dict keys like _LAZY_MAP = {'key': ...}  or  if name == 'key':
                if isinstance(child, ast.Constant) and isinstance(child.value, str):
                    key = child.value
                    if key and not key.startswith('_'):
                        if key not in info['lazy_getattr_keys']:
                            info['lazy_getattr_keys'].append(key)

    # ------------------------------------------------------------------
    # lazy_loader detection
    # Detect calls matching:  lazy_loader.attach_stub(...) or attach_stub(...)
    # where the function name / attribute is 'attach_stub'.
    # ------------------------------------------------------------------
    lazy_loader_detected = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            # lazy_loader.attach_stub(...)
            if isinstance(func, ast.Attribute) and func.attr == 'attach_stub':
                lazy_loader_detected = True
                break
            # attach_stub(...)  — in case imported directly
            if isinstance(func, ast.Name) and func.id == 'attach_stub':
                lazy_loader_detected = True
                break

    if lazy_loader_detected:
        info['lazy_loader_mode'] = True
        stub_path = init_path.with_suffix('.pyi')  # __init__.pyi
        if stub_path.exists():
            info['stub_file'] = str(stub_path)
            info['stub_symbols'] = _extract_pyi_symbols(stub_path)
            # Also pull __all__ from stub if not already populated
            if not info['all_list']:
                info['all_list'] = _extract_pyi_all(stub_path)
        else:
            print(
                f'[warn] lazy_loader detected in {init_path} but no .pyi stub found '
                f'at {stub_path}',
                file=sys.stderr,
            )

    return info


def _extract_pyi_symbols(pyi_path: Path) -> list[str]:
    """
    Parse a .pyi stub file (valid Python AST) and return all imported symbol
    names — both from 'from .sub import Foo, Bar' and 'import X' statements.
    These represent the lazy-loaded public API declared by lazy_loader.attach_stub.
    """
    tree = _ast_parse_safe(pyi_path)
    if tree is None:
        return []

    symbols: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                name = alias.asname if alias.asname else alias.name
                if name and name != '*' and not name.startswith('_'):
                    if name not in symbols:
                        symbols.append(name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.asname if alias.asname else alias.name.split('.')[0]
                if name and not name.startswith('_'):
                    if name not in symbols:
                        symbols.append(name)
    return sorted(symbols)


def _extract_pyi_all(pyi_path: Path) -> list[str]:
    """Extract __all__ list from a .pyi stub file."""
    tree = _ast_parse_safe(pyi_path)
    if tree is None:
        return []

    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Assign)
            and any(
                isinstance(t, ast.Name) and t.id == '__all__'
                for t in node.targets
            )
        ):
            if isinstance(node.value, (ast.List, ast.Tuple)):
                return [
                    elt.value
                    for elt in node.value.elts
                    if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
                ]
    return []


# ---------------------------------------------------------------------------
# Line counter
# ---------------------------------------------------------------------------

def _count_lines(path: Path) -> int:
    try:
        return len(path.read_bytes().splitlines())
    except OSError:
        return 0


# ---------------------------------------------------------------------------
# Module inventory — source tree mode
# ---------------------------------------------------------------------------

def _inventory_from_source(pkg_root: Path) -> list[dict]:
    """Walk filesystem for .py files under pkg_root."""
    entries = []
    for py_file in sorted(pkg_root.rglob('*.py')):
        rel = py_file.relative_to(pkg_root.parent)
        # Convert path to dotted module name
        parts = list(rel.with_suffix('').parts)
        dotted = '.'.join(parts)
        lines = _count_lines(py_file)
        entries.append({
            'module': dotted,
            'path': str(py_file.relative_to(pkg_root.parent)),
            'lines': lines,
            'large': lines >= LARGE_THRESHOLD,
        })
    return entries


# ---------------------------------------------------------------------------
# Module inventory — installed package mode
# ---------------------------------------------------------------------------

def _inventory_from_package(pkg_name: str) -> tuple[list[dict], str | None]:
    """Use pkgutil.walk_packages to enumerate installed package."""
    try:
        pkg = importlib.import_module(pkg_name)
    except ImportError as e:
        print(f'[error] Cannot import {pkg_name}: {e}', file=sys.stderr)
        sys.exit(1)

    pkg_path = getattr(pkg, '__path__', None)
    pkg_file = getattr(pkg, '__file__', None)
    location = str(Path(pkg_file).parent) if pkg_file else None

    entries = []
    if pkg_path:
        for importer, modname, ispkg in pkgutil.walk_packages(
            path=pkg_path,
            prefix=pkg_name + '.',
            onerror=lambda x: None,
        ):
            # Attempt to find source file without importing
            try:
                spec = importer.find_spec(modname)  # type: ignore[union-attr]
                src = spec.origin if spec else None
            except Exception:
                src = None

            lines = _count_lines(Path(src)) if src and Path(src).exists() else 0
            entries.append({
                'module': modname,
                'path': src or '(unknown)',
                'lines': lines,
                'large': lines >= LARGE_THRESHOLD,
            })

    return entries, location


# ---------------------------------------------------------------------------
# Markdown renderer
# ---------------------------------------------------------------------------

def _render_markdown(
    pkg_name: str,
    version: str | None,
    location: str | None,
    init_info: dict,
    inventory: list[dict],
) -> str:
    lines: list[str] = []

    lines.append(f'# Module Map: {pkg_name}')
    lines.append('')
    lines.append('> Generated by opensci-skill/scripts/map-modules.py')
    lines.append(f'> Python {sys.version.split()[0]}')
    lines.append('')

    # ------------------------------------------------------------------
    lines.append('## Package Overview')
    lines.append('')
    lines.append(f'| Key | Value |')
    lines.append(f'|-----|-------|')
    lines.append(f'| Name | `{pkg_name}` |')
    lines.append(f'| Version | `{version or "unknown"}` |')
    lines.append(f'| Location | `{location or "unknown"}` |')
    total_large = sum(1 for e in inventory if e['large'])
    lines.append(f'| Submodules | {len(inventory)} ({total_large} large) |')
    lines.append('')

    # ------------------------------------------------------------------
    lines.append('## `__init__.py` Analysis')
    lines.append('')

    if init_info.get('lazy_loader_mode'):
        lines.append('> **`lazy_loader` detected** — `__init__.py` delegates the public API')
        lines.append('> via `lazy_loader.attach_stub()`. The source of truth is')
        if init_info.get('stub_file'):
            stub_rel = Path(init_info['stub_file']).name
            lines.append(f'> **`{stub_rel}`** (companion `.pyi` stub), not `__init__.py`.')
        else:
            lines.append('> a companion `__init__.pyi` stub — **stub not found at expected path**.')
        lines.append('> Inspect the `.pyi` directly for the complete public API.')
        lines.append('')

        if init_info['stub_symbols']:
            lines.append(f'### Symbols from `.pyi` stub ({len(init_info["stub_symbols"])} total)')
            lines.append('')
            for sym in init_info['stub_symbols']:
                lines.append(f'- `{sym}`')
            lines.append('')
        elif not init_info.get('stub_file'):
            lines.append('_No `.pyi` stub found — public API cannot be determined from source._')
            lines.append('')

    else:
        if init_info['version']:
            lines.append(f'**`__version__`**: `{init_info["version"]}`')
            lines.append('')

        if init_info['eager_star_imports']:
            lines.append('### Eager star imports')
            lines.append('These symbols are loaded at import time:')
            lines.append('')
            for imp in init_info['eager_star_imports']:
                lines.append(f'- `from {imp} import *`')
            lines.append('')

        if init_info['eager_named_imports']:
            lines.append('### Eager named imports')
            lines.append('')
            for imp in init_info['eager_named_imports']:
                lines.append(f'- `from {imp}`')
            lines.append('')

        if init_info['lazy_getattr_keys']:
            lines.append('### Lazy `__getattr__` symbols')
            lines.append('These are only loaded when first accessed:')
            lines.append('')
            for key in sorted(init_info['lazy_getattr_keys']):
                lines.append(f'- `{key}`')
            lines.append('')

        if init_info['all_list']:
            lines.append('### `__all__`')
            lines.append('')
            for name in init_info['all_list']:
                lines.append(f'- `{name}`')
            lines.append('')

        if not any([
            init_info['eager_star_imports'],
            init_info['eager_named_imports'],
            init_info['lazy_getattr_keys'],
            init_info['all_list'],
        ]):
            lines.append('_No eager imports, lazy `__getattr__`, or `__all__` detected._')
            lines.append('')

    # ------------------------------------------------------------------
    lines.append('## Module Inventory')
    lines.append('')
    lines.append(f'`[LARGE]` = ≥{LARGE_THRESHOLD} lines — read carefully, may contain many classes/functions.')
    lines.append('')
    lines.append('| Module | Lines | Notes |')
    lines.append('|--------|-------|-------|')
    for entry in inventory:
        tag = '`[LARGE]`' if entry['large'] else ''
        lines.append(f'| `{entry["module"]}` | {entry["lines"]} | {tag} |')
    lines.append('')

    # ------------------------------------------------------------------
    if init_info['top_level_imports']:
        lines.append('## Dependency Hints')
        lines.append('Top-level packages imported in `__init__.py`:')
        lines.append('')
        for dep in sorted(set(init_info['top_level_imports'])):
            lines.append(f'- `{dep}`')
        lines.append('')

    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description='Build a module map of a Python package for agent consumption.'
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        '--package',
        help='Importable package name (must be installed or on PYTHONPATH)'
    )
    group.add_argument(
        '--source',
        help='Path to the package root directory containing __init__.py'
    )
    parser.add_argument(
        '--output', default='assets/module-map.md',
        help='Output markdown file (default: assets/module-map.md)'
    )
    args = parser.parse_args()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    if args.source:
        pkg_root = Path(args.source).resolve()
        if not pkg_root.is_dir():
            print(f'[error] Source directory not found: {pkg_root}', file=sys.stderr)
            sys.exit(1)
        pkg_name = pkg_root.name
        init_path = pkg_root / '__init__.py'
        location = str(pkg_root)

        if init_path.exists():
            init_info = _extract_init_info(init_path)
        else:
            print(
                f'[warn] No __init__.py at {init_path} — package may be a namespace package, '
                f'use src/ layout, or rely on implicit namespace. Module map will be incomplete.',
                file=sys.stderr,
            )
            init_info = {
                'eager_star_imports': [], 'eager_named_imports': [],
                'lazy_getattr_keys': [], 'all_list': [],
                'version': None, 'top_level_imports': [],
                'lazy_loader_mode': False, 'stub_file': None, 'stub_symbols': [],
            }
        version = init_info.get('version')
        inventory = _inventory_from_source(pkg_root)

    else:  # --package
        pkg_name = args.package
        inventory, location = _inventory_from_package(pkg_name)

        # Try to find __init__.py in the reported location
        if location:
            init_path = Path(location) / '__init__.py'
            if init_path.exists():
                init_info = _extract_init_info(init_path)
            else:
                print(
                    f'[warn] No __init__.py at {init_path} — package may be a namespace package, '
                    f'use src/ layout, or rely on implicit namespace. Module map will be incomplete.',
                    file=sys.stderr,
                )
                init_info = {
                    'eager_star_imports': [], 'eager_named_imports': [],
                    'lazy_getattr_keys': [], 'all_list': [],
                    'version': None, 'top_level_imports': [],
                    'lazy_loader_mode': False, 'stub_file': None, 'stub_symbols': [],
                }
        else:
            init_info = {
                'eager_star_imports': [], 'eager_named_imports': [],
                'lazy_getattr_keys': [], 'all_list': [],
                'version': None, 'top_level_imports': [],
                'lazy_loader_mode': False, 'stub_file': None, 'stub_symbols': [],
            }
        version = init_info.get('version')
        # Also try importlib for version
        if not version:
            try:
                import importlib.metadata
                version = importlib.metadata.version(pkg_name)
            except Exception:
                pass

    # ------------------------------------------------------------------
    md = _render_markdown(pkg_name, version, location, init_info, inventory)
    output_path.write_text(md, encoding='utf-8')

    print(f'Package  : {pkg_name}')
    print(f'Version  : {version or "unknown"}')
    if init_info.get('lazy_loader_mode'):
        stub = init_info.get('stub_file') or 'NOT FOUND'
        print(f'API mode : lazy_loader detected — stub: {stub}')
    print(f'Modules  : {len(inventory)} ({sum(1 for e in inventory if e["large"])} large)')
    print(f'Output   : {output_path}')


if __name__ == '__main__':
    main()
