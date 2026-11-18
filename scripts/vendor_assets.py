#!/usr/bin/env python3
"""构建期的离线内联助手：把 assets/vendor 里的库读成可直接塞进 HTML 的片段。

被 build_companion.py / build_handbook.py 引入，不单独运行。
没有 assets/vendor 时所有函数返回空串，构建照旧走 CDN。
"""
import base64
import os
import re

VENDOR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "vendor")


def path(name):
    return os.path.join(VENDOR, name)


def has(name):
    p = path(name)
    return os.path.exists(p) and os.path.getsize(p) > 1024


def read(name):
    return open(path(name), encoding="utf-8").read()


def _inline_fonts(css):
    """KaTeX CSS 只留 woff2，并换成 data URI；woff/ttf 分支删掉，免得内联后引用不存在的文件。"""
    css = re.sub(r',\s*url\(fonts/[^)]*\.(?:woff|ttf)\)(?:\s*format\("[^"]+"\))?', "", css)

    def repl(m):
        fn = m.group(1)
        fp = os.path.join(VENDOR, "fonts", fn)
        if not os.path.exists(fp):
            return m.group(0)
        raw = base64.b64encode(open(fp, "rb").read()).decode("ascii")
        return f'url(data:font/woff2;base64,{raw})'

    return re.sub(r"url\(fonts/([A-Za-z0-9_\-]+\.woff2)\)", repl, css)


def katex_css():
    if not has("katex.min.css"):
        return ""
    return "<style id=\"katex-offline\">\n" + _inline_fonts(read("katex.min.css")) + "\n</style>"


def pico_css():
    if not has("pico.min.css"):
        return ""
    return "<style id=\"pico-offline\">\n" + read("pico.min.css") + "\n</style>"


def katex_js():
    if not has("katex.min.js"):
        return ""
    return "<script id=\"katex-offline-js\">" + read("katex.min.js") + "</script>"


def vis_js():
    if not has("vis-network.min.js"):
        return ""
    return "<script id=\"vis-offline-js\">" + read("vis-network.min.js") + "</script>"


def mermaid_js():
    if not has("mermaid.min.js"):
        return ""
    return "<script id=\"mermaid-offline-js\">" + read("mermaid.min.js") + "</script>"


CDN_LINK_RE = re.compile(
    r'<link[^>]+href="https://(?:cdn\.jsdelivr\.net/npm/(?:katex|@picocss/pico|vis-network)[^"]*|'
    r'registry\.npmmirror\.com/(?:katex|@picocss/pico|vis-network)[^"]*|unpkg\.com/(?:katex|@picocss/pico|vis-network)[^"]*)"[^>]*>\s*'
)


def strip_cdn_links(html):
    """离线构建时把 CDN 的 katex/pico/vis 样式表链接删掉（内容已内联）。"""
    return CDN_LINK_RE.sub("", html)
