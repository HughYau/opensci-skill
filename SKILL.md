---
name: opensci-skill
description: Help an agent familiarize itself with any scientific Python library or codebase so it can write a high-quality opensci skill for that library. Use when creating, auditing, or refactoring opensci skills for published packages, source-only repositories, namespace packages, or mixed-layout projects. Content is optimized for agent consumption. Trigger keywords: write skill, create skill, new skill, opensci skill, skill for library, audit skill, skill quality, scientific skill, library skill, familiarize library, api dictionary, symbol index, function lookup.
---

# opensci-skill

A meta-skill for familiarizing an agent with a scientific Python library and producing a high-quality opensci skill for it. All content and outputs are optimized for **agent consumption**, not human readers.

## Target Output Structure

Every opensci library skill must follow this layout exactly:

```
<library-name>/
├── SKILL.md                  # Navigator entrypoint — required
├── assets/                   # Gathered artifacts from scripts — agent-readable
│   ├── version.txt           # Library version, Python version, build date (Step 0)
│   ├── module-map.md         # Output of map-modules.py (Step 1)
│   ├── api-dump.md           # Output of extract-api-patterns.py (Medium/Heavy)
│   ├── symbol-index.md       # Dictionary index (Step 2.5)
│   ├── symbol-index.jsonl    # Machine-readable symbol registry (Step 2.5)
│   ├── symbol-cards/         # Per-module symbol cards (Step 2.5)
│   │   ├── <module>.md
│   │   └── ...
│   └── docs-cache/           # Output of fetch-docs.py or fetch-local-rst.py
│       ├── index.md
│       └── ...
├── references/
│   ├── <domain-1>.md         # Deep content, loaded on demand
│   ├── <domain-2>.md
│   └── ...                   # One file per functional domain
└── scripts/                  # Optional: runnable helpers copied from opensci-skill/scripts/
    └── <helper>.py
```

**Forbidden files** (never create inside a skill folder):
`README.md`, `CHANGELOG.md`, `INSTALLATION_GUIDE.md`, `CONTRIBUTING.md`

---

## Step 0 — Choose Depth Mode

**Before doing anything else**, select a mode and confirm with the user:

| Mode | Source | Speed | When to use |
|------|--------|-------|-------------|
| **Light** | Docs/web only — no code execution | Fast | Public library with good online docs |
| **Medium** | Docs + verified code examples | Moderate | Need confirmed API behavior |
| **Heavy** | Full source traversal + paper links | Slow | Niche lib, sparse docs, or research code |

> Prompt: "Which depth mode? Light (docs only) / Medium (docs + verified examples) / Heavy (full source traversal)"

> **Default for autonomous execution** (no user interaction possible): use **Medium** — verified examples without full source traversal.

All subsequent steps are mode-conditional. Sections marked `[Light+]` apply to all modes; `[Medium+]` apply to Medium and Heavy; `[Heavy]` apply to Heavy only.

## Step 0.5 — Environment + Install Permission Gate `[Light+]`

Before any `pip install` / `conda install` action, explicitly confirm execution environment and install policy with the user.

Required prompt (single turn is fine):

> "For this skill build, which environment should I use? (a) existing env with no new installs, (b) specific venv/conda env, (c) create a new env, (d) allow installs in current env. If installs are allowed, which package manager should I use?"

Record the decision in `assets/version.txt`:

```
environment: <env name/path>
python_executable: <path or `python`>
install_permission: yes|no
install_scope: none|current-env|named-env|new-env
package_manager: pip|conda|mamba|uv|other
```

> **Safety default**: if no explicit permission is provided, assume `install_permission: no` and continue with docs/source-only paths where possible.

> **If installs are denied**: do not run install commands. Use `--source` workflows, hosted docs, and tag execution-only claims as `[UNVERIFIED: install denied in selected environment]`.

## Step 0.6 — Coverage Profile Gate `[Light+]`

Choose coverage profile before authoring content:

| Profile | Goal | Typical output size | Recommended for |
|---------|------|---------------------|-----------------|
| **Workflow** | High-quality guidance for common tasks only | Small/medium | Task-focused assistants |
| **Dictionary** | Broad symbol lookup across public API | Large | Knowledge-base style assistants |
| **Hybrid** | Workflow references + dictionary assets | Medium/large | Default for robust agents |

Required prompt:

> "Coverage profile? Workflow / Dictionary / Hybrid. Dictionary/Hybrid will generate symbol index assets for broad API lookup."

Record decision in `assets/version.txt`:

```
coverage_profile: workflow|dictionary|hybrid
```

> **Default for autonomous execution**: `coverage_profile: hybrid`.

### Capture library version (all modes, mandatory)

Immediately after mode selection, before reading any source or docs, record the library version:

```bash
# Preferred — works even if __version__ is dynamic (lazy_loader, hatch-vcs, etc.)
python -c "import importlib.metadata; print(importlib.metadata.version('<pip-name>'))"

# Fallback — works if __version__ is directly set
python -c "import <pkg>; print(<pkg>.__version__)"
```

Write the result to `assets/version.txt`:

```
library: <pkg>
version: X.Y.Z
python: 3.XX
built: YYYY-MM-DD
```

> **Version sanity check**: If `importlib.metadata.version(...)` raises `PackageNotFoundError`, or if `__version__` returns `"0+unknown"` or `"0.0.0"`, the package is not properly installed. Only install if `install_permission: yes`; otherwise continue in docs/source mode and mark execution-dependent claims `[UNVERIFIED]`. A `"0+unknown"` result typically indicates a `hatch-vcs` or `setuptools-scm` dynamic version that was never written because the package was not installed from source with git tags visible.

> **Build-toolchain fallback**: If editable install fails because compiled dependencies are unavailable (C/C++/Fortran/Rust toolchains, system headers, CUDA, etc.), install the published wheel instead (`pip install <pip-name>`) and continue in `--package` mode **only if install permission is granted**. Record this in `assets/version.txt`:
>
> ```
> install_mode: wheel
> editable_install: failed (<short reason>)
> ```

### Preflight dependencies for docs tooling `[Light+]`

Before running `fetch-docs.py`, ensure converter dependencies are available in the selected environment:

```bash
python -m pip install --upgrade requests html2text
```

`fetch-docs.py` can run without `html2text`, but markdown quality drops when it falls back to basic tag stripping. If installs are not allowed, proceed without `--require-html2text` and note reduced fidelity in `assets/version.txt`.

**Why**: API behavior, parameter names, and return types can differ across versions. Every generated file must be stamped with the version it was built against.

---

## Step 1 — Build Module Map `[Light+]`

Run `map-modules.py` to produce `assets/module-map.md` in the **target skill's** `assets/` folder.

```bash
# If package is pip-installable:
python opensci-skill/scripts/map-modules.py --package <library> --output <library>/assets/module-map.md

# If working from source (editable install recommended, permission required):
# [REQUIRES install_permission: yes]
pip install -e /path/to/library
python opensci-skill/scripts/map-modules.py --package <library> --output <library>/assets/module-map.md

# If source-only (not installable):
python opensci-skill/scripts/map-modules.py --source /path/to/library/<pkgname> --output <library>/assets/module-map.md
```

> **`src/` layout**: Modern libraries (e.g., `hatch`/`flit` projects) place the package inside `src/<pkgname>/`. If the repo has no top-level `<pkgname>/` directory, look for `src/<pkgname>/__init__.py`. Pass `--source /path/to/library/src/<pkgname>` (not `src/`). With `--package`, install first (`pip install -e .`) only when install permission is granted.

> **`lazy_loader` detection**: If `map-modules.py` stdout reports **`API mode : lazy_loader detected`**, the `.pyi` stub file (e.g., `<pkg>/__init__.pyi`) is the ground truth for the public API — do NOT rely on `__init__.py` alone. Open the `.pyi` file directly for the full symbol list; it defines `__all__` and all import sources.

> **Flat `__all__` (submodule-list only)**: If `__all__` contains only submodule names (e.g., `['connectome', 'datasets', 'image', ...]`) and no function symbols, the public API lives one level deeper. For each submodule in `__all__`, also inspect `<pkg>/<submodule>/__init__.py` to find its function-level exports. Record symbols as `<pkg>.<submodule>.<fn>` in `assets/module-map.md`.

Also manually inspect `__init__.py` (and `__init__.pyi` if present) and record in `assets/module-map.md`:
- Eager star-imports (`from .submod import *`) — these populate the top-level namespace
- Lazy `__getattr__` entries — only loaded on attribute access (import side-effect: none until accessed)
- `__all__` — the explicit public API contract
- Submodule list and approximate line counts (large files >500 lines are important to flag)

---

## Step 2 — Gather Documentation `[Light+]`

### Light mode — crawl web docs

```bash
# Preferred (html2text available):
python opensci-skill/scripts/fetch-docs.py \
    --url https://<docs-host>/<docs-path>/ \
    --lib <library> \
    --output <library>/assets/docs-cache \
    --require-html2text

# If install_permission=no and html2text is unavailable:
python opensci-skill/scripts/fetch-docs.py \
    --url https://<docs-host>/<docs-path>/ \
    --lib <library> \
    --output <library>/assets/docs-cache
```

> Use the canonical documentation URL for that library (ReadTheDocs, `docs.scipy.org`, project docs site, etc.), not a hardcoded hostname pattern. If no hosted docs exist (README-only project), skip `fetch-docs.py` and rely on local docs/source/docstrings.

> **Large library docs** (scipy, scikit-learn, pandas, etc.): the default `--max-pages 100` covers only a fraction of large doc sites. For comprehensive coverage use `--max-pages 300` or higher, or target a subsection URL (e.g., `https://docs.scipy.org/doc/scipy/reference/`) to focus on API pages.

### Asset triage for large outputs `[Light+]`

Do **not** read large assets end-to-end (`assets/api-dump.md`, full `assets/docs-cache/`). Use targeted retrieval:

1. Start from the current domain's symbol list.
2. Search only for matching symbols/paths in `assets/`.
3. Read narrow windows around matches and extract evidence.
4. Tag unresolved claims as `[UNVERIFIED: verify against <source>]`.

This keeps context usage bounded and improves factual precision.

### Medium/Heavy mode — also gather local RST `[Medium+]`

```bash
# First locate conf.py — common locations: doc/, docs/, doc/source/, docs/source/.
#   find /path/to/library -name conf.py -not -path "*/.*"
# Point --source at the directory that CONTAINS conf.py (not the repo root).
# If no local docs exist (README-only library), skip this step and rely on fetch-docs.py.
python opensci-skill/scripts/fetch-local-rst.py \
    --source /path/to/library/doc \
    --output <library>/assets/docs-cache
```

> **Auto-generated API pages** (e.g., `doc/modules/generated/`, `doc/api/generated/`) are only present after `make html` has been run. If the directory is absent in a fresh checkout, skip it and fall back to source docstrings via `extract-api-patterns.py`.

After fetching docs, locate changelog/migration files. Common locations: `CHANGELOG.md`, `CHANGES.rst`, `HISTORY.rst`, `NEWS.rst`, `RELEASES.md`, `doc/changes/`, `doc/whats_new/`, `docs/changelog/`, `doc/release_notes.rst`. If location is unclear: `find /path/to/library -maxdepth 3 -iname "change*" -o -iname "history*" -o -iname "news*" -o -iname "release*" | grep -v __pycache__`. Append their locations to `assets/version.txt`:

```
changelog: doc/changes/   # or CHANGES.rst, HISTORY.rst, etc.
```

Consult the most recent changelog entry for any deprecations or API changes that affect the current version.

**Sphinx-Gallery examples**: Check `conf.py` for `sphinx_gallery_conf['examples_dirs']` to find the canonical examples directory (often `examples/`, `doc/examples/`, or `tutorials/`). If that key is absent, scan for `.py` files with `# %%` cell markers or `# sphinx_gallery_thumbnail_number` headers. These are high-value real-usage patterns not typically included in RST docs. Note their paths in `assets/version.txt` (e.g., `examples_dir: examples/`) and copy representative scripts to `assets/` for reference.
**Jupyter notebooks**: Check `examples/`, `notebooks/`, and `docs/tutorials/` for `.ipynb` files — many libraries ship tutorial notebooks instead of (or in addition to) Sphinx-Gallery scripts. Treat them as equivalent real-usage pattern sources. Note their paths in `assets/version.txt` (e.g., `notebooks_dir: notebooks/`).

### Heavy mode — full source traversal `[Heavy]`

```bash
python opensci-skill/scripts/extract-api-patterns.py \
    --package <library> \
    --output <library>/assets/api-dump.md \
    --max-depth 2
```

For Heavy mode, also manually read source files for any module >500 lines. Link functions to papers where docstrings cite them (record as `# Paper: <title or DOI>` in `assets/module-map.md`).

**Do NOT write from memory alone.** Verify every non-trivial claim against `assets/`.
Mark anything unverified: `[UNVERIFIED: verify against <source>]`

### Step 2.5 — Build Dictionary Assets `[Light+]`

Generate symbol lookup assets for dictionary-style retrieval.

```bash
# Runtime mode (installed package; preferred for signatures):
python opensci-skill/scripts/build-symbol-index.py \
    --package <library> \
    --max-depth 2 \
    --output-index <library>/assets/symbol-index.md \
    --output-jsonl <library>/assets/symbol-index.jsonl \
    --cards-dir <library>/assets/symbol-cards

# Source mode (no installs required; AST fallback):
python opensci-skill/scripts/build-symbol-index.py \
    --source /path/to/library/<pkgname> \
    --output-index <library>/assets/symbol-index.md \
    --output-jsonl <library>/assets/symbol-index.jsonl \
    --cards-dir <library>/assets/symbol-cards
```

Use dictionary assets as first-line retrieval for future tasks:
1. Query `assets/symbol-index.jsonl` for exact symbol names.
2. Open matching `assets/symbol-cards/<module>.md` entries.
3. Open source files only if implementation details are required.

---

## Step 3 — Domain Split `[Light+]`

Identify 5–10 functional domains from the module map and docs (use 2–4 for very small libraries). Each domain becomes one `references/<domain>.md` file.

Ask:
- What are the major user-facing workflows? (e.g., I/O, preprocessing, fitting, visualization)
- What submodules or classes anchor each workflow?
- What is out of scope for typical use?

Also check `pyproject.toml` for a `[tool.importlinter]` section — if present, its contracts precisely document the intended module layering and dependency rules, and should be treated as authoritative input to domain boundary decisions.

> **Large library scope** (>100 submodules, e.g., scipy, scikit-learn, pandas):
> - For `coverage_profile: workflow`, keep narrative coverage to 5–10 high-value submodules and add a `## Scope` note listing out-of-scope areas.
> - For `coverage_profile: dictionary|hybrid`, still generate broad symbol index assets (`symbol-index.*`, `symbol-cards/`) even if narrative references remain scoped.

---

## Step 4 — Write `references/` Files

Use `references/reference-file-template.md` as the skeleton. For each file:

- Mode-conditional depth (see depth table at top of template)
- One cohesive functional domain per file
- TOC if file will exceed 100 lines
- No links to other `references/` files (one level deep)
- Data-dependency fallback: if examples require `.hdf5`, `.fif`, or other data files, provide a synthetic-data fallback block:

```python
# DATA DEPENDENCY: real usage requires an external data file (e.g., .hdf5, .fif, .zarr).
# Synthetic fallback for API verification:
import numpy as np
data = np.random.rand(100, 3)          # mimics real input shape/dtype
result = <library>.<function>(data)    # replace with real file-loading call
# e.g.: result = <library>.load('<datafile>')
```

If the API expects a library-specific container (not a raw `ndarray`), build a minimal valid typed object instead of forcing NumPy input. Prefer official toy datasets or constructors when available.

```python
# Typed fallback pattern for structured APIs
# Example idea: construct the smallest valid object accepted by the function.
# Do not pass bare NumPy arrays when the API expects a rich container type.
obj = <library>.<ContainerClass>(<minimal_valid_fields>)
result = <library>.<function>(obj)
```

**Optional-dependency fallback**: If a function requires an optional install extra (e.g., `<library>[plot]`, `<library>[viz]`, `<library>[io]`), either (a) wrap the example in `try/except ImportError` with an explanatory comment, or (b) prefix the example with `# REQUIRES: pip install <pkg>[<extra>]`. Use the `[REQUIRES: pkg[extra]]` annotation tag in the signature block (defined in `references/reference-file-template.md`).

```python
# REQUIRES: pip install <library>[<extra>]
try:
    from <library> import <optional_module>
    <optional_module>.<function>(data)
except ImportError:
    print("Install <library>[<extra>] for this feature.")
```

---

## Step 5 — Write Target Skill's `SKILL.md`

Use `references/skill-template.md` as the skeleton. Non-negotiable rules:

| Rule | Detail |
|------|--------|
| Frontmatter fields | `name` and `description` only — no other fields |
| `name` format | `^[a-z][a-z0-9-]*$`, matches directory name, no `--`, ≤64 chars |
| `description` role | Primary trigger — include what + when + concrete keywords, ≤1024 chars |
| Coverage profile | `assets/version.txt` includes `coverage_profile` and generated outputs follow that profile |
| Body size | ≤500 lines total |
| Runnable snippets | All Quick Start code must run without modification, or have explicit data-dependency fallback |
| Dictionary assets | For `coverage_profile: dictionary|hybrid`, `assets/symbol-index.md`, `assets/symbol-index.jsonl`, and `assets/symbol-cards/` are required |
| Reference depth | One level only — `references/*.md` may not chain to other reference files |
| Confidence tagging | `[UNVERIFIED: verify against <source>]` on any unconfirmed claim |
| No trigger section in body | Never add "When to Use" or "Trigger" section to SKILL.md body |
| Token economy | Keep niche/library-specific content aggressively; cut generic Python boilerplate |
| No forbidden files | Never create README.md, CHANGELOG.md, etc. inside skill folders |
| `## Version` section | Target skill's `SKILL.md` must contain a `## Version` section with exact version string (see `references/skill-template.md`). All Quick Start code blocks must include a comment: `# tested against <pkg>==X.Y.Z` |

---

## Step 6 — Quality Gate

Run through `references/authoring-checklist.md` before declaring done.
Every item must pass. Zero exceptions.

For Medium/Heavy modes, execute snippet verification before delivery:

```bash
python opensci-skill/scripts/verify-snippets.py --root <library> --fail-fast
```

For `coverage_profile: dictionary|hybrid`, verify dictionary assets exist and are populated before delivery.

---

## References

- `references/authoring-checklist.md` — Pre-delivery quality gate (run before every commit)
- `references/skill-template.md` — Copy-paste SKILL.md skeleton for a new library skill
- `references/reference-file-template.md` — Copy-paste skeleton for a single `references/<domain>.md`
- `scripts/fetch-docs.py` — Crawl official docs site → `assets/docs-cache/`
- `scripts/fetch-local-rst.py` — Walk local Sphinx RST directory → `assets/docs-cache/`
- `scripts/extract-api-patterns.py` — Extract public API signatures → `assets/api-dump.md`
- `scripts/build-symbol-index.py` — Build `symbol-index.jsonl` + `symbol-cards/` dictionary assets
- `scripts/map-modules.py` — Map package structure and `__init__.py` imports → `assets/module-map.md`
- `scripts/verify-snippets.py` — Execute fenced Python blocks in `SKILL.md` + `references/*.md`
