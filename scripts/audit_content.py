#!/usr/bin/env python3
"""内容层审计：扫已构建的知枢页面，报"带数字但没有出处"的句子、claim 覆盖缺口、外链依赖。

用法：
    python3 audit_content.py 测试书学习伴侣.html [--strict]

与 verify_handbook.py 的分工：
- verify_handbook.py 是浏览器功能回归（能不能点、能不能跳、有没有报错）；
- 本脚本是静态内容审计（说的对不对得起出处），不启浏览器。

只依赖标准库。"数字无出处"的检测思路与 `数字+单位` 正则参考了
ai-azhou/pdf-to-interactive-web（MIT）的 scripts/audit_html.py，按其 page-contract 改写为
知枢的 DATA 结构；其余为知枢自有逻辑。
"""
import argparse
import json
import re
import sys

CITE = re.compile(r'<sup class="cite"[^>]*data-cite="([^"]+)"')
NUM = re.compile(
    r"(?<!第)(\d+(?:\.\d+)?\s*(?:%|％|倍|成|亿|万|元|人|次|年|月|日|页|条|个|岁|字|克|米|秒|分钟|小时|°|℃))"
    r"|(\d+\.\d+)")
TAG = re.compile(r"<[^>]+>")
BLOCK_SPLIT = re.compile(r"</p>|</li>|</h1>|</h2>|</h3>|</dd>|</blockquote>")


def load_pages(path):
    html = open(path, encoding="utf-8").read()
    m = re.search(r"const DATA = (\{.*?\});\n", html, re.S)
    if not m:
        return None
    raw = m.group(1).replace("<\\/", "</")
    try:
        d = json.loads(raw)
    except Exception:
        return None
    rendered = d.get("rendered") or d.get("pages") or {}
    return d.get("manifest") or {}, rendered


def text_of(block):
    return TAG.sub("", block).replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&").strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("html")
    ap.add_argument("--strict", action="store_true", help="有问题时返回非零退出码")
    ap.add_argument("--limit", type=int, default=25, help="每类最多列多少条")
    a = ap.parse_args()

    loaded = load_pages(a.html)
    if not loaded:
        print("读取失败：没找到 DATA 结构，可能不是 build_companion.py 的产物")
        return 2
    manifest, rendered = loaded

    pages = {}
    for pid, v in rendered.items():
        pages[pid] = v.get("html", "") if isinstance(v, dict) else str(v)

    uncited, cited_ids, per_page = [], [], {}
    for pid, html in pages.items():
        used = CITE.findall(html)
        cited_ids.extend(used)
        cjk = len(re.findall(r"[\u3400-\u9fff]", TAG.sub("", html)))
        per_page[pid] = cjk
        for block in BLOCK_SPLIT.split(html):
            blk = block.strip()
            if not blk or "<sup class=\"cite\"" in blk:
                continue
            lead = re.match(r"<\s*([a-zA-Z0-9]+)", blk)
            tag = (lead.group(1).lower() if lead else "")
            if tag in ("h1", "h2", "h3", "h4"):
                continue
            if "source-badge" in blk or "prereq" in blk:
                continue
            t = text_of(block)
            if len(t) < 4 or not NUM.search(t):
                continue
            uncited.append((pid, t[:90]))

    claims = {str(c.get("id")) for c in (manifest.get("claims") or []) if isinstance(c, dict) and c.get("id")}
    used_set = set(cited_ids)
    unused = sorted(claims - used_set)
    dangling = sorted({i for i in used_set if claims and i not in claims})

    ext = len(re.findall(r'https?://[^\s"\'<>]+', open(a.html, encoding="utf-8").read()))

    print(f"== 内容审计 {a.html}")
    print(f"页面 {len(pages)} 个 · 正文汉字 {sum(per_page.values())} · 外链 {ext} 处")

    print(f"\n== 数字/数量句无出处：{len(uncited)} 处")
    for pid, t in uncited[: a.limit]:
        print(f"  [{pid}] {t}")

    if claims:
        print(f"\n== claim 覆盖：定义 {len(claims)} · 页面引用 {len(used_set)}")
        if unused:
            print(f"  未被引用的 claim（{len(unused)}）：{', '.join(unused[: a.limit])}")
        if dangling:
            print(f"  引用了但没有定义的 claim（{len(dangling)}）：{', '.join(dangling[: a.limit])}")
    else:
        print("\n== 未定义 claims[]：整本没有句级出处，只有页级 source")

    bad = bool(uncited) or bool(dangling) or bool(unused)
    print("\n结论：" + ("有问题，见上" if bad else "通过"))
    return 1 if (bad and a.strict) else 0


if __name__ == "__main__":
    sys.exit(main())
