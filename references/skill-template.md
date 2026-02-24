# SKILL.md Template
# Copy this file to <library-name>/SKILL.md and fill in each [PLACEHOLDER].
# Lines starting with `# INSTRUCTION:` are authoring notes — delete them before delivery.
# Target: ≤500 lines total in the finished file.
# MODE TAGS: Sections/comments marked [Light+] appear in all modes.
#            [Medium+] appear in Medium and Heavy modes only.
#            [Heavy] appear in Heavy mode only.

---
name: [library-name]
# INSTRUCTION: name must match parent directory. Lowercase, hyphens only, no --, ≤64 chars.
description: [One-sentence summary of what the library does]. Use when [concrete use cases].
  Keywords: [keyword1], [keyword2], [keyword3], [function names], [domain terms].
# INSTRUCTION: description ≤1024 chars. This is the PRIMARY TRIGGER — be specific.
# Include function/class names, domain vocabulary, and action verbs.
# Do NOT add a "When to Use" section in the body. All trigger info goes here.
---

# [Library Display Name]

[One sentence: what is this library and what problem does it solve.]

## Version

<!-- built against: [library-name]==[X.Y.Z] -->
Built against: `[library-name]==[X.Y.Z]`
Python: `[X.Y]`
> If using a different version, check `assets/version.txt` and consult changelog for breaking changes.

## Environment Gate

Before any install command, confirm environment + permission with the user and record in `assets/version.txt`:

```text
environment: <env name/path>
python_executable: <path or `python`>
install_permission: yes|no
install_scope: none|current-env|named-env|new-env
package_manager: pip|conda|mamba|uv|other
coverage_profile: workflow|dictionary|hybrid
```

# INSTRUCTION: If install permission is not explicit, treat it as `no`.

## Installation

```bash
# [Light+] Published package (requires install_permission: yes):
pip install [library-name]
# conda install -c conda-forge [library-name]   # if commonly used via conda

# [Medium+] Local source (requires install_permission: yes):
# git clone https://github.com/[org]/[repo].git
# pip install -e .[dev]

# If editable install fails due native build dependencies/toolchain:
# pip install [library-name]
# Record in assets/version.txt:
#   install_mode: wheel
#   editable_install: failed (<short reason>)
```

# INSTRUCTION [Light+]: Verify pip name matches PyPI listing.
# INSTRUCTION [Medium+]: Use pip install -e . for local source libraries only if install_permission=yes.
#   Run: python -c "import importlib.metadata; print(importlib.metadata.version('[pip-name]'))"
#   to confirm installed version. Record in assets/version.txt.
# INSTRUCTION [All modes]: Check pyproject.toml or setup.cfg for optional extras (e.g., [all], [plot], [hdf5]).
#   Some libraries require extras for core workflows: pip install <library>[all]
#   Note any required extras in the Installation section's bash block so users know what to install.

---

## [Domain 1 Name]

# INSTRUCTION [Light+]: Replace with your first functional domain (e.g., "Data I/O", "Preprocessing").
# One runnable Quick Start snippet. Real imports. Real data or minimal synthetic data.
# Snippet must produce output a user can verify.

```python
import [library]

# tested against [library-name]==[X.Y.Z]
# [Short comment explaining what this does]
[minimal_runnable_example = ...]
print([result])
```

# INSTRUCTION: Add `# tested against [library-name]==[X.Y.Z]` as first comment in every snippet.
# Use [VERSION: behavior changed in X.Y — describe] for any version-sensitive line.
# Use [REQUIRES: <pkg>[extra]] for calls that need optional dependencies.

# INSTRUCTION: If this library requires external data files to run (e.g., .hdf5, .msh, .zarr),
# add the following fallback block immediately after the primary example:
#
# ```python
# # --- Synthetic data fallback (no external files required) ---
# import numpy as np
# [synthetic_data = np.random.rand(...)]   # mimics real input shape/type
# [result = library.function(synthetic_data)]
# print([result])
# ```
# If the API expects a library-specific container type (not a raw ndarray),
# build a minimal valid typed object instead of forcing NumPy inputs.
# [Medium+]: verify both the primary and fallback snippets execute without error.

See `references/[domain-1].md` for full API, parameter tables, and patterns.

---

## [Domain 2 Name]

```python
import [library]

# [Short comment]
[minimal_runnable_example = ...]
```

See `references/[domain-2].md`.

---

## [Domain 3 Name]

```python
import [library]

[minimal_runnable_example = ...]
```

See `references/[domain-3].md`.

---

## [Domain 4 Name]

```python
import [library]

[minimal_runnable_example = ...]
```

See `references/[domain-4].md`.

---

## [Domain 5 Name]

```python
import [library]

[minimal_runnable_example = ...]
```

See `references/[domain-5].md`.

---
# INSTRUCTION: Add more domain sections as needed. Aim for 5–10 domains.
# Each section: ~5–15 lines. Keep SKILL.md as a navigator, not a tutorial.
# Deep content (full signatures, parameter tables, gotchas) goes in references/.

## Verification (Medium+)

```bash
python opensci-skill/scripts/verify-snippets.py --root [library-name] --fail-fast
```

# INSTRUCTION: Run this before delivery. All fenced Python snippets must pass.

## API Dictionary (Dictionary/Hybrid)

- `assets/symbol-index.md` — module-level dictionary navigation
- `assets/symbol-index.jsonl` — machine-readable symbol lookup (one record per symbol)
- `assets/symbol-cards/` — per-module symbol cards with signatures + source anchors

# INSTRUCTION: If coverage profile is dictionary or hybrid, include this section and keep paths accurate.

## Quick Reference

# INSTRUCTION: A minimal cheat sheet for the most-used functions/classes.
# One line per item: FunctionName — what it does.
# [Medium+]: populate from assets/api-dump.md.
# [Heavy]: verify each entry against source and note source file in references/.

| Function / Class | Purpose |
|-----------------|---------|
| `[ClassName]` | [one-line description] |
| `[function_name()]` | [one-line description] |
| `[function_name()]` | [one-line description] |
| `[function_name()]` | [one-line description] |
| `[function_name()]` | [one-line description] |

---

## Module Map

# INSTRUCTION [All modes]: Run scripts/map-modules.py first. Paste a condensed summary here.
# Full map is in assets/module-map.md.
# Flag the __init__.py import style (eager / lazy __getattr__ / __all__).

| Submodule | Contents | Notes |
|-----------|----------|-------|
| `[library].[submod1]` | [brief] | |
| `[library].[submod2]` | [brief] | |
| `[library].[submod3]` | [brief] | [LARGE] if >500 lines |

Import style: [eager star-imports / lazy `__getattr__` / `__all__` list / mixed]

See `assets/module-map.md` for full submodule inventory.

---

## References

# INSTRUCTION: List every references/ file with a one-line description.
# Do not add README.md, CHANGELOG.md, or INSTALLATION_GUIDE.md.

- `references/[domain-1].md` — [what deep content is in here]
- `references/[domain-2].md` — [what deep content is in here]
- `references/[domain-3].md` — [what deep content is in here]
- `references/[domain-4].md` — [what deep content is in here]
- `references/[domain-5].md` — [what deep content is in here]
