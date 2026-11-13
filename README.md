# 知枢 · zhishu-adaptive-knowledge-companion

把任何学习材料——一个知识点、一组题、一份课件、一本书、多本书——变成"按依赖带你走、答错倒推根因、难点从零推透"的单文件交互学习网页。

**当前版本 v1.4.0**（更新记录见 [CHANGELOG.md](CHANGELOG.md)）

## 特性

**学习机制**

- 自动识别输入形态（知识点/题目/课件/书/多书），走最轻流水线
- 概念依赖力导向图（vis-network），点击跳转
- 答错沿前置链倒推根因 + 误解卡片纠偏
- FSRS 间隔重复抽认卡
- 掌握度概率估计（简化 BKT）
- 学习热力图 + 连续 streak
- 错题本自动收集

**搜索（v1.2–v1.4）**

- 分词：按标点切分，中文长词拆二元组，过滤 36 个停用词——"为什么导数是切线斜率"也能命中
- 同义召回：`references/synonyms.json` 内置 16 组近义词（定义/含义/释义、导数/变化率/切线斜率…），书目录下可放同名文件追加专属术语
- 分层打分：精确词 100 / 同义 30 / 二元组 1，精确命中永远优先
- 结果按章节分组，标题显示真实章节名与概念名，参考类页面降权
- 点击结果滚到首个命中处并高亮，片段最多标 6 处

**工程**

- 版本号写入页面（`ZS_VERSION`），误解卡在单书与总入口都可用
- 进度导出/导入（JSON），单书与多书总入口前缀隔离，换设备可搬
- `verify_handbook.py` 32 项浏览器回归（真实 chromium 跑，不是静态检查）

**呈现**

- KaTeX 公式、滚动淡入、字号调节、阅读进度条、打印/PDF 导出
- Pico CSS 美化，深色模式

## 使用

这是一个 Doubao 工作模式 skill，不是独立 Web 应用。把整个目录放进 `~/.doubao/agent_mode/workspace/.user_skills/` 即可在对话中调用。

单独构建与验证：

```bash
# 单书（book 目录内需有 manifest.json）
python3 scripts/build_companion.py --manifest <book>/manifest.json --out <book>/学习伴侣.html

# 多书总入口（扫描 root 下所有含 manifest.json 的书目录）
python3 scripts/build_handbook.py --root <root>

# 回归验证
python3 scripts/verify_handbook.py --index <root>/index.html \
  --chromium /usr/local/bin/chromium --report <root>/verify.json
```

## 目录结构

```
├── SKILL.md                 # 技能主文档：六层架构、五种输入形态、八阶段流程、17 条踩坑
├── CHANGELOG.md             # 1.4.0 / 1.3.0 / 1.2.0 / 1.1.0 / 1.0.0
├── agents/doubao.yaml
├── references/
│   ├── workflow.md          # 八阶段流程细则
│   ├── pedagogy.md          # 教学法与去 AI 味硬规则
│   ├── templates.md         # manifest schema、误解卡、依赖分级
│   ├── synonyms.json        # 搜索同义词表
│   └── taxonomy-integration.md / github-pages.md / open-source-patterns.md
└── scripts/
    ├── build_companion.py   # 单书构建
    ├── build_handbook.py    # 多书总入口构建
    ├── verify_handbook.py   # 32 项浏览器回归
    ├── extract_text.py      # PDF/文本抽取
    └── package_delivery.py  # 交付打包
```

## 已知限制

1. 搜索词表靠人工维护，冷门术语与缩写需自行写入 `synonyms.json`。
2. 分组只到章节级，不按概念聚合。
3. 误解卡仅对单选题生效。
4. 全量重建：已有 HTML 不会自动获得新能力，需重新 build。
5. 依赖 KaTeX CDN，离线打开公式不渲染。
