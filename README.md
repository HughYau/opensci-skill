# 🔬 OpenSci Skill

<p align="center">
  <strong>一个为 AI Agent 构建科学 Python 库知识库的元技能（Meta-Skill）</strong>
</p>

<p align="center">
  <a href="./README_en.md">English</a> ·
  <a href="#快速开始">快速开始</a> ·
  <a href="#工作原理">工作原理</a> ·
  <a href="#贡献技能">贡献技能</a>
</p>

---

## 🧩 这是什么

**OpenSci Skill** 是一个元技能（Meta-Skill）：它不面向某一个具体的科学库，而是教会 AI Agent **如何为任意一个科学 Python 库生成高质量的、可复用的 Skill 知识文件**。

使用 OpenSci Skill，你可以让 Agent 自动完成：
- 🕷️ 爬取、解析目标库的官方文档
- 🔍 提取库的模块结构与公开 API 签名
- 📖 构建符号索引（Symbol Index）用于精准函数查找
- 🗂️ 将知识按功能域组织成结构化的参考文件
- 📄 输出一个标准化的 `SKILL.md` 导航入口

产出的 Skill 可被支持外部知识注入或 skill loader 的 Agent 框架加载（例如Claude Code，OpenCode等），实现对特定领域库的**精准、可更新、可复用**的调用能力。

---

## 💡 动机：为什么需要这个项目

### ❌ 问题一：AI Agent 在专业领域的工具调用不准确

大型语言模型对通用代码有较强的认知，但对**细分领域的科学库**（如 MNE、nilearn、PyMC、scanpy 等）的 API 掌握往往停留在训练数据时的快照。具体表现为：

- 使用了已废弃的 API（deprecated）
- 混淆了不同版本的参数签名
- 对库特有的数据结构（如 `Raw`、`AnnData`）生成错误用法
- 对可选依赖项的安装和导入路径判断错误

### ❌ 问题二：知识无法及时更新

LLM 的训练数据存在时间截止点（knowledge cutoff）。科学库版本升级频繁，API 变化快，而模型无法持续自我更新。在没有外部知识注入的情况下，Agent 对"这个函数的最新签名是什么"根本无从知晓。

### ❌ 问题三：知识难以复用

每次给 Agent 配置一个新的科学库使用场景时，往往需要重新上传文档、重新设计 Prompt、重新验证代码示例。这些工作**无法跨项目、跨团队、跨 Agent 复用**。

### ❌ 问题四：传统文档是 AI 的上下文负担

为人类设计的 Guidebook、Tutorial 和 API Reference 充斥着大量叙述性文字、重复的背景介绍和冗余示例。对 AI Agent 而言，这些内容**直接消耗宝贵的上下文窗口**，却几乎不提供增量信息价值——因为 LLM 对通用概念早已了解。真正需要注入的是那些模型*不知道*的部分：精确的版本签名、库特有的数据容器用法、已废弃 API 的替代方案。

OpenSci Skill 从设计上就以 Agent 为首要读者，**激进地剔除冗余**，只保留模型从训练数据无法可靠获取的高密度知识。

### ✅ OpenSci Skill 的解法

| 问题 | 解法 |
|------|------|
| ❌ 工具调用不准确 | 从库的实际安装包 / 源码中提取 API，确保签名与版本绑定 |
| ❌ 知识不能及时更新 | Skill 可以随库版本重新生成，version.txt 明确标记构建版本 |
| ❌ 知识难以复用 | 标准化的 Skill 目录结构，任何支持该格式的 Agent 都能直接加载 |
| ❌ 文档是上下文负担 | 输出内容以 Agent 为首要读者，剔除冗余叙述，只保留高密度知识 |

---

## ⚙️ 工作原理

### 📁 Skill 的目录结构

由 OpenSci Skill 产出的每个库技能遵循统一结构：

```
<library-name>/
├── SKILL.md                  # 导航入口（必须）
├── assets/                   # 自动生成的机器可读资产
│   ├── version.txt           # 库版本、Python 版本、构建日期
│   ├── module-map.md         # 模块结构图
│   ├── symbol-index.md       # 符号字典索引（人类可读）
│   ├── symbol-index.jsonl    # 符号字典索引（机器可读）
│   ├── symbol-cards/         # 按模块拆分的符号卡片
│   └── docs-cache/           # 爬取/解析后的官方文档缓存
├── references/
│   ├── <domain-1>.md         # 按功能域拆分的深度参考
│   └── ...
└── scripts/                  # 可选：辅助脚本
```

### 📋 产物契约（Skill Contract）

OpenSci Skill 的输出不是"一堆文件"，而是一个有明确规范的可依赖 artifact。

**`SKILL.md` 必须包含的段落：**

| 段落 | 要求 |
|------|------|
| YAML frontmatter | 仅 `name` + `description` 两个字段，`name` 须与目录名一致 |
| `## Version` | 精确版本字符串，格式见下方"版本绑定" |
| `## Installation` | 可运行的安装命令，标注可选 extras |
| 各功能域 Quick Start | 每域至少一个可运行示例，有数据依赖须附合成数据回退块 |
| `See references/<domain>.md` 指针 | 每个功能域末尾须有跳转指针，禁止在 SKILL.md 内嵌深度内容 |

**`assets/symbol-index.jsonl` 每行 schema：**

```jsonc
{
  "symbol": "fit_transform",          // 符号名（不含模块前缀）
  "module": "sklearn.preprocessing",  // 完整模块路径
  "kind": "method",                   // function | class | method | attribute
  "signature": "fit_transform(X, y=None, **fit_params)", // 完整签名
  "doc_url": "https://...",           // 官方文档链接，无则 null
  "since_version": "0.18",            // 引入版本，未知则 null
  "deprecated": null,                 // 废弃信息字符串，或 null
  "confidence": "verified",           // verified | doc-derived | inferred
  "source": "runtime"                 // runtime | ast | docs
}
```

### 🎚️ 三种深度模式

| 模式 | 数据来源 | 速度 | 适用场景 |
|------|----------|------|----------|
| **Light** | 仅爬取官方在线文档 | 快 | 文档完善的公开库 |
| **Medium** | 文档 + 可执行代码示例验证 | 中等 | 需要确认实际 API 行为 |
| **Heavy** | 完整源码遍历 + 论文链接提取 | 慢 | 文档稀疏的科研库 |

### 📊 三种覆盖度档案

| 档案 | 目标 | 适用场景 |
|------|------|----------|
| **Workflow** | 覆盖高频工作流 | 面向任务的助手 |
| **Dictionary** | 广泛的 API 符号查找 | 知识库型助手 |
| **Hybrid** | 工作流 + 字典资产（默认） | 通用 Agent |

### 🛠️ 核心辅助脚本

| 脚本 | 功能 |
|------|------|
| `scripts/map-modules.py` | 提取模块结构与 `__init__.py` 导出 |
| `scripts/fetch-docs.py` | 爬取官方在线文档 → `docs-cache/` |
| `scripts/fetch-local-rst.py` | 解析本地 Sphinx RST 文档 |
| `scripts/extract-api-patterns.py` | 提取公开 API 签名 → `api-dump.md` |
| `scripts/build-symbol-index.py` | 构建符号索引与符号卡片 |
| `scripts/verify-snippets.py` | 执行验证所有代码片段 |

### 🔄 流程总览

```
选择深度模式与覆盖度档案
        ↓
记录环境与安装权限 (version.txt)
        ↓
构建模块图 (map-modules.py)
        ↓
采集文档 (fetch-docs.py / fetch-local-rst.py)
        ↓
构建符号索引 (build-symbol-index.py)          ← Dictionary/Hybrid
        ↓
提取 API 模式 (extract-api-patterns.py)        ← Medium/Heavy
        ↓
划分功能域，编写 references/<domain>.md
        ↓
编写目标库 SKILL.md
        ↓
质量检查 (authoring-checklist.md + verify-snippets.py)
```

---

## 🚀 快速开始

### 为一个库生成 Skill

将 `opensci-skill/` 目录（本仓库）挂载到你的 Agent 可访问的工作区，然后触发 Agent：

```
为 <library-name> 创建一个 opensci skill
```

Agent 会自动运行完整流程并在 `<library-name>/` 目录下输出标准化 Skill 文件。

### 触发关键词（适用于支持 Skill 系统的 Agent）

```
write skill | create skill | new skill | opensci skill |
skill for library | audit skill | library skill | api dictionary
```

### 参考文档

- [references/skill-template.md](references/skill-template.md) — 目标库 `SKILL.md` 的编写骨架
- [references/reference-file-template.md](references/reference-file-template.md) — `references/<domain>.md` 的编写骨架
- [references/authoring-checklist.md](references/authoring-checklist.md) — 交付前质量门控清单

---

## 🤝 贡献技能

> **🎯 目标：为开源社区建立一个 Agent 公共知识库**

每一个基于 OpenSci Skill 生成的科学库 Skill，都是可以被社区复用的知识资产。我们邀请你：

1. 使用 OpenSci Skill 为你熟悉的科学库（PyMC、scanpy、xarray、zarr 等）生成 Skill
2. 将生成的 `<library-name>/` 目录提交到你的仓库（欢迎update你的skill在本仓库readme界面）
3. 在 Issue 中提议你希望覆盖的下一个库

**一个 Skill 的工作量因库的规模和代码质量而异，通常在 Light 模式下只需几分钟。**


---

## 🧭 设计原则

- 🤖 **面向 Agent，而非人类读者**：所有输出格式、密度和组织方式均针对 LLM 上下文消费优化
- 📌 **版本绑定**：每个 Skill 都绑定到构建时的精确版本，避免版本漂移导致的幻觉
- 💰 **Token 经济**：激进地删除 LLM 已知内容，只保留特定于该库的高价值知识
- ✅ **可验证性**：所有代码示例须可执行；无法验证的内容须显式标注 `[UNVERIFIED]`
- 🎚️ **渐进深度**：Light/Medium/Heavy 三档模式，按需投入资源

---

## 📜 许可证

MIT

---

<p align="center">
如果这个项目对你有帮助，欢迎 Star ⭐
</p>
