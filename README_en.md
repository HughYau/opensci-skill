# 🔬 OpenSci Skill

<p align="center">
  <strong>A Meta-Skill for Building Agent Knowledge Bases for Scientific Python Libraries</strong>
</p>

<p align="center">
  <a href="./README.md">中文</a> ·
  <a href="#quick-start">Quick Start</a> ·
  <a href="#how-it-works">How It Works</a> ·
  <a href="#contributing-skills">Contributing Skills</a>
</p>

---

## 🧩 What Is This

**OpenSci Skill** is a meta-skill — it doesn't target any single scientific library. Instead, it teaches an AI Agent **how to generate a high-quality, reusable Skill knowledge file for any scientific Python library**.

Using OpenSci Skill, an Agent can automatically:
- 🕷️ Crawl and parse a library's official documentation
- 🔍 Extract the module structure and public API signatures
- 📖 Build a Symbol Index for precise function lookup
- 🗂️ Organize knowledge into structured reference files by functional domain
- 📄 Output a standardized `SKILL.md` navigator entrypoint

The resulting Skill can be loaded directly by AI Agents that support the Skill format (e.g., GitHub Copilot), enabling **accurate, up-to-date, and reusable** library usage capabilities for that specific domain.

---

## 💡 Motivation: Why This Project Exists

### ❌ Problem 1 — Inaccurate Tool Usage in Specialized Domains

Large language models have strong coverage of general-purpose code, but their knowledge of **niche scientific libraries** (MNE, nilearn, PyMC, scanpy, etc.) is often frozen at training time. Common failure modes include:

- Calling deprecated APIs
- Confusing parameter signatures across versions
- Generating incorrect usage for library-specific data containers (e.g., `Raw`, `AnnData`)
- Mishandling optional dependency imports and install paths

### ❌ Problem 2 — Knowledge Becomes Stale

LLMs have a knowledge cutoff. Scientific libraries release frequently, and APIs change. Without an external knowledge injection mechanism, an Agent has no reliable way to answer "what is the current signature of this function?".

### ❌ Problem 3 — Knowledge Is Not Reusable

Each time an Agent is configured for a new scientific library use case, someone must re-upload docs, re-engineer prompts, and re-validate code examples. This work **cannot be reused across projects, teams, or Agents**.

### ❌ Problem 4 — Human-Readable Docs Are a Context Burden for AI

Guidebooks, tutorials, and API references written for human readers are filled with narrative prose, repeated background explanations, and redundant examples. For an AI Agent, this content **directly consumes precious context window space** while delivering almost no incremental information value — the LLM already knows the general concepts. What actually needs to be injected is what the model *doesn't know*: exact versioned signatures, library-specific container semantics, and migration paths for deprecated APIs.

OpenSci Skill is designed with the Agent as the primary reader. It **aggressively strips redundancy** and retains only high-density knowledge that cannot be reliably derived from the model's training data.

### ✅ OpenSci Skill's Solution

| Problem | Solution |
|---------|----------|
| ❌ Inaccurate tool calls | Extract API from the actual installed package / source; bind signatures to a specific version |
| ❌ Stale knowledge | Skills can be regenerated per library version; `version.txt` records the exact build version |
| ❌ Non-reusable knowledge | Standardized Skill directory layout, directly loadable by any compatible Agent |
| ❌ Docs are a context burden | Agent-first output format — strips narrative; keeps only high-density library-specific knowledge |

---

## ⚙️ How It Works

### 📁 Skill Directory Layout

Every library skill produced by OpenSci Skill follows a consistent structure:

```
<library-name>/
├── SKILL.md                  # Navigator entrypoint (required)
├── assets/                   # Auto-generated, machine-readable artifacts
│   ├── version.txt           # Library version, Python version, build date
│   ├── module-map.md         # Module structure map
│   ├── symbol-index.md       # Symbol dictionary index (human-readable)
│   ├── symbol-index.jsonl    # Symbol dictionary index (machine-readable)
│   ├── symbol-cards/         # Per-module symbol cards
│   └── docs-cache/           # Crawled/parsed official documentation cache
├── references/
│   ├── <domain-1>.md         # Deep reference per functional domain
│   └── ...
└── scripts/                  # Optional: helper scripts
```

### 🎚️ Three Depth Modes

| Mode | Source | Speed | When to Use |
|------|--------|-------|-------------|
| **Light** | Crawl official online docs only | Fast | Well-documented public libraries |
| **Medium** | Docs + verified code examples | Moderate | Need confirmed API behavior |
| **Heavy** | Full source traversal + paper links | Slow | Sparse-doc research libraries |

### 📊 Three Coverage Profiles

| Profile | Goal | Best For |
|---------|------|----------|
| **Workflow** | High-quality guidance for common tasks | Task-focused assistants |
| **Dictionary** | Broad API symbol lookup | Knowledge-base style assistants |
| **Hybrid** | Workflow references + dictionary assets (default) | General-purpose Agents |

### 🛠️ Core Helper Scripts

| Script | Purpose |
|--------|---------|
| `scripts/map-modules.py` | Extract module structure and `__init__.py` exports |
| `scripts/fetch-docs.py` | Crawl official online docs → `docs-cache/` |
| `scripts/fetch-local-rst.py` | Parse local Sphinx RST documentation |
| `scripts/extract-api-patterns.py` | Extract public API signatures → `api-dump.md` |
| `scripts/build-symbol-index.py` | Build symbol index and symbol cards |
| `scripts/verify-snippets.py` | Execute and validate all code snippets |

### 🔄 End-to-End Pipeline

```
Select depth mode and coverage profile
        ↓
Record environment & install permissions (version.txt)
        ↓
Build module map (map-modules.py)
        ↓
Gather documentation (fetch-docs.py / fetch-local-rst.py)
        ↓
Build symbol index (build-symbol-index.py)            ← Dictionary/Hybrid
        ↓
Extract API patterns (extract-api-patterns.py)         ← Medium/Heavy
        ↓
Split functional domains, write references/<domain>.md
        ↓
Write target library SKILL.md
        ↓
Quality gate (authoring-checklist.md + verify-snippets.py)
```

---

## 🚀 Quick Start

### Generate a Skill for a Library

Mount the `opensci-skill/` directory (this repository) into your Agent's accessible workspace, then trigger the Agent:

```
Create an opensci skill for <library-name>
```

The Agent will run the full pipeline and output a standardized Skill under `<library-name>/`.

### Trigger Keywords (for Agents with Skill support)

```
write skill | create skill | new skill | opensci skill |
skill for library | audit skill | library skill | api dictionary
```

### Reference Documents

- [references/skill-template.md](references/skill-template.md) — Template skeleton for a target library's `SKILL.md`
- [references/reference-file-template.md](references/reference-file-template.md) — Template skeleton for `references/<domain>.md`
- [references/authoring-checklist.md](references/authoring-checklist.md) — Pre-delivery quality gate checklist

---

## 🤝 Contributing Skills

> **🎯 Goal: Build a public Agent knowledge base for the open-source community**

Every library Skill generated using OpenSci Skill is a reusable knowledge asset for the community. We invite you to:

1. Use OpenSci Skill to generate Skills for scientific libraries you know well — NumPy, SciPy, Pandas, scikit-learn, MNE, nilearn, PyMC, scanpy, xarray, zarr, and many more
2. Submit the generated `<library-name>/` directory via Pull Request
3. Propose additional libraries you'd like covered in Issues

**The effort to contribute a Skill varies by library size and documentation quality. In Light mode, it typically takes only a few minutes.**

### Contribution Rules

- **Forbidden files** inside any Skill folder: `README.md`, `CHANGELOG.md`, `CONTRIBUTING.md`
- `assets/version.txt` must be present and explicitly state the build version
- All code examples must be runnable, or have an explicit data-dependency note
- Run `scripts/verify-snippets.py` to zero errors before submitting

### Libraries We'd Love Covered

Some high-priority candidates for community Skills:

| Domain | Libraries |
|--------|-----------|
| Neuroscience | MNE-Python, nilearn, Neo, Brian2 |
| Biology / Genomics | scanpy, anndata, biopython, pysam |
| Statistics / Probabilistic ML | PyMC, numpyro, arviz, bambi |
| Earth / Climate | xarray, cf-xarray, MetPy, cartopy |
| Image / Signal | scikit-image, pywavelets, torchaudio |
| Materials / Chemistry | pymatgen, ASE, RDKit, mendeleev |

---

## 🧭 Design Principles

- 🤖 **Agent-first, not human-first**: All output format, density, and organization is optimized for LLM context consumption
- 📌 **Version-bound**: Every Skill is bound to the exact version it was built against, eliminating version-drift hallucinations
- 💰 **Token economy**: Aggressively drop content LLMs already know; keep only library-specific high-value knowledge
- ✅ **Verifiability**: All code examples must be executable; unverified claims are explicitly tagged `[UNVERIFIED]`
- 🎚️ **Progressive depth**: Three-tier Light/Medium/Heavy modes — invest resources proportional to the library's complexity

---

## 📜 License

MIT

---

<p align="center">
If this project helps you, please consider giving it a ⭐ and sharing it with others working on AI-assisted scientific computing.
</p>
