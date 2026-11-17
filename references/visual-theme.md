# 深色视觉层

给知枢产物套一层统一的深色视觉。它只改样式，不改 DOM、路由、数据结构，适合已经构建好的页面做视觉同步，也适合新页面在 `build_companion.py` / `build_handbook.py` 之后补一层。

## 视觉口径

| 项 | 值 |
|---|---|
| 默认主题 | 深色，浅色可切 |
| 底色 | `#080d1a` |
| 面板 | `#101a2f` / `#16213b` |
| 主色 | 钴蓝 `#5c7cff` |
| 辅色 | 鲸青 `#16c7d9` |
| 成功/激活 | `#2bd9a5` |
| 浅色底 | 暖灰纸感 `#edf1f8`，不是纯白 |
| 标题 | Noto Serif CJK / Songti 衬线 |
| 正文 | Noto Sans CJK / PingFang |
| 数字 | JetBrains Mono / 系统等宽，`tnum` |
| 底纹 | 26px 点阵，透明度 0.12，不用玻璃拟态 |

原则是"技术编辑感 + 仪表盘"：深色底、低饱和面板、一个钴蓝主色、一个鲸青辅色、衬线标题、点阵背景。不要紫蓝渐变、发光边框、毛玻璃、emoji 图标。

## 用法

在 skill 根目录执行：

```bash
# 单页
python3 scripts/apply_visual_theme.py --file <page.html>

# 目录：默认处理 index.html 和 *学习伴侣.html
python3 scripts/apply_visual_theme.py --root <知枢目录>

# 目录：处理全部 HTML（含章节页、实验页）
python3 scripts/apply_visual_theme.py --root <知枢目录> --all-html
```

脚本做三件事：

1. 在 `</head>` 前插入 `<style id="zs-visual-theme">`，内容是 `assets/visual-theme.css`。
2. 在 `</body>` 前插入 `<script id="zs-visual-init">`，设置默认深色、清理界面 emoji、同步主题按钮文案。
3. 重复执行时替换而不是追加，页面里只会有一份。

建议顺序：`build_companion.py` / `build_handbook.py` → `apply_visual_theme.py` → `verify_handbook.py` → `package_delivery.py`。如果先打包再注入，zip 里会是旧皮肤。

## 兼容范围

已实测：

- 旧版多书总入口：`header` + `.tabs` + `.sidebar` + `.main`，使用 `--bg` / `--panel` / `--text` 变量；
- 单书伴侣：`.layout` + `.sidebar` + `.main`，带 `#progress-bar`、`#q`、`.quiz-item`、`.fc-front`；
- 旧版从零推导页：使用 `--bg2` / `--card` / `--accent` 的深色页面；
- 新版总入口：如果页面已有 `visual-skin` 或 `#zs-visual-theme`，脚本会替换主题样式，不会重复插入。已经有完整自定义壳的页面不建议再套。

不适合：

- 带 Canvas / WebGL 主视觉且颜色写死在 JS 里的页面；
- 依赖纯白背景做图像混合的页面；
- 已经有一套完整品牌视觉的页面。强套会二次覆盖，先备份再试。

## 主题切换

- 默认 `:root` 是深色。
- 旧多书总入口的按钮把 `body.dataset.theme` 设成 `dark` 或空字符串；空字符串对应浅色。脚本会把按钮文案同步成"浅色 / 深色"。
- 旧 SVM 一类页面把 `data-theme="light"` 放在 `<html>` 上；样式表同时支持 `html[data-theme="light"]` 和 `body[data-theme="light"]`。
- 初始脚本只在 `body` 和 `html` 都没有主题属性时补 `dark`，不覆盖用户已选。

## 验收

至少检查四个视口/状态：

1. 1440px 桌面：底色是 `#080d1a`，标题是衬线，侧栏和正文不粘连。
2. 390px 手机：`scrollWidth === innerWidth`，表格能横向滚动，抽屉/目录可开合。
3. 浅色切换：背景变 `#edf1f8`，正文是深色，不出现白底白字。
4. 控制台：没有 CSS 语法错误、没有新增加的 404。

命令：

```bash
python3 - <<'PY'
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b=p.chromium.launch(executable_path="/usr/local/bin/chromium",args=["--no-sandbox"])
    for w,h in ((1440,1000),(390,844)):
        pg=b.new_page(viewport={"width":w,"height":h})
        pg.goto("file:///绝对路径/index.html"); pg.wait_for_timeout(800)
        print(w, pg.evaluate("document.documentElement.scrollWidth"), pg.evaluate("innerWidth"))
        pg.screenshot(path=f"/tmp/theme-{w}.png")
    b.close()
PY
```

## 踩坑

1. **别在 `build_handbook.py` 重建后忘记重跑**：重建会覆盖 `index.html`，视觉层要最后注入。
2. **不要给 `#progress-bar > div` 改宽度逻辑**：旧页面用 JS 设置 `width`，主题只改背景色；改成 `transform: scaleX()` 会让进度条一直满格。
3. **主题按钮文案不要硬编码在 HTML 里**：旧页面点击后会自己改文案，脚本用 MutationObserver 和点击后置同步，避免出现"深色"按钮实际在浅色态。
4. **emoji 只在界面 chrome 清理**：范围限定 `header / .sidebar / .topbar / .tabs / .card-actions`，不要遍历正文，正文里的数学符号和箭头不能动。
5. **打印样式单独处理**：打印时强制白底黑字，否则整页黑底会浪费墨。
6. **CDN 不参与**：这套主题不加载外部字体或图标，断网也能看；字体回退到系统衬线/黑体。
