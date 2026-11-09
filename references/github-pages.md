# 部署到 GitHub Pages

点化产物是纯静态站点，只需把文件推到仓库根目录并开启 Pages。

## 前置

- 站点根目录必须有 `index.html`（`build_handbook.py` 产物）。
- 必须有空的 `.nojekyll`（`package_delivery.py` 会自动创建）——否则 Jekyll 会忽略 `_build/`、`_work/` 等以下划线开头的目录，中文文件名也可能出问题。

## 为什么这套产物能直接放上去

整个站点只有一个 `index.html` 加若干 Markdown 和单书伴侣 HTML，没有构建步骤，也没有后端。Pages 的"Deploy from a branch"就是原样托管，推上去即可访问。

Mermaid 走 CDN，联网正常时就渲染；离线时降级成源码并给出提示，不会白屏。这是有意的取舍：把 1.5 MB 的 mermaid 内联进去，页面首次打开会明显变慢。

体积上，四本书 `final` 包 1.1 MB，`full` 包 12.7 MB，离 Pages 的 1 GB 上限很远。真到十几本大部头，先删 `_work/` 里的扫描页截图。

## 三步部署

```bash
# 1. 解压交付包，把「包内全部文件/目录」放到仓库根目录（不是子目录）
cd <仓库目录>
git add -A
git commit -m "点化学习系统：总学习手册 + 各书学习伴侣"
git push origin main

# 2. 仓库 Settings → Pages → Source: Deploy from a branch
#    Branch: main ；目录: / (root) → Save
# 3. 约 1~2 分钟后访问
#    https://<用户名>.github.io/<仓库名>/
```

新仓库首次推送：

```bash
git init
git add -A
git commit -m "点化学习系统"
git branch -M main
git remote add origin https://github.com/<用户名>/<仓库名>.git
git push -u origin main
```

## 常见问题

1. **打开是 404**：确认 `index.html` 在仓库根目录；Pages 设置选的是 `main` + `/ (root)`；刚开启需等 1~2 分钟。
2. **中文文件名 404**：链接要用 URL 编码（浏览器点击会自动编码）；本 skill 的 `index.html` 内部全部用 hash 路由，不受影响；单书伴侣链接已用 `encodeURI` 处理。
3. **Mermaid 不显示**：图走 CDN 懒加载，离线时降级显示源码，属预期；要完全离线性需把 mermaid.min.js 内联。
4. **仓库太大**：`_work/`（扫描页截图）与 `_build/` 可删——`rm -rf 0*/_work _build`，不影响站点功能；Pages 上限 1 GB、单文件 100 MB。
5. **改内容后不更新**：Pages 有 CDN 缓存，等 1~2 分钟或换无痕窗口验证。
6. **私有仓库开 Pages**：公开 Pages 需仓库公开或使用付费计划；私有仓库的 Pages 仅对有权访问者可见。

## 可选：GitHub Actions 自动部署

纯静态站点不需要 Actions；若想每次 push 自动发布，可用官方 Pages 工作流。默认推荐「Deploy from a branch」，最省事。
