---
name: zhishu
display_name: 知枢学习系统
version: 1.7.0
description: 把任何学习材料——一个知识点、一组题、一份课件、一本书、多本书——变成"按依赖带你走、答错倒推根因、难点从零推透"的单文件交互学习网页。自动识别输入形态并选最轻的流水线：知识点走第一性原理推导、题目走诊断、课件走单章、书走整书成课、多书走整合入口。适用于"讲一下这个概念""把这堆题做成诊断卡""把这份课件做成能学的页""把这本书吃透""把几本书整合成一门课"。
---

# 知枢（zhishu）：贯通式个人学习系统

给一份材料，不管是一个知识点关键词、一组题、一份课件、一本书还是多本书，产出一个单文件 HTML：按依赖拓扑带你学，答错时沿前置链倒推到真正没掌握的根因，高难概念折叠展开完整推导。

## 它解决什么问题

- 材料存下来就算学过了，拆不开、讲不透，也没人考你。
- 错题只知道不会，不知道是前面哪个前置概念没懂。
- 难点只给结论不给推导，公式跳步，读两行就断链。

## 输入形态识别

拿到材料先判断形态，再决定走哪条流水线。整书流程最重，只有真的是一本书时才用。

| 输入形态 | 例子 | 流水线 | 产出 |
|---|---|---|---|
| 一个知识点关键词 | "讲一下隐函数求导""SVM 是怎么回事""从初中数学推到傅里叶变换" | 第一性原理路线：逆推依赖链→正向推导四件套→差生通读 | 单文件推导 HTML，含 KaTeX、Canvas 演示、折叠推导步骤 |
| 一组题/试卷 | 一堆习题、一份期末卷、一组错题 | 诊断路线：给每题标 `relatedConceptId` 和 `prerequisites`→建题目依赖图 | 诊断测试 HTML，答错倒推根因，跳转到对应知识点 |
| 一份课件/讲义/单篇 | 一个 PPT、一章讲义、一篇长文 | 轻量单章路线：拆 3–5 个核心概念→精讲+小测 | 单章学习页，不建总入口 |
| 一本书 | 一本教材、专著、实验指导 | 整书成课路线（下面八阶段） | 完整学习伴侣 HTML（章节+概念+测验+卡片+术语） |
| 多本书 | 同领域多本、跨教材+习题集+讲义 | 多书整合路线：概念去重→跨书映射→总入口 | index.html + 各书伴侣 |
| 混合材料 | 书+自己的笔记+几篇论文 | 按主体选主线，其他作为补充模块挂进概念页 | 同上，加引用/笔记模块 |

所有形态都带的能力：KaTeX 公式、出处脚注、深度推导折叠、去 AI 味写作、进度本地保存。抽认卡、术语表、模式库、GitHub Pages 部署、外部课标图谱按材料规模决定，材料不够大就不加。

形态判断不准时问一句："你是想把这一个概念彻底搞懂，还是把这份材料系统学一遍？"

## 交付形态

确定形态后，生成内容之前先问清楚要哪种交付：

| 选项 | 产出 | 适用 |
|---|---|---|
| A. 本地单文件 HTML | 一个 `.html` 文件，双击就能开，所有数据内联 | 自己学、临时用、不想建仓库 |
| B. GitHub Pages 完整包 | 一个文件夹：`index.html` + 各书目录 + `manifest.json` + `.nojekyll` + `README.md` + 部署说明，可直接 push 到 GitHub 仓库开 Pages | 想长期维护、分享给别人、跨设备同步进度 |

两种产出的文件结构和打包方式不同。A 是一个文件，B 是一整套目录，选错要返工，所以不要默认选 A。用户没说就问："要一个本地双击就能开的 HTML，还是一套能传 GitHub Pages 的完整目录？"

选 B 时再确认两件事：有没有现成仓库（没有就给建仓命令），以及要不要我直接推（要 PAT）。只给包不推也行。

## 视觉层（默认深色）

产物默认套一层深色视觉：`#080d1a` 底、`#101a2f` 面板、钴蓝 `#5c7cff`、鲸青 `#16c7d9`、衬线标题、点阵底纹。浅色是暖灰纸感 `#edf1f8`，不是纯白。设计口径和验收方法见 `references/visual-theme.md`。

视觉层只改样式，不改 DOM、路由和数据结构。构建完成后注入：

```bash
# 单页
python3 scripts/apply_visual_theme.py --file <page.html>

# 目录：默认处理 index.html 和 *学习伴侣.html
python3 scripts/apply_visual_theme.py --root <知枢目录>

# 目录：全部 HTML 都处理
python3 scripts/apply_visual_theme.py --root <知枢目录> --all-html

# 页面初始是浅色：改成深色初始态，主题按钮仍可切回浅色
python3 scripts/apply_visual_theme.py --file <page.html> --force-dark
```

脚本会插入 `#zs-visual-theme` 和 `#zs-visual-init`，重复执行只替换不叠加。建议顺序：构建 → 注入视觉 → 验证 → 打包。先打包再注入，zip 里会是旧皮肤。

视觉层不是所有页面都适合强套：Canvas/WebGL 主视觉、依赖纯白背景做图像混合、已有完整品牌视觉的页面，先备份再试。旧多书总入口、单书伴侣、旧版从零推导页已实测可用。

## 六层架构

```
L5 交付层   单文件HTML / GitHub Pages / 进度本地保存
L4 诊断层   随机抽题 → 答错沿 prerequisites 倒推 → 跳转+展开深度片段
L3 教学生成  常规章节精讲（book通道）+ 高难概念第一性原理推导（depth通道）
L2 摄入层   extract_text.py 抽文本，每段带页码出处
L1 骨架层   书内概念依赖图（必选）+ 课标图谱 externalTaxonomyId（可选）
```

## 工作流

先读 `references/workflow.md`。下面八阶段只对整书和多书生效。输入是"一个知识点"或"一组题"时走上面的最短路径，不套八阶段。

**Phase 0 输入确认**：清点材料，确认学习目标、受众基线、交付模式（final/full）和交付形态（本地单文件还是 Pages 完整包）。

**Phase 1 抽文本拆结构**：`scripts/extract_text.py` 按格式抽文本。数学或扫描版 PDF 抽出来是乱码的，弃用文本，改用 Read 按页读图。产出结构地图，每章切分语料。

**Phase 2 抽概念建依赖图**：逐章精读，产出概念清单、书内依赖图（每个概念标 `prerequisites`）、难点地图（标 `difficulty: 高难` 的概念）、心智模型。哪些概念走深度通道在这一步定下来。

**Phase 3 双通道生成内容**：
- 普通章节/概念按 `references/templates.md` 的模板写精讲：学习目标、一句话核心、类比、实例、常见误解、自测题。
- 高难概念走深度通道：逆推依赖链到读者基线，正向推导四件套（定义/类比/代数过程/数值算例），写完用 `pedagogy.md` §11 的差生通读清单检查，产出 `concepts/cXX-depth.md`。

**Phase 4 路径与记忆系统**：按依赖图拓扑排序排学习路径，生成测验（每题标 `relatedConceptId`）、抽认卡、术语表、模式库、速查表。

**Phase 5 组装单书**：写 `manifest.json`（schema 见 `templates.md` §10，注意 source、prerequisites、depthFragment、externalTaxonomyId 四个新字段），跑：

```bash
python3 scripts/build_companion.py --manifest <书目录>/manifest.json --out <书目录>/<slug>学习伴侣.html
python3 scripts/apply_visual_theme.py --file <书目录>/<slug>学习伴侣.html
```

**Phase 6 整合总入口**（多书时）：

```bash
python3 scripts/build_handbook.py --root <知枢目录>
python3 scripts/apply_visual_theme.py --root <知枢目录>
```

视觉注入放在构建之后、验证之前。`build_handbook.py` 重建会覆盖 `index.html`，先注入再打包等于白做。

**Phase 7 验证**：跑 `scripts/verify_handbook.py`，另查深度片段折叠、KaTeX 公式、诊断倒推链接。

**Phase 8 打包**：`scripts/package_delivery.py`，附交付说明。

## 关键能力

1. **出处脚注**：章节、概念、测验题都带 `source: {file, page}`，页面顶部显示出处。
2. **KaTeX 公式**：行内 `$...$`，块级 `$$...$$`，CDN 多源回退（jsDelivr / npmmirror / unpkg）。公式里的 `<` 写成 `&lt;`，否则被 HTML 解析器当标签吃掉。
3. **深度推导折叠**：高难概念的 `depthFragment` 放在概念页底部，用 `<details>` 折叠，默认收起，点"展开完整第一性原理推导"才显示。
4. **诊断模式**：侧边栏有诊断测试，随机抽 5 题。答错时沿 `prerequisites` 链倒推，列出可能的根因链接，点过去就跳到对应概念。
5. **前置知识条**：章节页和概念页顶部显示"前置知识：xxx → yyy"，链接可以直接跳。
6. **进度导出/导入**：单书伴侣和多书总入口都带导出/导入，格式是 JSON，含 `app/skillVersion/kind/prefix`。单书键前缀是 `<slug>:`，总入口是 `hb:`，两边互不覆盖。
7. **搜索分词与定位**：查询按标点切分，中文长词自动拆二元组（"为什么导数等于斜率"也能命中），命中词多的排前面。结果片段高亮命中词，点进去滚到首个命中处并闪一下。
8. **同义/近义召回**：`references/synonyms.json` 存 16 组近义词（定义/含义/释义、例题/算例/示例、导数/变化率/切线斜率等），组内两两互查。书目录下可以放同名文件追加专属术语。结果里标"同义命中"，说明这条是被哪个词召回的。
9. **搜索结果分组**：按章节聚合，组头显示命中数，标题用真实章节名而不是 id。术语表、速查表、模式库、抽认卡这类参考页权重降到 0.55，避免词频高的索引页压过正文。
10. **深色视觉层**：`assets/visual-theme.css` + `scripts/apply_visual_theme.py`，给已构建的页面注入深色 token、衬线标题、点阵底纹和界面 emoji 清理。只改样式，不改内容与路由；默认深色，浅色可切。
11. **可选课标图谱**：数学和理科材料可以接 cn-math-taxonomy，做法见 `references/taxonomy-integration.md`。
12. **句级出处**：manifest 里的 `claims[]`（`{id, page, quote, zh}`）给每句事实建账，正文写 `[[cl01]]`，构建后变成可点角标，点击弹出页码、原文原句和中文转述。总入口自动按书前缀化 id（`<书 key>:cl01`），跨书不撞号。写法与 9 类转述错误清单见 `references/pedagogy.md` §14。
13. **内容层审计**：`scripts/audit_content.py` 扫已构建的页面，报"带数字但没有出处"的句子、定义了却没被引用的 claim、引用了但没定义的 claim、外链数量。它和 `verify_handbook.py` 分工：后者验功能（能不能点、有没有报错），前者验内容对不对得起出处。

## 深度通道触发判据

一个概念满足三条以上才写 depthFragment：

- 从定义到结论需要多步代数推导。
- 零基础读者读完会问"为什么是这样"。
- 有设计动机可以讲，能用反例说明"为什么不那样设计"。
- 依赖链长，往前追两三层会退到读者还没学过的基础。

普通概念只写常规精讲。深度片段篇幅控制在概念正文的 2–3 倍。

## 差生通读清单

每个深度片段写完都要过一遍：

1. 这一步用到的概念前面出现过吗，解释过吗？
2. 这步代数读者能自己补出下一行吗？补不出就加中间步骤。
3. 符号第一次出现有没有白话说清？
4. 结论给了"为什么这样设计"吗，还是只给了"是什么"？

## 文件清单

```
zhishu/
├── SKILL.md                          # 本文件（frontmatter 带 version，改规则同步 CHANGELOG）
├── CHANGELOG.md                      # 版本与改动记录
├── README.md                         # 仓库说明与安装
├── assets/
│   └── visual-theme.css              # 深色视觉层（token/排版/组件/打印）
├── scripts/
│   ├── extract_text.py               # 多格式抽文本
│   ├── build_companion.py            # 单书 HTML 组装（含 KaTeX/诊断/深度片段）
│   ├── build_handbook.py             # 多书总入口
│   ├── apply_visual_theme.py         # 注入深色视觉层（可重复执行）
│   ├── verify_handbook.py            # 端到端验证（功能层）
│   ├── audit_content.py              # 内容层审计（数字无出处 / claim 覆盖）
│   └── package_delivery.py           # 打包
└── references/
    ├── workflow.md                   # 八阶段操作细节
    ├── templates.md                  # Markdown 模板 + manifest schema
    ├── pedagogy.md                   # 教学法（含深度通道判据、差生清单）
    ├── visual-theme.md                # 深色视觉口径、注入与验收
    ├── taxonomy-integration.md        # 外部课标图谱接入
    ├── github-pages.md               # Pages 部署
    └── open-source-patterns.md       # 参考过的开源项目
```

## 边界

- 外部知识图谱数据不内置。cn-math-taxonomy 是外部依赖，用到时下载到 `_work/`。
- 深度推导只对高难概念启用。每章都写会让产物变得读不动，工时也撑不住。
- 公式渲染依赖 CDN。完全离线时公式会显示成源码，文字和导航仍然可用。
- 教材例子可能有错。每个数值算例自己算一遍，算不通就换自拟题并在正文注明。

## 踩坑清单

下面每一条都是历史任务里真实发生过的静默失败：页面能打开，控制台干净，但内容是错的。生成后逐条过。

1. **单行 `$$...$$` 被吞**：Markdown 里写单行 `$$f'(x)=...$$` 时，渲染器要先判单行再处理多行。`build_companion.py` 已修，手写内容时注意不要把 `$$` 单独成行再结束。
2. **公式里 `<` 后跟字母被当标签**：`$m<n$` 会变成残留 `$m`，浏览器把 `<n` 当标签开头。`build_companion.py` 已自动把公式内 `<[a-zA-Z]` 转成 `&lt;`。手写 HTML 片段放进 Markdown 时要自己转义。
3. **多书合并时测验 id 重复**：每本书的测验 id 只写 `q01`，`build_handbook.py` 统一加书前缀。不要在单书 manifest 里自己加 `ch01-q01`，否则会变成 `book1-ch01-q01`，页面能作答但一致性检查报错。
4. **多章节固定 id 按钮失效**：交互按钮统一用 class + document 级事件委托，不用 `getElementById`。`build_companion.py` 已遵守。
5. **CDN 国内不可达**：Mermaid 的 npmmirror 路径（`mermaid/10/files/dist/mermaid.min.js`）实测连不通；pico.css 和 vis-network 的 npmmirror 路径都是 404，vis-network 的正确 JS 路径是 `dist/vis-network.min.js`（`dist/dist/` 是错的）。现在 Mermaid、KaTeX、pico、vis 统一 jsDelivr 优先、npmmirror 次之、unpkg 兜底，每个源带超时。只靠 `onerror` 会在不回调的源上永久卡住。验证时数 `.katex` 和 `.mermaid svg` 的数量，不要看截图 OCR，OCR 会把渲染好的公式读成源码样式。
6. **打包后必须解压到独立目录冒烟**：只测工作目录不算数。中文文件名、相对路径、`.nojekyll` 都可能在打包后出问题。
7. **`build_handbook.py` 早期版本不识别新字段**：深度片段、诊断页原先只在单书 companion 里有入口。现已补上 `__diagnosis__` 页面映射、侧边栏入口和诊断 JS。换环境复用时先点一遍 `#/book/<key>/diagnosis`，避免总入口显示"页面不存在"。深度片段在概念页内部，不需要总入口另加入口。
8. **OCR 乱码 PDF 不要硬抽文本**：数学或扫描版 PDF 抽出来是 `cid:` 或方框，弃用文本，改 Read 按页读图。用乱码硬撑会教错人。
9. **写作语气过 AI**：章节文案写完过一遍 `pedagogy.md` §12 的去 AI 味硬规则。
10. **容器类名与 CSS 不一致，内边距静默失效**：`build_handbook.py` 的架子曾写成 `<main>`，样式却挂在 `.main` 上，桌面 40px 与手机 16px 的内边距全部不生效，文字紧贴屏幕边缘。生成后在 390px 和 1440px 两个视口截图，量 `.main` 的左右边界；窄屏还要看表格是否横向溢出、长公式是否可滚动。
11. **移动端 Mermaid 卡在 loading**：jsDelivr 在国内可能一直不回调，`mermaidState` 停在 loading，后续页面也不再重试。加载顺序 npmmirror 优先，每个源加超时回退，不能只靠 `onerror`。
12. **表格里的公式被竖线切列**：Markdown 表格按裸 `|` 切分时，`$|z|$` 会被拆成三格，公式只剩残片。切分器要跳过 `$...$` 内的 `|` 和转义的 `\|`。`build_companion.py` 与 `build_handbook.py` 都要改，只改一个另一个仍会坏。
13. **手机端目录展开把正文推走**：12 章加 49 个概念展开后接近 2900px，正文要滚很久才出现。窄屏下给 `#nav` 加 `max-height:46vh` 和 `overflow-y:auto`，导航项与测验选项留 36–40px 触控高度，输入框字号 16px，避免 iOS 聚焦时自动放大页面。
14. **搜索索引漏掉内部页**：搜索曾对 `__` 前缀的页面 id 直接跳过，术语表、速查表、模式库、抽认卡、学习路径、测验页全部搜不到，症状是搜术语永远 0 条。单书走 `searchHref` / `searchLabel`，总入口走 `pdfToPage` 映射到真实路由。新增内部页时两处都要补，否则该页在搜索里不存在。
15. **搜索不做分词就搜不到整句**：英文按空格切，中文没有分隔符，`includes(整句)` 几乎必然 0 条。`tokenizeQuery` 先按标点切、中文长词拆二元组、过滤"的/是/什么/怎么"等停用词，再按命中词数排序；`hlSnippet` 出带 `<mark>` 的片段，`applyPendingHighlight` 在跳转后滚到首个命中。改搜索时这四段一起看，只改一处会得到"有结果但点进去没定位"的半成品。
16. **同义词表会带噪声，必须分层打分**：同义命中与精确命中混在一个总分里，一页"概念"堆出的同义分能压过真正写着该词的页。现在按精确 100 / 同义 30 / 二元组 1（上限 20）分层，精确永远在前。同义词组写成"定义/概念/含义/解释/说明"这种大杂烩，会把"解释一下"这类段落全召回，每组控制在 3–5 个真正等价的词。
17. **搜索结果组头的两个坑**：内部页的 `page` 是 `glossary` 这种单段字符串，`page.split('/')[1]` 得到 undefined，标题渲染成"undefined"，取值要先判断段数。术语表、速查表词频天然高，按最高分排组会把章节压到后面，参考类分组要单独降权（现在 ×0.55）。
18. **单书 Pages 目录做多书总入口时"未发现任何书"**：`build_handbook.py` 的 `discover` 原先把子目录里的 `index.html` 排除在伴侣候选之外，而 B 交付形态的书目录恰恰只有一个 `index.html`（根目录必须叫这个名字才能托管）。1.4.1 加了回退：目录内没有 `*学习伴侣.html` 时把 `index.html` 当伴侣，两种文件都在时仍优先命名明确的那个。
19. **一个未闭合的 `<h3>` 会让整章公式不渲染**：手写章节 HTML 时漏闭合一个标题、或多写一个 `</div>`，浏览器修 DOM 时把后面大半章吞进标题里。症状是这一章 `.katex` 数量远低于 `$` 配对数（实测一章应有 349 个，只渲染出 59 个），控制台没有任何报错。查法：`<div>` 与 `</div>`、`<h3>` 与 `</h3>`、`<p>` 与 `</p>` 逐个文件数配平，再和渲染后的 `.katex` 数对账。
20. **切旧章节时把上一章一起切掉**：用"切掉旧 summary 再追加新章节"的方式重组页面时，`core.rindex('<section', 0, idx)` 的 end 参数不吃 `idx` 本身，命中的是上一个 `<section`，于是前一章跟着被切走。症状是章节总数少一章，且少的正好是 summary 前面那章。改成 `core.rindex('</section>', 0, idx)`，从 summary 前一个闭合标签处切。
21. **分期写入的章节文件尾部会多一个 `"""`**：单次 Write 截断后内容不完整，追加时又补了一个三引号，文件末尾剩两个。症状是 `ast.parse` 报 `unterminated triple-quoted string literal`，构建脚本直接退出。每次追加完先跑一遍 `python3 -c "import ast;ast.parse(open(p).read())"` 再构建。
22. **重编号会打断正文引用**：把章节号从 12–18 改成 11–17 时，标题里的 `<span class="num">`、正文的"第 N 章"、小节号 `N.M`、公式号 `\tag{N.M}`、括注引用 `(N.M)` 都要一起改。用一次性映射函数替换，不要在循环里反复 replace，否则 12→11 之后又被 13→12 覆盖。改完抽查三处：标题编号连续、`第 N 章` 没有指回旧号、公式引用与实际 `\tag` 对齐。
23. **视觉层注入顺序错了会白做**：`build_handbook.py` 重建会覆盖 `index.html`，`apply_visual_theme.py` 必须在构建之后、验证和打包之前跑。先打包再注入，zip 里仍是旧皮肤。旧页面用 JS 设置 `#progress-bar > div` 的 `width`，主题只改背景色，不要改成 `transform`，否则进度条一直满格。
24. **`[[cl01]]` 只在正文替换，代码块里不换**：`_apply_claims` 按 `<pre>...</pre>` 切段后逐段替换，避免把示例代码里的 `[[...]]` 也变成角标。改这个正则时注意 `[\s\S]` 不要多转义一层写成 `[\\s\\S]`，否则匹配不到任何 `<pre>`，整页都被替换。
25. **多书总入口的 claim id 必须前缀化**：`build_handbook.py` 从各书伴侣 HTML 里抽 `rendered`，里面的 `data-cite="cl01"` 是单书局部 id，不前缀化就会两本书的 `cl01` 撞在一起，点 B 书的角标弹出 A 书的原句。`normalize_book` 里 href 前缀化之后紧跟着就是 data-cite 前缀化，`SOURCES` 键同格式。
