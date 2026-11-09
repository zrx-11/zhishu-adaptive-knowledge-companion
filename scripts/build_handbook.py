#!/usr/bin/env python3
"""把点化学习系统（单书或多书）整合成统一总入口 index.html + index.md。

用法：
  python3 scripts/build_handbook.py --root <点化学习系统目录>
  python3 scripts/build_handbook.py --root <目录> --out <index.html> --order "01,02"
  python3 scripts/build_handbook.py --root <目录> --cross-dir 00-跨书总览

自动发现规则：
  - 根目录下每个含 manifest.json 且有 *.html 的子目录 = 一本书；
  - 书名/标签取 manifest.title（去掉"点化学习系统/伴侣"等后缀），路由 key 取 manifest.slug（ASCII 化，回退 b01）；
  - 跨书总览目录默认 00-* 或以"总览"命名的目录，内含 *.md（README / 跨书概念映射表 / 综合检验建议 等任意篇数）。
"""
import argparse
import json
import os
import re
import sys
import html as html_mod

ALLOWED_RAW_TAGS = {
    "div", "span", "svg", "path", "rect", "circle", "line", "polyline",
    "polygon", "g", "text", "tspan", "defs", "lineargradient", "stop",
    "ellipse", "marker", "use", "a", "img", "details", "summary",
    "b", "i", "u", "br", "hr", "strong", "em", "code", "pre",
    "sub", "sup", "table", "thead", "tbody", "tr", "td", "th",
    "ul", "ol", "li", "p", "h1", "h2", "h3", "h4", "h5", "h6",
    "blockquote", "figure", "figcaption", "center",
}


def esc(t):
    return html_mod.escape(t, quote=True)


def san_url(u):
    return esc(u) if re.match(r"^(https?://|mailto:|#|/|\.\.?/)", u, re.I) else "#"


def inline(t):
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    t = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)",
               lambda m: f'<a href="{san_url(m.group(2))}" target="_blank" rel="noopener">{m.group(1)}</a>', t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", t)
    return t


def is_raw(l):
    m = re.match(r"^\s*</?([a-zA-Z0-9]+)", l)
    return m and m.group(1).lower() in ALLOWED_RAW_TAGS


def md2html(md):
    """最小 Markdown 渲染器（与 build_companion.py 同源）。"""
    lines = md.replace("\r\n", "\n").split("\n")
    out, para, i, n = [], [], 0, len(lines)
    in_code, code_buf, code_lang = False, [], ""
    lists = []

    def flush_para():
        nonlocal para
        if para:
            t = inline(esc(" ".join(para).strip()))
            if t:
                out.append(f"<p>{t}</p>")
            para = []

    def close_lists(mini=0):
        while lists and lists[-1][1] >= mini:
            typ, _ = lists.pop()
            out.append("</ol>" if typ == "ol" else "</ul>")

    while i < n:
        line = lines[i]
        if line.lstrip().startswith("```"):
            if in_code:
                lang = code_lang or ""
                if lang.lower() == "mermaid":
                    out.append(f'<div class="mermaid" data-src="1">{esc(chr(10).join(code_buf))}</div>'
                               f'<p class="mermaid-hint">↑ Mermaid 图示：联网时自动渲染；离线则阅读源码与正文。</p>')
                else:
                    cls = f' class="lang-{lang}"' if lang else ""
                    out.append(f"<pre{cls}><code>{esc(chr(10).join(code_buf))}</code></pre>")
                in_code = False
                code_buf = []
            else:
                flush_para()
                close_lists()
                in_code = True
                code_lang = line.lstrip()[3:].strip()
                code_buf = []
            i += 1
            continue
        if in_code:
            code_buf.append(line)
            i += 1
            continue
        if is_raw(line):
            flush_para()
            close_lists()
            buf = [line]
            j = i + 1
            while j < n and is_raw(lines[j]):
                buf.append(lines[j])
                j += 1
            out.append("\n".join(buf))
            i = j
            continue
        s = line.strip()
        if not s:
            flush_para()
            close_lists()
            i += 1
            continue
        m = re.match(r"^(#{1,6})\s+(.*)$", s)
        if m:
            flush_para()
            close_lists()
            out.append(f"<h{len(m.group(1))}>{inline(esc(m.group(2)))}</h{len(m.group(1))}>")
            i += 1
            continue
        if re.match(r"^(-{3,}|\*{3,}|_{3,})$", s):
            flush_para()
            close_lists()
            out.append("<hr>")
            i += 1
            continue
        if s.startswith(">"):
            flush_para()
            out.append(f"<blockquote>{inline(esc(re.sub(r'^>\\s?', '', s)))}</blockquote>")
            i += 1
            continue
        if s.startswith("|") and i + 1 < n and re.match(r"^\s*\|?[\s:\-|]+\|?\s*$", lines[i + 1]):
            flush_para()
            close_lists()
            head = [c.strip() for c in s.strip("|").split("|")]
            rows, j = [], i + 2
            while j < n and lines[j].strip().startswith("|"):
                rows.append([c.strip() for c in lines[j].strip().strip("|").split("|")])
                j += 1
            t = ["<table><thead><tr>"] + [f"<th>{inline(esc(c))}</th>" for c in head] + ["</tr></thead><tbody>"]
            for r in rows:
                t.append("<tr>" + "".join(f"<td>{inline(esc(c))}</td>" for c in r) + "</tr>")
            t.append("</tbody></table>")
            out.append("".join(t))
            i = j
            continue
        m = re.match(r"^(\s*)([-*+]|\d+[.)])\s+(.*)$", line)
        if m:
            ind = len(m.group(1).replace("\t", "    "))
            typ = "ol" if re.match(r"\d", m.group(2)) else "ul"
            if not lists or lists[-1][1] < ind:
                flush_para()
                close_lists(ind)
                if lists and lists[-1][1] < ind:
                    out[-1] = out[-1].rstrip("</li>") + f"\n<{typ}>\n<li>"
                else:
                    out.append(f"<{typ}><li>")
                lists.append((typ, ind))
            elif lists[-1][1] == ind and lists[-1][0] != typ:
                close_lists(ind)
                out.append(f"<{typ}><li>")
                lists.append((typ, ind))
            else:
                out.append("</li><li>")
            out.append(inline(esc(m.group(3)))
                       )
            i += 1
            continue
        para.append(s)
        i += 1
    flush_para()
    close_lists()
    return "\n".join(out)


# ---------------------------------------------------------------------------

DATA_RE = re.compile(r"const DATA\s*=\s*(\{.*?\});\s*\nconst ", re.S)


def slugify(s, fallback):
    s = (s or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or fallback


def extract_companion_data(html_path):
    html = open(html_path, encoding="utf-8").read()
    m = DATA_RE.search(html)
    if not m:
        return None
    try:
        raw = m.group(1).replace("<\\/", "</")
        d = json.loads(raw)
        if "rendered" not in d and "pages" in d:
            d["rendered"] = d["pages"]
        return d
    except Exception:
        return None


def sanitize_mermaid(src):
    """修复 Mermaid 常见语法雷：标签内 " | "、标签内半角括号（会与形状语法冲突）。
    只改标签内部，保留 root((...)) / A(...) 等合法形状语法。"""
    src = src.replace(" | ", " ｜ ")

    def _wrap(ch_l, ch_r):
        def fn(m):
            inner = m.group(1)
            if "(" in inner or ")" in inner:
                inner = inner.replace("(", "（").replace(")", "）")
            return ch_l + inner + ch_r
        return fn

    src = re.sub(r"\[([^\[\]\n]*)\]", _wrap("[", "]"), src)
    src = re.sub(r"\|([^|\n]*)\|", _wrap("|", "|"), src)
    src = re.sub(r"\{([^{}\n]*)\}", _wrap("{", "}"), src)
    return src


def normalize_book(key, data):
    man = data.get("manifest") or {}
    rendered = data.get("rendered") or {}

    # ① 内部链接 #/xxx => #/book/<key>/xxx
    rendered = {pid: re.sub(r'href="#/', f'href="#/book/{key}/', h) for pid, h in rendered.items()}

    # ①b Mermaid 标签内的 " | " 与半角括号会破坏语法 → 修正
    rendered = {pid: re.sub(
        r'(<div class="mermaid" data-src="1">)(.*?)(</div>)',
        lambda m: m.group(1) + sanitize_mermaid(m.group(2)) + m.group(3),
        h, flags=re.S) for pid, h in rendered.items()}

    # ② 测验 id 按章节加前缀（不同书/不同章都会重复 q01）
    quiz_cov = {}
    for ch in man.get("chapters", []):
        cid = ch.get("id")
        pid = f"__quiz_{cid}__"
        if pid not in rendered:
            continue
        h = rendered[pid]
        def _pfx(m):
            v = m.group(1)
            return v if v.startswith(str(cid) + "-") else f"{cid}-{v}"
        h = re.sub(r"data-qid='([^']+)'", lambda m: f"data-qid='{_pfx(m)}'", h)
        h = re.sub(r"name='([^']+)'", lambda m: f"name='{_pfx(m)}'", h)
        rendered[pid] = h
        quiz_cov[cid] = True
    for q in man.get("quizzes", []):
        cid = q.get("chapterId")
        if cid and quiz_cov.get(cid):
            qid = str(q.get("id", ""))
            if not qid.startswith(str(cid) + "-"):
                q["id"] = f"{cid}-{qid}"

    # ③ 聚合「全部测验」
    parts = ["<h1>全部测验</h1><p>全书各章测验汇总：逐题作答，提交后即时反馈并显示解析。</p>"]
    for ch in man.get("chapters", []):
        pid = f"__quiz_{ch.get('id')}__"
        if pid not in rendered:
            continue
        h = rendered[pid]
        h = re.sub(r"^\s*<h1>.*?</h1>", "", h, count=1, flags=re.S)
        parts.append(f"<h2>测验：{esc(ch.get('title', ch.get('id')))}</h2>" + h)
    # 单书自带的综合测验页不能被覆盖，否则跨章联考题会丢
    extra = rendered.get("__quiz_all__", "")
    if "quiz-item" in extra:
        extra = re.sub(r"^\s*<h1>.*?</h1>", "", extra, count=1, flags=re.S)
        parts.append("<h2>综合测验（多章联考）</h2>" + extra)
    rendered["__quiz_all__"] = "".join(parts)

    data["rendered"] = rendered
    data["quizCoverage"] = quiz_cov
    return data


def clean_title(t):
    t = t or ""
    for suf in ("点化学习系统", "点化学习伴侣", "学习伴侣", "·"):
        t = t.replace(suf, "")
    return re.sub(r"[《》]", "", t).strip() or t


def discover(root, order=None, label_map=None):
    dirs = []
    for name in sorted(os.listdir(root)):
        p = os.path.join(root, name)
        if not os.path.isdir(p) or name.startswith((".", "_")):
            continue
        if not os.path.exists(os.path.join(p, "manifest.json")):
            continue
        htmls = [f for f in os.listdir(p) if f.lower().endswith(".html") and f != "index.html"]
        if not htmls:
            continue
        dirs.append((name, p, htmls))

    if order:
        wanted = [x.strip() for x in order.split(",") if x.strip()]
        def ok(name):
            return any(name == w or name.startswith(w + "-") or name.startswith(w) for w in wanted)
        dirs = [d for d in dirs if ok(d[0])]

    books = []
    for idx, (name, path, htmls) in enumerate(dirs, 1):
        man = json.load(open(os.path.join(path, "manifest.json"), encoding="utf-8"))
        key = slugify(man.get("slug") or "", f"b{idx:02d}")
        # slug 冲突时加序号
        if any(b["key"] == key for b in books):
            key = f"{key}-{idx}"
        comp = man.get("companion")
        if comp and os.path.exists(os.path.join(path, comp)):
            comp_html = comp
        else:
            comp_html = max(htmls, key=lambda f: os.path.getsize(os.path.join(path, f)))
        label = (label_map or {}).get(name) or (label_map or {}).get(key) or clean_title(man.get("title", name))
        books.append({
            "key": key, "dir": name, "path": path, "manifest": man,
            "companion": os.path.join(name, comp_html).replace(os.sep, "/"),
            "label": label,
        })
    return books


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True, help="点化学习系统根目录")
    ap.add_argument("--out", default=None, help="输出 index.html 路径（默认 <root>/index.html）")
    ap.add_argument("--cross-dir", default=None, help="跨书总览目录名（默认自动找 00-* 或含'总览'的目录）")
    ap.add_argument("--order", default=None, help="只纳入指定前缀/目录名，逗号分隔，如 01,02")
    ap.add_argument("--label", action="append", default=[], help="自定义标签，格式 目录名=标签 或 key=标签")
    ap.add_argument("--no-md", action="store_true", help="不生成 index.md")
    args = ap.parse_args()

    root = os.path.abspath(args.root)
    label_map = {}
    for item in args.label:
        if "=" in item:
            k, v = item.split("=", 1)
            label_map[k.strip()] = v.strip()

    books = discover(root, args.order, label_map)
    if not books:
        sys.exit("未发现任何书（需子目录含 manifest.json 与 *.html）")

    print(f"发现 {len(books)} 本书：")
    for b in books:
        print(f"  - {b['key']}  {b['dir']}  ({b['label']})")

    payload_books = {}
    meta = []
    for b in books:
        data = extract_companion_data(os.path.join(b["path"], os.path.basename(b["companion"])))
        if data is None:
            sys.exit(f"无法从 {b['companion']} 抽取数据；请确认该 HTML 由 build_companion.py 生成")
        nb = normalize_book(b["key"], data)
        payload_books[b["key"]] = {
            "manifest": nb["manifest"],
            "rendered": nb["rendered"],
            "nav": nb.get("nav", []),
            "quizCoverage": nb.get("quizCoverage", {}),
        }
        man = nb["manifest"]
        meta.append({
            "key": b["key"], "title": b["label"], "subtitle": man.get("subtitle", ""),
            "chapters": len(man.get("chapters", [])), "concepts": len(man.get("concepts", [])),
            "quizzes": len(man.get("quizzes", [])), "cards": len(man.get("flashcards", [])),
            "companion": b["companion"],
        })

    # 跨书总览
    cross_dir = None
    if args.cross_dir:
        cross_dir = os.path.join(root, args.cross_dir)
    else:
        for name in sorted(os.listdir(root)):
            p = os.path.join(root, name)
            if os.path.isdir(p) and (name.startswith("00") or "总览" in name):
                if any(f.endswith(".md") for f in os.listdir(p)):
                    cross_dir = p
                    break
    cross, cross_meta = {}, []
    if cross_dir and os.path.isdir(cross_dir):
        pref = {"README.md": 0, "跨书概念映射表.md": 1, "综合检验建议.md": 2, "交付说明.md": 3}
        files = sorted([f for f in os.listdir(cross_dir) if f.endswith(".md")],
                       key=lambda f: (pref.get(f, 99), f))
        for i, fn in enumerate(files, 1):
            md = open(os.path.join(cross_dir, fn), encoding="utf-8").read()
            m = re.search(r"^#\s+(.*)$", md, re.M)
            label = m.group(1).strip() if m else fn[:-3]
            key = f"doc{i}"
            cross[key] = md2html(md)
            cross_meta.append({"key": key, "label": label, "file": fn})
    if not cross:
        # 单书/无总览：合成一页总览
        md = ["# 总览\n", "本学习系统包含以下书籍：\n", "| 书 | 章节 | 概念 | 测验 | 抽认卡 |", "|---|---|---|---|---|"]
        for m in meta:
            md.append(f"| {m['title']} | {m['chapters']} | {m['concepts']} | {m['quizzes']} | {m['cards']} |")
        md.append("\n> 建议从顶部标签选择一本书，按「学习路径」顺序推进。")
        cross["doc1"] = md2html("\n".join(md))
        cross_meta.append({"key": "doc1", "label": "总览", "file": "-"})

    tabs = [{"key": "cross", "label": "总览" if len(books) == 1 else "跨书总览"}]
    tabs += [{"key": m["key"], "label": m["title"]} for m in meta]

    def dump(o):
        return json.dumps(o, ensure_ascii=False).replace("</", "<\\/")

    payload = "{" + ",".join(
        f'"{k}":' + dump(v) for k, v in payload_books.items()) + "}"

    html = _SHELL.replace("__BOOKS__", payload)
    html = html.replace("__META__", dump(meta))
    html = html.replace("__CROSS__", dump(cross))
    html = html.replace("__CROSS_META__", dump(cross_meta))
    html = html.replace("__TABS__", dump(tabs))
    html = html.replace("__FIRST_DOC__", dump(cross_meta[0]["key"]))

    out_path = args.out or os.path.join(root, "index.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"已生成 {out_path} ({os.path.getsize(out_path)/1024:.0f} KB, {len(books)} 本书, {len(cross)} 篇总览)")

    if not args.no_md:
        md_path = os.path.join(os.path.dirname(out_path), "index.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(_index_md(meta, cross_meta, root, out_path))
        print(f"已生成 {md_path}")


def _index_md(meta, cross_meta, root, out_path):
    lines = ["# 学习总手册", "",
             f"**[打开总学习手册（index.html）]({os.path.basename(out_path)})** —— 统一入口，单文件可离线；"
             "顶部切换书籍，左侧按学习路径/章节/概念/测验/抽认卡/术语/模式/速查浏览，进度自动保存。", "",
             "## 书籍", "", "| 书 | 章节 | 概念 | 测验 | 抽认卡 | 学习伴侣 |", "|---|---|---|---|---|---|"]
    for m in meta:
        lines.append(f"| {m['title']} | {m['chapters']} | {m['concepts']} | {m['quizzes']} | "
                     f"{m['cards']} | [{os.path.basename(m['companion'])}]({m['companion']}) |")
    if cross_meta:
        lines += ["", "## 跨书总览", ""]
        for c in cross_meta:
            if c["file"] not in ("-",):
                lines.append(f"- [{c['label']}]({'00-跨书总览' if os.path.isdir(os.path.join(root, '00-跨书总览')) else ''}/{c['file']})")
            else:
                lines.append(f"- {c['label']}")
    lines += ["", "## 使用方法", "",
              "1. 双击 `index.html` 打开总学习手册（离线可用；Mermaid 图联网时渲染，离线显示源码）。",
              "2. 每本书含：学习路径 → 章节精讲 → 概念页 → 测验 → 抽认卡 → 术语表 → 模式库 → 速查表。",
              "3. 部署 GitHub Pages：把本目录全部文件放到仓库根目录，`git push` 后在 Settings→Pages 选 `main` + `/ (root)`。", ""]
    return "\n".join(lines)


_SHELL = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>学习总手册</title>
<style>
:root{
  --bg:#f7f7f8; --panel:#ffffff; --text:#1f2328; --muted:#6b7280;
  --accent:#2563eb; --accent-soft:#dbeafe; --border:#e5e7eb;
  --ok:#16a34a; --bad:#dc2626; --code-bg:#f3f4f6;
}
[data-theme="dark"]{
  --bg:#111318; --panel:#1a1d24; --text:#e5e7eb; --muted:#9ca3af;
  --accent:#60a5fa; --accent-soft:#1e3a5f; --border:#2d333d;
  --ok:#4ade80; --bad:#f87171; --code-bg:#20242c;
}
*{box-sizing:border-box}
html,body{margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;
  background:var(--bg);color:var(--text);line-height:1.7;font-size:15px}
a{color:var(--accent);text-decoration:none}
a:hover{text-decoration:underline}
header{position:sticky;top:0;z-index:20;background:var(--panel);border-bottom:1px solid var(--border);padding:10px 18px}
.brand{font-size:17px;font-weight:700;display:inline-block;margin-right:18px}
.brand span{color:var(--muted);font-weight:400;font-size:12px;margin-left:6px}
.tabs{display:inline-flex;gap:6px;flex-wrap:wrap;vertical-align:middle}
.tab{border:1px solid var(--border);background:var(--bg);color:var(--text);border-radius:999px;padding:4px 14px;cursor:pointer;font-size:13px}
.tab.active{background:var(--accent);border-color:var(--accent);color:#fff}
.hdr-right{float:right;display:flex;gap:8px;align-items:center;margin-top:2px}
#q{width:260px;padding:6px 10px;border:1px solid var(--border);border-radius:8px;background:var(--bg);color:var(--text);font-size:13px}
#theme-btn{border:1px solid var(--border);background:var(--panel);color:var(--text);border-radius:8px;padding:5px 12px;cursor:pointer;white-space:nowrap}
.layout{display:flex;min-height:calc(100vh - 60px)}
.sidebar{width:290px;flex:none;background:var(--panel);border-right:1px solid var(--border);
  padding:14px;position:sticky;top:60px;height:calc(100vh - 60px);overflow-y:auto}
#progress-bar{height:5px;background:var(--border);border-radius:3px;margin:6px 0;overflow:hidden}
#progress-bar>div{height:100%;width:0;background:var(--accent);transition:width .3s}
#progress-label{font-size:12px;color:var(--muted);margin-bottom:8px}
.nav-sec{font-size:12px;color:var(--muted);margin:12px 0 4px;text-transform:uppercase;letter-spacing:.4px}
.nav-item{display:block;padding:5px 10px;border-radius:6px;color:var(--text);font-size:14px}
.nav-item:hover{background:var(--accent-soft);text-decoration:none}
.nav-item.active{background:var(--accent-soft);color:var(--accent);font-weight:600}
.nav-item .done{float:right;color:var(--ok);font-size:12px}
#nav-toggle{display:none}
.main{flex:1;min-width:0;padding:28px 40px 80px;max-width:920px}
.page h1{font-size:26px;border-bottom:2px solid var(--border);padding-bottom:8px;margin-top:0}
.page h2{font-size:20px;margin-top:26px}
.page h3{font-size:17px;margin-top:22px}
.page table{border-collapse:collapse;width:100%;margin:12px 0;font-size:14px}
.page th,.page td{border:1px solid var(--border);padding:6px 10px;text-align:left}
.page th{background:var(--code-bg)}
.page code{background:var(--code-bg);padding:2px 5px;border-radius:4px;font-size:.9em}
.page pre{background:var(--code-bg);padding:12px;border-radius:8px;overflow-x:auto;font-size:13px}
.page pre code{background:none;padding:0}
.page blockquote{border-left:4px solid var(--accent);margin:12px 0;padding:6px 14px;background:var(--accent-soft);border-radius:0 6px 6px 0}
.page img{max-width:100%}
.mermaid{background:var(--code-bg);padding:14px;border-radius:8px;overflow-x:auto;font-family:ui-monospace,Menlo,Consolas,monospace;font-size:12.5px;white-space:pre;color:var(--muted)}
.mermaid-hint{font-size:12px;color:var(--muted);margin:4px 0 14px}
svg{max-width:100%;height:auto}
.quiz-item{border:1px solid var(--border);border-radius:10px;padding:14px 16px;margin:14px 0;background:var(--panel)}
.quiz-q{margin:0 0 8px;font-weight:500}
.quiz-opts label{display:block;padding:4px 0;cursor:pointer}
.quiz-blank{width:60%;padding:6px 10px;border:1px solid var(--border);border-radius:6px;background:var(--bg);color:var(--text)}
.quiz-check{margin-top:10px;padding:6px 16px;border:none;border-radius:6px;background:var(--accent);color:#fff;cursor:pointer}
.quiz-feedback{margin-left:12px;font-size:13px}
.fb-ok{color:var(--ok)}.fb-bad{color:var(--bad)}
.quiz-explain{margin-top:8px;font-size:13px;color:var(--muted);border-top:1px dashed var(--border);padding-top:6px}
.flashcard{perspective:1200px;margin:24px auto;max-width:520px;cursor:pointer;user-select:none}
.fc-inner{position:relative;width:100%;height:240px;transform-style:preserve-3d;transition:transform .5s}
.flashcard.flip .fc-inner{transform:rotateY(180deg)}
.fc-front,.fc-back{position:absolute;inset:0;backface-visibility:hidden;display:flex;align-items:center;justify-content:center;
  padding:22px;border-radius:14px;border:1px solid var(--border);background:var(--panel);font-size:16px;text-align:center}
.fc-back{transform:rotateY(180deg);background:var(--accent-soft);color:var(--text)}
.card-controls{display:flex;gap:14px;align-items:center;margin:12px 0;flex-wrap:wrap}
.card-actions{display:flex;gap:12px;justify-content:center}
.card-actions button{padding:8px 22px;border:none;border-radius:8px;cursor:pointer;font-size:14px}
#card-known-btn{background:var(--ok);color:#fff}
#card-again-btn{background:var(--bad);color:#fff}
.card-counts{color:var(--muted);font-size:13px}
.path-step{margin:8px 0;padding:10px 12px;border:1px solid var(--border);border-radius:8px;background:var(--panel)}
.path-step.passed{border-color:var(--ok)}
#glossary-filter{width:100%;max-width:380px;padding:7px 10px;border:1px solid var(--border);border-radius:8px;background:var(--bg);color:var(--text);margin-bottom:10px}
#glossary-list li{padding:6px 0;border-bottom:1px dashed var(--border)}
.glossary-ref{color:var(--muted);font-size:12px}
.search-hit{margin:10px 0}
.book-cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:14px;margin:16px 0}
.book-card{border:1px solid var(--border);border-radius:12px;padding:16px;background:var(--panel)}
.book-card h3{margin:0 0 6px;font-size:16px}
.book-card .meta{font-size:13px;color:var(--muted);margin-bottom:10px}
.book-card .enter{font-size:13px}
.empty{color:var(--muted);padding:20px 0}
@media print{header,.sidebar,.quiz-actions,.card-actions,.card-controls{display:none!important}.main{max-width:none;padding:0}}
@media (max-width:820px){.sidebar{width:100%;height:auto;position:static;padding:10px 14px}
  #nav{display:none}.sidebar.open #nav{display:block}
  #nav-toggle{display:block;width:100%;padding:8px 10px;margin:4px 0;border:1px solid var(--border);border-radius:8px;background:var(--bg);color:var(--text);font-size:14px;text-align:left;cursor:pointer}
  .layout{flex-direction:column}.main{padding:16px}
  .hdr-right{float:none;margin-top:8px}#q{width:100%}}
</style>
</head>
<body>
<header>
  <span class="brand">学习总手册<span>点化学习系统 · 统一入口</span></span>
  <span class="tabs" id="tabs"></span>
  <span class="hdr-right">
    <input id="q" type="search" placeholder="全书搜索…">
    <button id="theme-btn">🌙 深色</button>
  </span>
</header>
<div class="layout">
  <aside class="sidebar">
    <div id="progress-bar"><div id="progress-fill"></div></div>
    <div id="progress-label">进度 0%</div>
    <nav id="nav"></nav>
  </aside>
  <main><div id="view" class="page"></div></main>
</div>
<script>
const BOOKS = __BOOKS__;
const META = __META__;
const CROSS = __CROSS__;
const CROSS_META = __CROSS_META__;
const TABS = __TABS__;
const FIRST_DOC = __FIRST_DOC__;
const $ = s => document.querySelector(s);
const esc = s => String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

let cur = {book:'cross', doc:FIRST_DOC, page:'cross'};
const store = {
  get(k){ try{ return JSON.parse(localStorage.getItem(k)||'null') }catch(e){ return null } },
  set(k,v){ try{ localStorage.setItem(k, JSON.stringify(v)) }catch(e){} }
};
function stKey(book,k){ return 'hb:'+book+':'+k; }
function getState(book){
  return { visited: store.get(stKey(book,'visited'))||[], quiz: store.get(stKey(book,'quiz'))||{}, cards: store.get(stKey(book,'cards'))||{} };
}

/* ---------- 路由 ---------- */
function parseHash(){
  let h = location.hash.replace(/^#\//,'');
  if(!h) return {book:'cross', doc:FIRST_DOC, page:'cross'};
  const p = h.split('/');
  if(p[0]==='cross') return {book:'cross', doc:p[1]||FIRST_DOC, page:'cross'};
  if(p[0]==='book'){
    const key=p[1], page=p.slice(2).join('/')||'path';
    return {book:key, page:page, doc:null};
  }
  return {book:'cross', doc:FIRST_DOC, page:'cross'};
}
function pageIdOf(page){
  if(page==='path') return '__path__';
  if(page==='cards') return '__cards__';
  if(page==='glossary') return '__glossary__';
  if(page==='patterns') return '__patterns__';
  if(page==='cheatsheet') return '__cheatsheet__';
  if(page.startsWith('quiz/')) return '__quiz_'+(page.split('/')[1]||'all')+'__';
  if(page.startsWith('chapter/')) return page.slice(8);
  if(page.startsWith('concept/')) return page.slice(8);
  return page;
}

/* ---------- 顶栏 ---------- */
function renderTabs(){
  const el = $('#tabs'); el.innerHTML='';
  TABS.forEach(t=>{
    const b=document.createElement('button');
    b.className='tab'+(cur.book===t.key?' active':'');
    b.textContent=t.label;
    b.onclick=()=>{ location.hash = t.key==='cross' ? '#/cross/'+FIRST_DOC : '#/book/'+t.key+'/path'; };
    el.appendChild(b);
  });
}

/* ---------- 侧栏 ---------- */
function renderNav(){
  const nav=$('#nav'); nav.innerHTML='';
  const add=(label,href,cls)=>{
    const a=document.createElement('a'); a.className='nav-item'+(cls?' '+cls:''); a.href=href; a.textContent=label;
    nav.appendChild(a); return a;
  };
  const sec=t=>{ const d=document.createElement('div'); d.className='nav-sec'; d.textContent=t; nav.appendChild(d); };

  if(cur.book==='cross'){
    sec(CROSS_META.length>1 ? '跨书总览' : '总览');
    CROSS_META.forEach(c=> add(c.label, '#/cross/'+c.key, cur.doc===c.key?'active':''));
    sec('书籍入口');
    META.forEach(m=> add(m.title, '#/book/'+m.key+'/path'));
    updateProgress(0, CROSS_META.length>1 ? '跨书总览' : '总览');
    return;
  }
  const B=BOOKS[cur.book];
  const S=getState(cur.book);
  const man=B.manifest;
  add('学习路径','#/book/'+cur.book+'/path', cur.page==='path'?'active':'');
  sec('章节');
  (man.chapters||[]).forEach(c=>{
    const id=c.id;
    const a=add(c.title, '#/book/'+cur.book+'/chapter/'+id, cur.page==='chapter/'+id?'active':'');
    if(S.visited.includes(cur.book+'/chapter/'+id)){
      const s=document.createElement('span'); s.className='done'; s.textContent='✓'; a.appendChild(s);
    }
  });
  if((man.concepts||[]).length){
    sec('概念');
    man.concepts.forEach(c=>{
      const a=add(c.title, '#/book/'+cur.book+'/concept/'+c.id, cur.page==='concept/'+c.id?'active':'');
      if(S.visited.includes(cur.book+'/concept/'+c.id)){
        const s=document.createElement('span'); s.className='done'; s.textContent='✓'; a.appendChild(s);
      }
    });
  }
  sec('测验');
  add('全部测验','#/book/'+cur.book+'/quiz/all', cur.page==='quiz/all'?'active':'');
  (man.chapters||[]).forEach(c=>{
    if(!((B.quizCoverage||{})[c.id])) return;
    add('测验：'+c.title, '#/book/'+cur.book+'/quiz/'+c.id, cur.page==='quiz/'+c.id?'active':'');
  });
  sec('复习工具');
  add('抽认卡','#/book/'+cur.book+'/cards', cur.page==='cards'?'active':'');
  add('术语表','#/book/'+cur.book+'/glossary', cur.page==='glossary'?'active':'');
  if(B.rendered['__patterns__']) add('模式库','#/book/'+cur.book+'/patterns', cur.page==='patterns'?'active':'');
  if(B.rendered['__cheatsheet__']) add('速查表','#/book/'+cur.book+'/cheatsheet', cur.page==='cheatsheet'?'active':'');
  sec('其他');
  const m=META.find(x=>x.key===cur.book);
  if(m) add('单独打开学习伴侣 ↗', encodeURI(m.companion));

  updateProgressBook(cur.book);
}

/* ---------- 进度 ---------- */
function updateProgress(pct,label){
  $('#progress-fill').style.width=pct+'%';
  $('#progress-label').textContent=label;
}
function updateProgressBook(book){
  const B=BOOKS[book], S=getState(book);
  const chs=(B.manifest.chapters||[]).length;
  const done=(B.manifest.chapters||[]).filter(c=>S.visited.includes(book+'/chapter/'+c.id)).length;
  const pct=chs?Math.round(done/chs*100):0;
  $('#progress-fill').style.width=pct+'%';
  $('#progress-label').textContent=`《${(META.find(x=>x.key===book)||{}).title||book}》 进度 ${pct}% · 已学 ${done}/${chs} 章`;
}

/* ---------- 渲染 ---------- */
function renderCross(){
  const v=$('#view');
  const docId=cur.doc||FIRST_DOC;
  const html=CROSS[docId]||'<div class="empty">页面不存在</div>';
  let pre='';
  if(docId===FIRST_DOC){
    pre = '<h1>学习总手册</h1>'
      + '<p>本学习系统把书点化为一套可跟着走的学习内容。顶部切换书籍，或用下方卡片进入；'
      + '每本书含学习路径、章节精讲、概念页、测验、抽认卡、术语表、模式库与速查表，进度自动保存在本机浏览器。</p>'
      + '<div class="book-cards">'
      + META.map(m=>`<div class="book-card"><h3>${esc(m.title)}</h3>
          <div class="meta">${m.chapters} 章 · ${m.concepts} 概念 · ${m.quizzes} 测验 · ${m.cards} 抽认卡</div>
          <div class="enter"><a href="#/book/${m.key}/path">进入学习 →</a> &nbsp;|&nbsp;
          <a href="${encodeURI(m.companion)}" target="_blank">单独伴侣 ↗</a></div></div>`).join('')
      + '</div>';
  }
  v.innerHTML = pre + html;
  renderMermaid();
}

function renderBook(){
  const B=BOOKS[cur.book];
  if(!B){ $('#view').innerHTML='<div class="empty">书目不存在</div>'; return; }
  const pid=pageIdOf(cur.page);
  let html=B.rendered[pid];
  if(!html){ html='<div class="empty">页面不存在</div>'; }
  const S=getState(cur.book);
  if((cur.page.startsWith('chapter/')||cur.page.startsWith('concept/')) && !S.visited.includes(cur.book+'/'+cur.page)){
    S.visited.push(cur.book+'/'+cur.page);
    store.set(stKey(cur.book,'visited'), S.visited);
  }
  $('#view').innerHTML=html;
  if(cur.page==='cards') initCards();
  if(cur.page==='glossary') initGlossary();
  if(cur.page.startsWith('quiz/')) initQuizzes();
  if(pid==='__path__') updatePath();
  renderMermaid();
}

/* ---------- 测验 ---------- */
function initQuizzes(){
  const B=BOOKS[cur.book];
  document.querySelectorAll('.quiz-item').forEach(item=>{
    const btn=item.querySelector('.quiz-check');
    if(!btn||item.dataset.inited) return;
    item.dataset.inited='1';
    btn.addEventListener('click',()=>{
      const qid=item.dataset.qid, type=item.dataset.type;
      const q=(B.manifest.quizzes||[]).find(x=>x.id===qid); if(!q) return;
      let user=null, correct=false, fb='';
      if(type==='single'){
        const sel=item.querySelector('input:checked');
        user=sel?parseInt(sel.value):null;
        correct=(user===q.answer);
        fb=correct?'✓ 正确':'✗ 错误'+(user==null?'（未作答）':'');
      }else if(type==='multi'){
        user=Array.from(item.querySelectorAll('input:checked')).map(i=>parseInt(i.value)).sort();
        const ans=Array.isArray(q.answer)?q.answer.slice().sort():[q.answer];
        correct=user.length>0 && JSON.stringify(user)===JSON.stringify(ans);
        fb=correct?'✓ 正确':'✗ 错误';
      }else if(type==='blank'){
        const v=(item.querySelector('.quiz-blank').value||'').trim().toLowerCase();
        correct=(v===String(q.answer).trim().toLowerCase());
        fb=correct?'✓ 正确':'✗ 错误'+(v?'':'（未作答）');
      }
      item.querySelectorAll('input:checked').forEach(i=>{
        const val=parseInt(i.value);
        if(Array.isArray(q.answer)?q.answer.includes(val):val===q.answer) i.parentElement.style.color='var(--ok)';
        else i.parentElement.style.color='var(--bad)';
      });
      const feed=item.querySelector('.quiz-feedback');
      feed.className='quiz-feedback '+(correct?'fb-ok':'fb-bad');
      feed.textContent=fb;
      let ex=item.querySelector('.quiz-explain');
      if(!ex){ ex=document.createElement('div'); ex.className='quiz-explain'; item.appendChild(ex); }
      ex.innerHTML='解析：'+esc(q.explain||'');
      const S=getState(cur.book);
      const ch=q.chapterId||'__all__';
      if(!S.quiz[ch]) S.quiz[ch]={n:0};
      S.quiz[ch].n+=1;
      store.set(stKey(cur.book,'quiz'), S.quiz);
    });
  });
}
function updatePath(){
  const B=BOOKS[cur.book], S=getState(cur.book);
  document.querySelectorAll('.path-step').forEach(el=>{
    const step=el.id.replace('path-','');
    const s=(B.manifest.learningPath||[]).find(x=>String(x.step)===step);
    if(s && (s.chapterIds||[]).every(c=>S.visited.includes(cur.book+'/chapter/'+c))){
      el.classList.add('passed');
      if(!el.querySelector('.ck')){ const sp=document.createElement('span'); sp.className='ck done'; sp.textContent=' ✓ 已完成'; el.appendChild(sp); }
    }
  });
}

/* ---------- 抽认卡 ---------- */
let cardIdx=0, cardList=[];
function initCards(){
  const B=BOOKS[cur.book];
  const cards=B.manifest.flashcards||[];
  cardList=cards.slice(); cardIdx=0;
  if(!$('#card-done')){
    const d=document.createElement('div'); d.id='card-done'; d.className='empty';
    d.style.display='none'; d.textContent='本组卡片已全部复习完 🎉';
    const st=$('#card-stage'); if(st) st.appendChild(d);
  }
  const sel=$('#card-filter'); if(!sel) return;
  sel.innerHTML='<option value="">全部</option>';
  [...new Set(cards.map(c=>c.chapterId).filter(Boolean))].forEach(c=>{
    const o=document.createElement('option'); o.value=c;
    const ch=(B.manifest.chapters||[]).find(x=>x.id===c);
    o.textContent=ch?ch.title:c; sel.appendChild(o);
  });
  sel.onchange=()=>{ const v=sel.value; cardList=v?cards.filter(c=>c.chapterId===v):cards.slice(); cardIdx=0; showCard(); };
  $('#flashcard').onclick=()=>$('#flashcard').classList.toggle('flip');
  $('#card-known-btn').onclick=()=>markCard(true);
  $('#card-again-btn').onclick=()=>markCard(false);
  showCard();
}
function showCard(){
  const S=getState(cur.book);
  updateCardCounts();
  const done=$('#card-done'), fc=$('#flashcard');
  if(cardIdx>=cardList.length){
    if(done) done.style.display=''; if(fc) fc.style.display='none'; return;
  }
  if(done) done.style.display='none'; if(fc) fc.style.display='';
  const c=cardList[cardIdx];
  document.querySelector('.fc-front').textContent=c.front;
  document.querySelector('.fc-back').textContent=c.back;
  $('#flashcard').classList.remove('flip');
}
function markCard(known){
  const S=getState(cur.book);
  const c=cardList[cardIdx]; if(!c) return;
  S.cards[c.id]=known?'known':'again';
  store.set(stKey(cur.book,'cards'), S.cards);
  cardIdx++; showCard();
}
function updateCardCounts(){
  const S=getState(cur.book);
  const known=Object.values(S.cards).filter(v=>v==='known').length;
  const again=Object.values(S.cards).filter(v=>v==='again').length;
  const k=$('#card-known'), a=$('#card-again'), l=$('#card-left');
  if(k) k.textContent=known; if(a) a.textContent=again; if(l) l.textContent=Math.max(0,cardList.length-cardIdx);
}

/* ---------- 术语表 ---------- */
function initGlossary(){
  const input=$('#glossary-filter');
  if(!input||input.dataset.inited) return;
  input.dataset.inited='1';
  input.oninput=()=>{
    const v=input.value.trim().toLowerCase();
    document.querySelectorAll('#glossary-list li').forEach(li=>{
      li.style.display=(!v||li.dataset.term.includes(v))?'':'none';
    });
  };
}

/* ---------- 全局搜索 ---------- */
let searchIdx=null;
function buildSearch(){
  if(searchIdx) return searchIdx;
  searchIdx=[];
  META.forEach(m=>{
    const B=BOOKS[m.key];
    Object.entries(B.rendered).forEach(([pid,html])=>{
      if(pid.startsWith('__')) return;
      const text=html.replace(/<[^>]+>/g,' ').replace(/\s+/g,' ');
      searchIdx.push({book:m.key, page:pdfToPage(pid, B), text, label:m.title});
    });
  });
  Object.entries(CROSS).forEach(([k,html])=>{
    const meta=CROSS_META.find(x=>x.key===k)||{};
    searchIdx.push({book:'cross', page:'cross/'+k, text:html.replace(/<[^>]+>/g,' ').replace(/\s+/g,' '), label:(meta.label||'总览')});
  });
  return searchIdx;
}
function pdfToPage(pid, B){
  if(pid.startsWith('__quiz_')) return 'quiz/'+pid.replace('__quiz_','').replace('__','');
  if(pid==='__path__') return 'path';
  if(pid==='__cards__') return 'cards';
  if(pid==='__glossary__') return 'glossary';
  if(pid==='__patterns__') return 'patterns';
  if(pid==='__cheatsheet__') return 'cheatsheet';
  const ch=(B.manifest.chapters||[]).find(c=>c.id===pid);
  if(ch) return 'chapter/'+pid;
  return 'concept/'+pid;
}
$('#q').addEventListener('input', e=>{
  const v=e.target.value.trim().toLowerCase();
  if(!v){ route(); return; }
  const hits=buildSearch().filter(p=>p.text.toLowerCase().includes(v)).slice(0,40);
  $('#view').innerHTML='<h1>搜索结果：'+esc(v)+'</h1>'+
    (hits.length? hits.map(h=>{
      const href=h.book==='cross'?('#/cross/'+(h.page.split('/')[1]||FIRST_DOC)):('#/book/'+h.book+'/'+h.page);
      return `<div class="search-hit"><a href="${href}">${esc(h.label)}</a><br><span style="color:var(--muted);font-size:13px">${esc(h.text.slice(0,200))}</span></div>`;
    }).join('') : '<div class="empty">未找到相关内容，试试章节名 / 概念名 / 术语。</div>');
});

/* ---------- Mermaid ---------- */
let mermaidState='idle';
function renderMermaid(){
  const els=Array.from(document.querySelectorAll('.mermaid')).filter(el=>!el.dataset.rendered);
  if(!els.length) return;
  const run=()=>{ try{
    mermaid.initialize({startOnLoad:false, theme:document.body.dataset.theme==='dark'?'dark':'default'});
    els.forEach((el,idx)=>{ try{
      const out=mermaid.render('mm'+Date.now()+idx, el.textContent);
      if(out && typeof out.then==='function'){
        out.then(r=>{ el.innerHTML=r.svg; el.dataset.rendered='1'; }).catch(()=>{ el.dataset.rendered='0'; });
      } else { el.innerHTML=out; el.dataset.rendered='1'; }
    } catch(e){ el.dataset.rendered='0'; } });
  }catch(e){} };
  if(window.mermaid){ run(); return; }
  if(mermaidState==='loading') return;
  mermaidState='loading';
  const urls=['https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js',
              'https://unpkg.com/mermaid@10/dist/mermaid.min.js',
              'https://registry.npmmirror.com/mermaid/10/files/dist/mermaid.min.js'];
  let ui=0;
  const tryNext=()=>{
    if(ui>=urls.length){ mermaidState='failed'; return; }
    const s=document.createElement('script');
    s.src=urls[ui++];
    s.onload=()=>{ mermaidState='loaded'; run(); };
    s.onerror=()=>{ s.remove(); tryNext(); };
    document.head.appendChild(s);
  };
  tryNext();
}

/* ---------- 主题 ---------- */
const themeBtn=$('#theme-btn');
themeBtn.onclick=()=>{
  const d=document.body.dataset.theme==='dark';
  document.body.dataset.theme=d?'':'dark';
  themeBtn.textContent=d?'🌙 深色':'☀️ 浅色';
};

/* ---------- 启动 ---------- */
function route(){
  cur=parseHash();
  renderTabs();
  renderNav();
  if(cur.book==='cross') renderCross(); else renderBook();
  window.scrollTo(0,0);
}
window.addEventListener('hashchange', route);
(function(){
  const sb=document.querySelector('.sidebar'); if(!sb) return;
  const btn=document.createElement('button'); btn.id='nav-toggle'; btn.textContent='目录（点开选择章节）';
  btn.onclick=()=>sb.classList.toggle('open');
  sb.insertBefore(btn, sb.querySelector('#nav'));
  window.addEventListener('hashchange',()=>{ if(window.innerWidth<=820) sb.classList.remove('open'); });
})();
route();
</script>
</body>
</html>
"""

if __name__ == "__main__":
    main()
