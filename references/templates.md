# 产物模板与 manifest.json 规范

所有 Markdown 产物按本文件模板生成；`manifest.json` 是组装 HTML 学习伴侣的结构化清单，字段必须与本文件一致。

模板给的是骨架，不是填空题。小标题照搬，里面的文字要按 `references/pedagogy.md` 写成人话——尤其是 7.1 节列的几种机器味，出现就改。同一本书里不同章节的篇幅允许差很多，难点写长，顺的地方写短。

## 1. 学习总纲（知识库根 SKILL.md）

```markdown
---
name: <书名-或-主题>（点化学习总纲）
---

# <书名/主题> 点化学习系统

## 这本书/这个主题在讲什么
<核心论点 2~3 句：回答什么问题、作者主张、论证主线>

## 全书心智模型
<1 张 Mermaid 图：全书核心概念与主线关系>

## 学习路径（推荐顺序）
| 步骤 | 章节 | 主题 | 前置 | 检查点 |
|---|---|---|---|---|
| 01 | ch01 | ... | 无 | 通过 ch01 自测 |
| 02 | ch02 | ... | ch01 | ... |

## 章节索引
- 第 1 章 <标题>（难度 ★☆☆）→ chapters/ch01-*.md
- ...

## 前置知识（零基础缺口补讲）
| 缺口 | 对应补讲位置 | 学完标志 |
|---|---|---|

## 术语表 / 模式库 / 速查表 入口
```

## 2. 章节点化卡（chapters/chNN-*.md）

```markdown
# 第 N 章：<标题>

- **难度**：★☆☆ | **预估学时**：X 小时 | **前置**：第 M 章、概念 <Y>

## 学习目标
学完本章，你能：<动词化、可验证、与自测题一一对应的 2~4 条>

## 一句话核心
<最重要的一句话>

## 零基础讲解
<白话展开。每个术语首次出现即加粗并给出白话定义，同步进术语表。不跳步，每个推导给出可复核步骤>

### 概念 1：<名称>（难度：基础/进阶/高难）
<白话定义 → 类比（注明边界）→ 图示 → 实例>

### 概念 2：...
<按依赖顺序展开，先讲前置再讲后续>

## 图示
<至少一个 Mermaid/HTML 图 + "看图说明"（该图看什么、能得出什么结论）>

## 类比与实例
- 类比：<贴近日常的类比 + 失效边界>
- 实例：<完整、带步骤带结果的可验证例子>

## 常见误解
- 别以为 <错误认知>——实际上 <正确解释，附理由>

## 自测题（答案）
1. <单选题/多选题/填空题/简答题>（答案：<A/B/...>；解析：<为什么>）
2. ...

## 复习锚点
- <过几天回来能一句话复述的 2~3 条>
```

## 3. 概念页（concepts/<slug>.md）

```markdown
# <概念名>

- **难度**：基础/进阶/高难 | **涉及章节**：第 X、Y 章

## 一句话定义
<白话>

## 为什么重要
<它在全书知识体系里的位置、解决什么问题>

## 图示
<概念地图/关系图>

## 详解
<零基础讲解 + 类比 + 实例>

## 常见误解
...

## 在书中出现的脉络
| 章节 | 语境 | 关键结论 |
|---|---|---|

## 相关概念
- <前置概念>、<后续概念>（互相链接）
```

## 4. 学习路径（paths/learn.md）

```markdown
# 学习路径：<名称>

<面向谁、覆盖什么、终点能力>

## 路径总览
<Mermaid 流程图：步骤 1 → 2 → 3 ...>

## 步骤 N：<主题>
**目标**：<学完你能……>
**阅读**：ch0N-*.md
**检查点**：完成自测题（≥80% 正确率）
**复习**：相关抽认卡标签 <tag>

...

## 学完全程后
- 你能：<综合能力清单>
- 综合检验：<跨章综合题/项目式任务>
```

## 5. 测验（quiz.md）

```markdown
# <书名> 测验

## 第 N 章测验（检查点）
### Q1.（单选/多选/填空/简答）<题干>
- A. ... B. ... C. ... D. ...
**答案**：<...>
**解析**：<为什么对/为什么错>

## 综合测验（多章联考）
...

## 最终检验
<全书综合任务：一个需要整合多章知识的可完成项目/案例分析，附评分要点>
```

## 6. 抽认卡（flashcards.md）

```markdown
# <书名> 抽认卡

## 第 N 章
### 卡片：<问题/线索>
- **背面**：<答案>
- **标签**：<tag1, tag2>
- **章节**：ch0N
```

正面只放问题/线索，绝不放答案。

## 7. 术语表（glossary.md）

```markdown
# 术语表

| 术语 | 白话定义 | 首次出现 | 章节 |
|---|---|---|---|
| <术语> | <一句话白话> | ch01 | 第 1 章 |
```

## 8. 模式库（patterns.md）

```markdown
# 模式与框架库

## 框架：<名称>
<作者用于分析问题的固定结构，何时用、怎么用>

## 决策规则
<if/else 形式的判断路径>

## 反模式
<作者明确反对的做法 + 为什么 + 替代方案>
```

## 9. 速查表（cheatsheet.md）

```markdown
# 速查表

## 公式/规则
| 场景 | 内容 |
|---|---|

## 常用命令/参数/流程步骤
...
```

## 10. manifest.json schema

```json
{
  "slug": "book-slug",
  "title": "书名/主题",
  "subtitle": "一句话副标题",
  "book": {
    "title": "书名",
    "author": "作者",
    "source": ["来源文件名或链接"]
  },
  "audience": "零基础 / 有基础",
  "goal": "学习目标描述",
  "learningPath": [
    {"step": "01", "title": "步骤标题", "chapterIds": ["ch01"], "checkpoint": "检查点说明"}
  ],
  "chapters": [
    {
      "id": "ch01",
      "title": "第 1 章：标题",
      "file": "chapters/ch01-xxx.md",
      "difficulty": 1,
      "source": {"file": "教材名", "page": 45},
      "prerequisites": ["ch00", "c03"]
    }
  ],
  "concepts": [
    {
      "id": "c01",
      "title": "概念名",
      "file": "concepts/xxx.md",
      "chapterIds": ["ch01"],
      "difficulty": "基础 | 进阶 | 高难",
      "source": {"file": "教材名", "page": 46},
      "prerequisites": ["c00"],
      "depthFragment": "concepts/c01-depth.md",
      "externalTaxonomyId": "math.grade8.quadratic-equation"
    }
  ],
  "glossary": [
    {"term": "术语", "def": "白话定义", "chapterId": "ch01"}
  ],
  "patterns": {"file": "patterns.md"},
  "cheatsheet": {"file": "cheatsheet.md"},
  "quizzes": [
    {
      "id": "q01",
      "chapterId": "ch01",
      "type": "single|multi|blank",
      "question": "题干",
      "options": ["A", "B", "C"],
      "answer": 0,
      "explain": "解析",
      "relatedConceptId": "c01",
      "source": {"file": "习题集", "page": 12}
    }
  ],
  "flashcards": [
    {"id": "f01", "chapterId": "ch01", "front": "问题", "back": "答案", "tags": ["tag"]}
  ]
}
```

### 知枢新增字段说明

| 字段 | 类型 | 作用 |
|---|---|---|
| `chapters[].source` / `concepts[].source` / `quizzes[].source` | `{file, page}` 或字符串 | 原文出处脚注，页面顶部显示 |
| `chapters[].prerequisites` / `concepts[].prerequisites` | id 数组 | 前置知识（章节 id 或概念 id），渲染为前置知识条；诊断答错时沿此链回溯 |
| `concepts[].depthFragment` | 文件路径 | 第一性原理深度推导片段（Markdown），概念页底部折叠显示 |
| `concepts[].difficulty` | 基础/进阶/高难 | 高难概念触发深度通道 |
| `concepts[].externalTaxonomyId` | 字符串 | 可选，对应 cn-math-taxonomy 等外部课标图谱的节点 id |
| `quizzes[].relatedConceptId` | 概念 id | 答错时关联的根因概念，诊断倒推的起点 |
| `quizzes[].optionMisconceptions` | 数组 | 每个选项对应的误解 id（single 类型），选错时弹出误解卡片 |

### 知枢新增：依赖分级与误解

```json
{
  "prerequisites": [
    {"id": "c01", "type": "hard"},
    {"id": "c02", "type": "soft"},
    {"id": "c03", "type": "recommended"}
  ],
  "misconceptions": [
    {"id": "m01", "wrong": "导数就是切线斜率", "correction": "导数是瞬时变化率，切线斜率只是几何解释"}
  ]
}
```

- `type: hard` = 必须先会（红色"必"标签）
- `type: soft` = 建议先看（灰色"荐"标签）
- `type: recommended` = 拓展阅读（蓝色"拓"标签）
- 旧格式字符串数组 `["c01"]` 兼容，默认按 hard 处理
- `misconceptions` 是全局列表，测验选项通过 `optionMisconceptions` 引用

字段约束：`chapterIds`/`chapterId` 必须与 `chapters[].id` 一致；`quizzes[].answer` 类型与 `type` 匹配；`quizzes[].explain` 必填；`prerequisites` 不得形成环；`depthFragment` 文件存在时才会被渲染。

## 11. 跨书总览（`00-跨书总览/README.md`）

```markdown
# 跨书总览：<主题>学习路线

## 推荐学习顺序
| 顺序 | 书 | 为什么在这个位置 | 能力里程碑 |
|---|---|---|---|
| 1 | <书 A> | <依赖关系/难度依据> | 学完你能…… |
| 2 | <书 B> | …… | …… |

## 各书定位（一句话）
- 《A》：<覆盖什么、不适合什么>
- 《B》：……

## 学习节奏建议
<每周投入、先读哪几章、什么时候交叉复习>

## 总入口
打开 `index.html` 总学习手册，按顺序推进；每本书的进度独立保存。
```

## 12. 跨书概念映射表（`00-跨书总览/跨书概念映射表.md`）

```markdown
# 跨书概念映射表

对照各书真实 `manifest.json` 生成，禁止凭记忆填写。

| 概念 | 书 A 章节 | 书 B 章节 | 书 C 章节 | 口径差异 |
|---|---|---|---|---|
| <概念名> | 第 N 章 | 第 M 章 | — | <若定义不同，写差异与适用场景> |

## 使用方式
- 先在某本书学到该概念，再到映射表看其他书如何讲同一概念（交叉复习）。
```

## 13. 综合检验建议（`00-跨书总览/综合检验建议.md`）

```markdown
# 综合检验建议

## 跨书整合题
### 题 1：<需要同时用到 A、B 两本书知识的任务>
- 涉及：A 第 X 章、B 第 Y 章
- 要求：<可验证的产出>
- 评分要点：<3~4 条>

## 进阶路线
1. <路线一：偏理论/偏工程/偏竞赛>
2. ……
```

## 14. 交付说明（`交付说明.md`，两种交付模式都必须有）

```markdown
# <主题> · 交付说明

## 一、这是什么
<一句话：N 本书点化后的系统化知识库手册，总入口 index.html>

## 二、目录结构
| 路径 | 说明 |
|---|---|
| `index.html` | 总学习手册（单文件，统一入口） |
| `index.md` | Markdown 导航页 |
| `README.md` | 部署与使用说明 |
| `.nojekyll` | GitHub Pages 关闭 Jekyll |
| `00-跨书总览/` | 推荐顺序 / 概念映射 / 综合检验 |
| `NN-书名/` | 该书知识库 + 学习伴侣 HTML + manifest |
| `_build/`（仅 full） | 整合脚本与抽取数据 |
| 各书 `_work/`（仅 full） | 抽取原文、页面截图、验证脚本与截图 |

## 三、怎么用
<双击 index.html / 切换书 / 导航 / 搜索 / 进度>

## 四、部署 GitHub Pages
<三步：解压到仓库根 → git push → Settings→Pages→main/(root)>

## 五、验证结论
<跑过哪些验证、结果如何、已知限制>

## 六、取舍说明
<体积来源、中间产物是否可删、版权提示>
```

## 15. 单书 manifest 的 companion 字段（可选）

```json
{"companion": "<slug>学习伴侣.html"}
```
`build_handbook.py` 会优先使用该字段定位单书 HTML；缺省时自动选择目录内最大的 `*.html`。

## 16. `index.md`（build_handbook.py 自动生成）

包含：总入口链接、四书统计表、跨书总览链接、使用方法、目录结构、验证摘要。
