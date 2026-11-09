#!/usr/bin/env python3
"""打包点化交付物（zip），支持 final / full 两种模式，并确保 Pages 所需文件就位。

用法：
  python3 scripts/package_delivery.py --root <点化学习系统目录> --out <包.zip> --mode final
  python3 scripts/package_delivery.py --root <目录> --out <包.zip> --mode full   # 含中间产物

final：知识库 + 学习伴侣 + index.html/index.md/README.md/.nojekyll + 00-跨书总览；排除 _work/、_build/。
full ：额外包含 _work/（抽取原文、页面截图、验证脚本与截图）与 _build/（整合脚本、抽取数据、验证报告）。
两种模式都会补齐 .nojekyll 与 交付说明.md（已存在则保留）。
"""
import argparse
import json
import os
import re
import zipfile

EXCLUDE_ALWAYS = {".git", "__pycache__", ".DS_Store", ".ipynb_checkpoints"}


def ensure_nojekyll(root):
    p = os.path.join(root, ".nojekyll")
    if not os.path.exists(p):
        open(p, "w").close()
        print("已创建 .nojekyll")


def collect(root, mode):
    files = []
    excluded = 0
    for dirpath, dirnames, filenames in os.walk(root):
        rel_dir = os.path.relpath(dirpath, root)
        parts = [] if rel_dir == "." else rel_dir.split(os.sep)
        # 目录级排除
        drop = [d for d in parts if d in EXCLUDE_ALWAYS]
        if drop:
            dirnames[:] = []
            continue
        if mode == "final":
            if any(p in ("_work", "_build") for p in parts):
                excluded += sum(len(fs) for _, _, fs in os.walk(dirpath))
                dirnames[:] = []
                continue
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_ALWAYS]
        for fn in filenames:
            if fn in EXCLUDE_ALWAYS or fn.endswith((".pyc", ".zip")):
                continue
            files.append(os.path.normpath(os.path.join(dirpath, fn)))
    return files, excluded


def read_manifests(root):
    out = []
    for name in sorted(os.listdir(root)):
        p = os.path.join(root, name)
        if not os.path.isdir(p) or name.startswith((".", "_")):
            continue
        mf = os.path.join(p, "manifest.json")
        if not os.path.exists(mf):
            continue
        try:
            m = json.load(open(mf, encoding="utf-8"))
        except Exception:
            continue
        out.append({
            "dir": name,
            "title": m.get("title", name),
            "chapters": len(m.get("chapters", [])),
            "concepts": len(m.get("concepts", [])),
            "quizzes": len(m.get("quizzes", [])),
            "cards": len(m.get("flashcards", [])),
            "glossary": len(m.get("glossary", [])),
        })
    return out


def write_note(root, mode, books):
    p = os.path.join(root, "交付说明.md")
    if os.path.exists(p):
        print("交付说明.md 已存在，保留原文件")
        return
    lines = ["# 点化学习系统 · 交付说明", "",
             "本包是一套可直接学习的系统化知识库手册：统一入口 `index.html`，每本书另有独立学习伴侣。", "",
             f"**交付模式**：`{mode}`" + ("（仅最终产物）" if mode == "final" else "（最终产物 + 中间产物）"), "",
             "## 一、书目", "", "| 目录 | 书 | 章节 | 概念 | 测验 | 抽认卡 | 术语 |", "|---|---|---|---|---|---|---|"]
    for b in books:
        lines.append(f"| {b['dir']} | {b['title']} | {b['chapters']} | {b['concepts']} | "
                     f"{b['quizzes']} | {b['cards']} | {b['glossary']} |")
    lines += ["", "## 二、目录说明", "",
              "| 路径 | 说明 |", "|---|---|",
              "| `index.html` | 总学习手册：单文件统一入口，可离线打开 |",
              "| `index.md` | Markdown 导航页 |",
              "| `README.md` | 使用与部署说明 |",
              "| `.nojekyll` | GitHub Pages 关闭 Jekyll，原样托管静态文件 |",
              "| `00-跨书总览/` | 推荐学习顺序 / 跨书概念映射 / 综合检验建议 |",
              "| `NN-书名/` | 该书 SKILL.md、chapters/、concepts/、配套 md、manifest.json、学习伴侣.html |",
              "| `_build/`（仅 full） | 整合脚本、抽取数据、验证脚本与报告 |",
              "| 各书 `_work/`（仅 full） | 抽取原文、扫描页截图、构建与验证脚本、验证截图 |", "",
              "## 三、使用方法", "",
              "1. 双击 `index.html`：顶部切换书籍与总览，左侧按学习路径/章节/概念/测验/抽认卡/术语/模式/速查浏览。",
              "2. 学习进度、测验记录、卡片复习状态保存在浏览器本地（localStorage）。",
              "3. 单书伴侣：各书目录下的 `*学习伴侣.html` 可单独打开。", "",
              "## 四、部署 GitHub Pages", "",
              "```bash",
              "# 把包内全部文件放到仓库根目录后",
              "git add -A && git commit -m \"点化学习系统\" && git push origin main",
              "# Settings → Pages → Deploy from a branch → main → / (root) → Save",
              "```", "",
              "访问 `https://<用户名>.github.io/<仓库名>/` 即进入总学习手册。", "",
              "## 五、验证", "",
              "- 总入口 `index.html` 已通过生成阶段的 `scripts/verify_handbook.py` 端到端验证"
              "（首页/总览页/各书首末章/测验作答/抽认卡/术语/搜索/进度持久/深色/控制台）。",
              "- 各书伴侣：逐章导航、搜索、测验反馈、抽认卡、进度持久、深色模式。", "",
              "## 六、取舍", "",
              "- `_work/`、`_build/` 不影响站点运行；如需更轻的公开仓库，可删除后再推送。",
              "- 扫描页截图与抽取原文仅作过程留档，公开前请确认版权边界。", ""]
    open(p, "w", encoding="utf-8").write("\n".join(lines))
    print("已生成 交付说明.md")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--mode", choices=["final", "full"], default="full")
    args = ap.parse_args()

    root = os.path.abspath(args.root)
    if not os.path.exists(os.path.join(root, "index.html")):
        raise SystemExit("缺少 index.html：请先运行 build_handbook.py")
    ensure_nojekyll(root)
    books = read_manifests(root)
    write_note(root, args.mode, books)

    files, excluded = collect(root, args.mode)
    out = os.path.abspath(args.out)
    if out.startswith(root + os.sep):
        files = [f for f in files if os.path.abspath(f) != out]
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for f in files:
            z.write(f, os.path.relpath(f, root))
    size = os.path.getsize(out)
    with zipfile.ZipFile(out) as z:
        bad = z.testzip()
    print(f"打包完成：{out}")
    print(f"  模式：{args.mode} | 文件：{len(files)} | 大小：{size/1024/1024:.1f} MB | 排除：约 {excluded} 个中间文件")
    print("  完整性：OK" if not bad else f"  完整性异常：{bad}")
    if args.mode == "final":
        print("  提示：final 模式不含 _work/ 与 _build/；如需中间产物请用 --mode full 重新打包。")


if __name__ == "__main__":
    main()
