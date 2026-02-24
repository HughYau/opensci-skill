# Reference File Template
# Copy this file to <library-name>/references/<domain>.md and fill in each [PLACEHOLDER].
# Lines starting with `# INSTRUCTION:` are authoring notes — delete them before delivery.
# Add a TOC if this file will exceed 100 lines.
# MODE TAGS: [Light+] all modes | [Medium+] Medium+Heavy | [Heavy] Heavy only

<!-- built against: [library-name]==[X.Y.Z] -->

# Domain: [Domain Name]
# INSTRUCTION: Replace with the domain this file covers (e.g., "Preprocessing", "I/O").

<!-- TOC (add when file exceeds 100 lines)
- [Section 1 Name](#section-1-name)
- [Section 2 Name](#section-2-name)
- [Section 3 Name](#section-3-name)
-->

---

## Depth by Mode

# INSTRUCTION: Fill in this table during authoring so reviewers know what was verified.
# Delete this section before delivery.

| Item | Light | Medium | Heavy |
|------|-------|--------|-------|
| Signatures | From docs/docstrings | Verified via `extract-api-patterns.py` | Verified in source + `# Source:` annotated |
| Examples | Doc-based, may be untested | Executed, output confirmed | Executed + data-dependency fallback tested |
| Parameters | Copied from docs | Cross-checked against source defaults | Full `inspect.signature` verified |
| Synthetic fallback fidelity | Shape-only mock is acceptable | Uses realistic type/shape for API validation | Uses minimal valid typed container matching production API |
| Paper links | Not required | Not required | `# Paper: <DOI>` on algorithm functions |

---

## [Section 1: Primary Class or Function Group]

# INSTRUCTION: Cover one cohesive group of functions/classes per section.
# Include: full signature, parameter table, runnable example, common pitfalls.
# [Heavy]: add `# Source: <file>.py:L<n>` after the signature block.
# [Heavy]: add `# Paper: <DOI or citation>` if function implements a published algorithm.

### `[ClassName or function_name](param1, param2, ...)`

**Signature:**
```python
[library].[ClassName](
    param1: [type],           # [brief description]
    param2: [type] = [default],  # [brief description]
    param3: [type] = [default],  # [brief description]
)
# [Heavy] Source: [submodule/file.py]:L[line number]
# [Heavy] Paper: [Author et al., Year — DOI or arXiv link]  (if applicable)
# [DEPRECATED in X.Y: use replacement_fn() instead]   — tag deprecated APIs
# [ADDED in X.Y]                                       — tag APIs new in this version
    # [REQUIRES: [library][extra]]                         — tag optional-dependency functions
# INSTRUCTION: Use [REQUIRES:] when the function raises ImportError unless an optional install
# extra is present (e.g., `pip install <library>[<extra>]`). Also wrap the example block in
# try/except ImportError, or prefix it with `# REQUIRES: pip install <pkg>[<extra>]`.
# INSTRUCTION: Optional dependency installs require explicit install permission in the selected environment.
# INSTRUCTION: Resolve `<extra>` names from `pyproject.toml` (`[project.optional-dependencies]`)
# or `setup.cfg` (`extras_require`) rather than guessing.
```

**Key Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `param1` | `[type]` | — | [what it controls] |
| `param2` | `[type]` | `[default]` | [what it controls] |
| `param3` | `[type]` | `[default]` | [what it controls] |

**Example:**
```python
import [library]
import numpy as np  # include only if actually needed

# [Comment explaining the example goal]
[obj] = [library].[ClassName](
    param1=[value],
    param2=[value],
)
[result] = [obj].[method]([arg])
print([result])  # expected: [what user sees]
```

# INSTRUCTION: If the example requires external data files, add a synthetic fallback:
# ```python
# # --- Synthetic data fallback ---
# import numpy as np
# [data = np.random.rand(...)]   # shape/dtype matching real input
# [result = library.ClassName(data)]
# print([result])
# ```
# If the API requires a rich object (AnnData/xarray/Raw/etc.), instantiate a
# minimal valid typed object instead of passing a bare ndarray.
# [Medium+]: execute both blocks and confirm output.

**Common pitfalls:**
- [Pitfall 1: e.g., "param2 expects Hz not ms — a common unit mistake"]
- [Pitfall 2: e.g., "data must be preloaded before calling this method"]
- [VERSION: param `foo` renamed to `bar` in X.Y]

---

## [Section 2: Next Function or Class Group]

### `[function_name](arg1, arg2, **kwargs)`

**Signature:**
```python
[library].[function_name](
    arg1: [type],
    arg2: [type] = [default],
    **kwargs,
) -> [return_type]
# [Heavy] Source: [submodule/file.py]:L[line number]
```

**Key Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `arg1` | `[type]` | — | [description] |
| `arg2` | `[type]` | `[default]` | [description] |

**Example:**
```python
import [library]

[result] = [library].[function_name](
    arg1=[value],
    arg2=[value],
)
print([result])
```

**Common pitfalls:**
- [Pitfall 1]

---

## [Section 3: Patterns]

# INSTRUCTION: Add a patterns section if there are recurring multi-step workflows
# specific to this domain that are not obvious from individual function docs.
# [Heavy]: annotate each step with source file reference if non-obvious.

### [Pattern Name]

```python
import [library]

# Step 1: [what this does]
[step1 = ...]

# Step 2: [what this does]
[step2 = ...]

# Step 3: [what this does]
[step3 = ...]
print([final_result])
```

---
# INSTRUCTION: Repeat sections as needed for this domain.
# Keep content focused on what is NOT obvious from training data.
# If a section is thin, merge it with a related section rather than padding.
# For exhaustive API listing, rely on assets/symbol-cards instead of bloating this file.
# Do NOT link to other references/ files from here.
# [UNVERIFIED: verify against <source>] — tag any claim not confirmed from source or docs.
