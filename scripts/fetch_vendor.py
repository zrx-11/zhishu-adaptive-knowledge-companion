#!/usr/bin/env python3
"""下载离线内联所需的第三方库到 assets/vendor/。

用法：
    python3 scripts/fetch_vendor.py            # 只取 KaTeX + Pico + vis-network（约 1.4MB）
    python3 scripts/fetch_vendor.py --mermaid  # 追加 Mermaid（+3.3MB）

构建时加 `--offline katex`（KaTeX+Pico）或 `--offline all`（再加 vis-network），
这两个库就会内联进 HTML，断网也能渲染公式与图谱。
Mermaid 体积太大，默认仍走 CDN；需要纯粹离线时加 `--offline-mermaid` 并在本脚本带 `--mermaid` 取下来。
"""
import argparse
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VENDOR = os.path.join(HERE, "assets", "vendor")

KATEX_VER = "0.16.11"
PICO_VER = "2.0.6"
VIS_VER = "9.1.9"
MERMAID_VER = "10.9.1"

FILES = {
    "katex.min.js": f"https://cdn.jsdelivr.net/npm/katex@{KATEX_VER}/dist/katex.min.js",
    "katex.min.css": f"https://cdn.jsdelivr.net/npm/katex@{KATEX_VER}/dist/katex.min.css",
    "pico.min.css": f"https://cdn.jsdelivr.net/npm/@picocss/pico@{PICO_VER}/css/pico.min.css",
    "vis-network.min.js": f"https://cdn.jsdelivr.net/npm/vis-network@{VIS_VER}/standalone/umd/vis-network.min.js",
}
EXTRA = {"mermaid.min.js": f"https://cdn.jsdelivr.net/npm/mermaid@{MERMAID_VER}/dist/mermaid.min.js"}


def fetch(url, dest, force=False):
    if os.path.exists(dest) and not force and os.path.getsize(dest) > 1024:
        return os.path.getsize(dest), False
    req = urllib.request.Request(url, headers={"User-Agent": "zhishu-fetch/1.7"})
    data = urllib.request.urlopen(req, timeout=60).read()
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "wb") as f:
        f.write(data)
    return len(data), True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mermaid", action="store_true")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()

    os.makedirs(VENDOR, exist_ok=True)
    total = 0
    for name, url in FILES.items():
        size, fresh = fetch(url, os.path.join(VENDOR, name), a.force)
        total += size
        print(("下载 " if fresh else "已存在 ") + f"{name} {size / 1024:.0f}KB")

    # KaTeX 字体：只取 CSS 引用到的 woff2（woff/ttf 在内联时会被丢掉）
    css_path = os.path.join(VENDOR, "katex.min.css")
    css = open(css_path, encoding="utf-8").read()
    import re
    fonts = sorted(set(re.findall(r"fonts/([A-Za-z0-9_\-]+\.woff2)", css)))
    fdir = os.path.join(VENDOR, "fonts")
    os.makedirs(fdir, exist_ok=True)
    fname_total = 0
    for fn in fonts:
        size, _ = fetch(f"https://cdn.jsdelivr.net/npm/katex@{KATEX_VER}/dist/fonts/{fn}", os.path.join(fdir, fn), a.force)
        fname_total += size
    print(f"KaTeX 字体 {len(fonts)} 个 {fname_total / 1024:.0f}KB")

    if a.mermaid:
        for name, url in EXTRA.items():
            size, fresh = fetch(url, os.path.join(VENDOR, name), a.force)
            print(("下载 " if fresh else "已存在 ") + f"{name} {size / 1024:.0f}KB")

    print(f"\n内联预估：KaTeX+Pico+vis ≈ {(total + fname_total * 1.37) / 1024 / 1024:.1f}MB（字体按 base64 膨胀 37% 计）")
    print(f"目录：{VENDOR}")


if __name__ == "__main__":
    sys.exit(main())
