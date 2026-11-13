#!/usr/bin/env python3
"""zhishu（知枢）: 把 Markdown 学习知识库 + manifest.json 组装成单文件交互 HTML 学习伴侣。

用法：
  python3 build_companion.py --manifest <dir>/manifest.json --out <dir>/<slug>-companion.html

在 book-enlighten 基础上新增：
- 出处脚注（每个章节/概念/题目标注原文页码）
- KaTeX 数学公式渲染（CDN 多源回退，与 mermaid 同策略）
- 深度推导片段折叠（<details>），默认收起
- 诊断模式：答错沿书内依赖图回溯前置概念，跳转并展开深度片段
- 概念/章节的 prerequisites 依赖字段
"""
import argparse
import html as html_mod
import json
import os
import re
import sys

# ----------------------------------------------------------------------------
# 最小 Markdown 渲染器（支持正文常用语法 + 安全 HTML 透传 + LaTeX 公式）
# ----------------------------------------------------------------------------

ALLOWED_RAW_TAGS = {
    "div", "span", "svg", "path", "rect", "circle", "line", "polyline",
    "polygon", "g", "text", "tspan", "defs", "lineargradient", "stop",
    "ellipse", "marker", "use", "a", "img", "details", "summary",
    "b", "i", "u", "br", "hr", "strong", "em", "code", "pre",
    "sub", "sup", "table", "thead", "tbody", "tr", "td", "th",
    "ul", "ol", "li", "p", "h1", "h2", "h3", "h4", "h5", "h6",
    "blockquote", "figure", "figcaption", "center",
}


def _escape(text):
    return html_mod.escape(text, quote=True)


def _sanitize_url(url):
    if re.match(r"^(https?://|mailto:|#|/|\.\.?/)", url, re.I):
        return _escape(url)
    return "#"


def _inline(text):
    """处理行内语法：code / **bold** / *italic* / [link](url) / $math$。输入为已转义文本。"""
    # `code`（先保护 code 内的内容不被其他规则误处理）
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    # [text](url)
    def _link(m):
        label, url = m.group(1), m.group(2)
        return f'<a href="{_sanitize_url(url)}" target="_blank" rel="noopener">{label}</a>'
    text = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", _link, text)
    # **bold**
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    # *italic*
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", text)
    # $行内公式$（不跨越换行，不匹配 $$）
    text = re.sub(r"(?<!\$)\$([^\$\n]+?)\$(?!\$)", r'<span class="katex-inline">\1</span>', text)
    return text


def _split_table_row(text):
    """按表格分隔符切分，但忽略公式内与转义的竖线。"""
    s = text.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|") and not s.endswith("\\|"):
        s = s[:-1]
    cells, cur, in_math, i = [], [], False, 0
    while i < len(s):
        ch = s[i]
        if ch == "\\" and i + 1 < len(s):
            cur.append(ch); cur.append(s[i + 1]); i += 2; continue
        if ch == "$":
            in_math = not in_math; cur.append(ch); i += 1; continue
        if ch == "|" and not in_math:
            cells.append("".join(cur).strip()); cur = []; i += 1; continue
        cur.append(ch); i += 1
    cells.append("".join(cur).strip())
    return cells


def _is_raw_open(line):
    m = re.match(r"^\s*</?([a-zA-Z0-9]+)", line)
    return m and m.group(1).lower() in ALLOWED_RAW_TAGS


def md_to_html(md_text):
    """把 Markdown 文本渲染为 HTML。输出已转义 + 安全透传。"""
    lines = md_text.replace("\r\n", "\n").split("\n")
    out = []
    i = 0
    n = len(lines)

    def flush_para(buf):
        if buf:
            txt = _inline(_escape(" ".join(buf).strip()))
            if txt:
                out.append(f"<p>{txt}</p>")
            buf.clear()

    para = []
    in_code = False
    code_buf = []
    code_lang = ""
    list_stack = []

    def close_lists(min_indent=0):
        while list_stack and list_stack[-1][1] >= min_indent:
            typ, _ = list_stack.pop()
            out.append("</ol>" if typ == "ol" else "</ul>")

    while i < n:
        line = lines[i]

        # 代码块
        if line.lstrip().startswith("```"):
            if in_code:
                lang = code_lang or ""
                cls = f' class="lang-{lang}"' if lang else ""
                if lang.lower() == "mermaid":
                    src = _escape("\n".join(code_buf))
                    out.append(
                        f'<div class="mermaid" data-src="1">{src}</div>'
                        f'<p class="mermaid-hint">↑ Mermaid 图示：联网时自动渲染为图表；离线时请阅读上方源码与正文说明。</p>')
                else:
                    out.append(f"<pre{cls}><code>{_escape(chr(10).join(code_buf))}</code></pre>")
                in_code = False
                code_buf = []
            else:
                flush_para(para)
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

        # $$ 块级公式（支持单行 $$...$$ 和多行 $$ 开头到 $$ 结尾）
        if line.strip().startswith("$$"):
            flush_para(para)
            close_lists()
            stripped_line = line.strip()
            # 单行情况：$$...$$
            if stripped_line.endswith("$$") and len(stripped_line) > 4:
                formula_src = stripped_line[2:-2].strip()
                formula_src = re.sub(r"<([a-zA-Z])", r"&lt;\1", formula_src)
                out.append(f'<div class="katex-block">{formula_src}</div>')
                i += 1
                continue
            # 多行情况
            formula_lines = []
            i += 1
            while i < n and not lines[i].strip().endswith("$$"):
                formula_lines.append(lines[i])
                i += 1
            if i < n:
                last = lines[i].strip()[:-2]
                if last:
                    formula_lines.append(last)
                i += 1
            formula_src = "\\\\".join(formula_lines).strip()
            # 公式内容不能整段 _escape（会把 LaTeX 反斜杠也转义），
            # 但必须把 < 后跟字母的位置转成 &lt;，否则浏览器当标签解析，DOM 被拆坏
            # （first-principles-derivation 踩过的坑：$m<n$ 会只剩 $m）
            formula_src = re.sub(r"<([a-zA-Z])", r"&lt;\1", formula_src)
            out.append(f'<div class="katex-block">{formula_src}</div>')
            continue

        # 原始 HTML 透传
        if _is_raw_open(line):
            flush_para(para)
            close_lists()
            raw_buf = [line]
            j = i + 1
            while j < n and _is_raw_open(lines[j]):
                raw_buf.append(lines[j])
                j += 1
            out.append("\n".join(raw_buf))
            i = j
            continue

        stripped = line.strip()

        if not stripped:
            flush_para(para)
            close_lists()
            i += 1
            continue

        # 标题
        m = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if m:
            flush_para(para)
            close_lists()
            level = len(m.group(1))
            out.append(f"<h{level}>{_inline(_escape(m.group(2)))}</h{level}>")
            i += 1
            continue

        if re.match(r"^(-{3,}|\*{3,}|_{3,})$", stripped):
            flush_para(para)
            close_lists()
            out.append("<hr>")
            i += 1
            continue

        if stripped.startswith(">"):
            flush_para(para)
            quote = _inline(_escape(re.sub(r"^>\s?", "", stripped)))
            out.append(f"<blockquote>{quote}</blockquote>")
            i += 1
            continue

        # 表格
        if stripped.startswith("|") and i + 1 < n and re.match(r"^\s*\|?[\s:\-|]+\|?\s*$", lines[i + 1]):
            flush_para(para)
            close_lists()
            header = _split_table_row(stripped)
            rows = []
            j = i + 2
            while j < n and lines[j].strip().startswith("|"):
                rows.append(_split_table_row(lines[j]))
                j += 1
            tbl = ["<table><thead><tr>"]
            for c in header:
                tbl.append(f"<th>{_inline(_escape(c))}</th>")
            tbl.append("</tr></thead><tbody>")
            for r in rows:
                tbl.append("<tr>")
                for c in r:
                    tbl.append(f"<td>{_inline(_escape(c))}</td>")
                tbl.append("</tr>")
            tbl.append("</tbody></table>")
            out.append("".join(tbl))
            i = j
            continue

        # 列表
        m = re.match(r"^(\s*)([-*+]|\d+[.)])\s+(.*)$", line)
        if m:
            indent = len(m.group(1).replace("\t", "    "))
            typ = "ol" if re.match(r"\d", m.group(2)) else "ul"
            content = m.group(3)
            if not list_stack or list_stack[-1][1] < indent:
                flush_para(para)
                close_lists(indent)
                if list_stack and list_stack[-1][1] < indent:
                    out[-1] = out[-1].rstrip("</li>") + "\n<" + typ + ">\n<li>"
                else:
                    out.append(f"<{typ}><li>")
                list_stack.append((typ, indent))
            elif list_stack[-1][1] == indent and list_stack[-1][0] != typ:
                close_lists(indent)
                out.append(f"<{typ}><li>")
                list_stack.append((typ, indent))
            else:
                out.append("</li><li>")
            out.append(_inline(_escape(content)))
            i += 1
            continue

        para.append(stripped)
        i += 1

    flush_para(para)
    close_lists()
    return "\n".join(out)


# ----------------------------------------------------------------------------
# 学习伴侣 HTML 组装
# ----------------------------------------------------------------------------

def manifest_ch_title(manifest, cid):
    for c in manifest.get("chapters", []):
        if c["id"] == cid:
            return c.get("title", cid)
    return cid or ""


def _source_badge(source):
    """渲染出处脚注。source 可以是字符串或 {file, page} 对象。"""
    if not source:
        return ""
    if isinstance(source, dict):
        parts = []
        if source.get("file"):
            parts.append(str(source["file"]))
        if source.get("page"):
            parts.append(f"p.{source['page']}")
        src = " · ".join(parts)
    else:
        src = str(source)
    if not src:
        return ""
    return f'<div class="source-badge">📖 出处：{_escape(src)}</div>'


def _depth_fragment_html(data, concept):
    """如果概念有深度推导片段文件，读取并用 <details> 折叠包裹。"""
    df = concept.get("depthFragment")
    if not df:
        return ""
    fp = os.path.join(data["base_dir"], df)
    if not os.path.exists(fp):
        return f'<div class="depth-missing">⚠ 深度推导文件缺失：{_escape(df)}</div>'
    with open(fp, "r", encoding="utf-8") as fh:
        frag_md = fh.read()
    frag_html = md_to_html(frag_md)
    return (f'<details class="depth-fragment">'
            f'<summary>🔬 展开完整第一性原理推导（{_escape(concept.get("title",""))}）</summary>'
            f'<div class="depth-body">{frag_html}</div>'
            f'</details>')


def _load_synonyms(*dirs):
    """读取同义词组：技能自带 references/synonyms.json + 各书目录下可选 synonyms.json。
    返回 [[词,词,...], ...]，组内两两互查；不足两词的组丢弃。"""
    groups, seen = [], set()
    base = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "references", "synonyms.json")
    paths = [base] + [os.path.join(d, "synonyms.json") for d in dirs if d]
    for p in paths:
        if not os.path.exists(p):
            continue
        try:
            obj = json.load(open(p, encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(obj, dict):
            continue
        for _, v in obj.items():
            if not isinstance(v, list):
                continue
            g = []
            for x in v:
                s = str(x).strip()
                if s and s not in g:
                    g.append(s)
            if len(g) < 2:
                continue
            key = tuple(sorted(g))
            if key in seen:
                continue
            seen.add(key)
            groups.append(g)
    return groups

def build_html(data):
    pages = data["pages"]
    manifest = data["manifest"]

    # ---- 学习路径页 ----
    path_html = ["<h1>学习路径</h1>",
                 "<p>按推荐顺序学习；每步通过检查点（自测题）后再继续。</p>",
                 "<ol class='path-list'>"]
    for step in manifest.get("learningPath", []):
        chap_links = "、".join(
            f'<a href="#/chapter/{cid}">{_escape(manifest_ch_title(manifest, cid))}</a>'
            for cid in step.get("chapterIds", []))
        checkpoint = step.get("checkpoint", "")
        cp_html = f"<br>检查点：{_escape(checkpoint)}" if checkpoint else ""
        path_html.append(
            f"<li class='path-step' id='path-{step.get('step','')}'><strong>步骤 {step.get('step','')}："
            f"{_escape(step.get('title',''))}</strong><br>阅读：{chap_links}{cp_html}</li>")
    path_html.append("</ol>")
    path_html.append("<p>进度：<span id='path-progress-label'>0/0</span></p>")
    data["pages"]["__path__"] = {"html": "".join(path_html), "kind": "path", "title": "学习路径"}

    # ---- 知识图谱页（vis-network 力导向图）----
    graph_html = ["<h1>🕸 知识图谱</h1>",
                  "<p>节点是概念，边是先修关系。拖拽节点、滚轮缩放，点击节点跳转到对应概念页。</p>",
                  '<div id="graph-container" style="height:520px;border:1px solid var(--border);border-radius:10px;background:var(--panel)"></div>',
                  '<p class="sub">红线 = 必学前置 · 灰线 = 建议先看 · 蓝线 = 拓展阅读</p>']
    data["pages"]["__graph__"] = {"html": "".join(graph_html), "kind": "graph", "title": "知识图谱"}

    # ---- 测验页 ----
    quizzes_by_chapter = {}
    for q in manifest.get("quizzes", []):
        quizzes_by_chapter.setdefault(q.get("chapterId", "__all__"), []).append(q)
    quiz_pages = {}
    for cid, qs in quizzes_by_chapter.items():
        qh = ["<h1>测验" + (f"：{_escape(manifest_ch_title(manifest, cid))}" if cid != "__all__" else "（综合）") + "</h1>"]
        for idx, q in enumerate(qs, 1):
            qh.append(_render_quiz(q, idx))
        qh.append("<p class='quiz-summary'>完成作答后点击「检查答案」查看得分与解析。</p>")
        quiz_pages[cid] = "".join(qh)
    data["pages"]["__quiz_all__"] = {"html": "".join(
        _render_quiz(q, i) for i, q in enumerate(manifest.get("quizzes", []), 1)
        if q.get("chapterId") == "__all__") or "<p>（无综合题）</p>", "kind": "quiz", "title": "综合测验"}
    for cid, html_text in quiz_pages.items():
        if cid != "__all__":
            data["pages"][f"__quiz_{cid}__"] = {"html": html_text, "kind": "quiz", "title": "测验"}

    # ---- 抽认卡页 ----
    cards_html = ["<h1>抽认卡</h1>",
                  "<p>点击卡片翻面；判断「认识 / 不熟」以记录复习状态。</p>",
                  "<div class='card-controls'><label>按章节筛选：<select id='card-filter'><option value=''>全部</option></select></label>"
                  "<span class='card-counts'>认识 <b id='card-known'>0</b> · 不熟 <b id='card-again'>0</b> · 剩余 <b id='card-left'>0</b></span></div>",
                  "<div id='card-stage'><div class='flashcard' id='flashcard'><div class='fc-inner'><div class='fc-front'></div><div class='fc-back'></div></div></div></div>",
                  "<div class='card-actions'><button id='card-again-btn'>不熟</button><button id='card-known-btn'>认识</button></div>"]
    data["pages"]["__cards__"] = {"html": "".join(cards_html), "kind": "cards", "title": "抽认卡"}

    # ---- 术语表页 ----
    glossary_html = ["<h1>术语表</h1>", "<input id='glossary-filter' type='search' placeholder='筛选术语…'>", "<ul id='glossary-list'>"]
    for g in manifest.get("glossary", []):
        ch_ref = ""
        if g.get("chapterId"):
            ch_ref = (f" <span class=glossary-ref>（"
                      f"{_escape(manifest_ch_title(manifest, g.get('chapterId')))}）</span>")
        glossary_html.append(
            f"<li data-term='{_escape(g.get('term', '').lower())}'>{_escape(g.get('term', ''))} — "
            f"{_escape(g.get('def', ''))}{ch_ref}</li>")
    glossary_html.append("</ul>")
    data["pages"]["__glossary__"] = {"html": "".join(glossary_html), "kind": "glossary", "title": "术语表"}

    # ---- 诊断页（P3 核心）----
    data["pages"]["__diagnosis__"] = {"html": _render_diagnosis_page(manifest), "kind": "diagnosis", "title": "诊断测试"}

    # ---- 模式库 / 速查表 ----
    for key, label, pid in (("patterns", "模式库", "__patterns__"), ("cheatsheet", "速查表", "__cheatsheet__")):
        f = (manifest.get(key) or {}).get("file")
        if f:
            fp = os.path.join(data["base_dir"], f)
            if os.path.exists(fp):
                with open(fp, "r", encoding="utf-8") as fh:
                    data["pages"][pid] = {"html": md_to_html(fh.read()), "kind": label, "title": label}

    # ---- 给章节和概念页注入出处和深度片段 ----
    for ch in manifest.get("chapters", []):
        pid = ch["id"]
        if pid in pages:
            badge = _source_badge(ch.get("source"))
            prereq_links = _prereq_links(manifest, ch.get("prerequisites", []), "chapter")
            pages[pid]["html"] = badge + prereq_links + pages[pid]["html"]
    for c in manifest.get("concepts", []):
        pid = c["id"]
        if pid in pages:
            badge = _source_badge(c.get("source"))
            prereq_links = _prereq_links(manifest, c.get("prerequisites", []), "concept")
            depth = _depth_fragment_html(data, c)
            pages[pid]["html"] = badge + prereq_links + pages[pid]["html"] + depth

    # ---- 侧边栏导航 ----
    nav = [{"label": "学习路径", "href": "#/path"},
           {"label": "🕸 知识图谱", "href": "#/graph"},
           {"label": "🩺 诊断测试", "href": "#/diagnosis"}]
    nav.append({"label": "章节", "children": [
        {"label": c.get("title", c.get("id")), "href": f"#/chapter/{c['id']}"} for c in manifest.get("chapters", [])]})
    if manifest.get("concepts"):
        nav.append({"label": "概念", "children": [
            {"label": c.get("title", c.get("id")), "href": f"#/concept/{c['id']}"} for c in manifest["concepts"]]})
    quiz_children = [{"label": "综合测验", "href": "#/quiz/all"}]
    quiz_children += [{"label": f"测验：{c.get('title', c.get('id'))}", "href": f"#/quiz/{c['id']}"}
                      for c in manifest.get("chapters", [])]
    nav.append({"label": "测验", "children": quiz_children})
    nav.append({"label": "抽认卡", "href": "#/cards"})
    nav.append({"label": "术语表", "href": "#/glossary"})
    if "__patterns__" in data["pages"]:
        nav.append({"label": "模式库", "href": "#/patterns"})
    if "__cheatsheet__" in data["pages"]:
        nav.append({"label": "速查表", "href": "#/cheatsheet"})

    data["nav"] = nav
    data["rendered"] = {pid: p["html"] for pid, p in pages.items()}

    html_str = _SHELL
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    html_str = html_str.replace("__TITLE__", _escape(manifest.get("title", "知枢学习伴侣")))
    html_str = html_str.replace("__SUBTITLE__", _escape(manifest.get("subtitle", "")))
    html_str = html_str.replace("__DATA_JSON__", payload)
    html_str = html_str.replace("__SYN_GROUPS__", json.dumps(_load_synonyms(data.get("base_dir")), ensure_ascii=False).replace("</", "<\\/"))
    return html_str


def _prereq_links(manifest, prereqs, kind):
    """渲染前置知识链接条。prereqs 支持两种格式：
    - 字符串数组 ["c01","ch02"]（旧格式，全当 hard）
    - 对象数组 [{"id":"c01","type":"hard|soft|recommended"}]
    """
    if not prereqs:
        return ""
    links = []
    for item in prereqs:
        if isinstance(item, str):
            pid, ptype = item, "hard"
        else:
            pid = item.get("id", "")
            ptype = item.get("type", "hard")
        cls = {"hard": "prereq-hard", "soft": "prereq-soft", "recommended": "prereq-rec"}.get(ptype, "prereq-hard")
        label = ""
        href = ""
        if kind == "chapter":
            label = manifest_ch_title(manifest, pid)
            href = f"#/chapter/{pid}"
        else:
            for c in manifest.get("concepts", []):
                if c["id"] == pid:
                    label = c.get("title", pid)
                    href = f"#/concept/{pid}"
                    break
        if not label:
            continue
        tag = {"hard": "必", "soft": "荐", "recommended": "拓"}.get(ptype, "必")
        links.append(f'<span class="{cls}"><span class="prereq-tag">{tag}</span> <a href="{href}">{_escape(label)}</a></span>')
    if not links:
        return ""
    return f'<div class="prereq-bar">⬅ 前置：{" · ".join(links)}</div>'


def _render_quiz(q, idx):
    qtype = q.get("type", "single")
    qid = q.get("id", f"q{idx}")
    opts = q.get("options") or []
    question = _inline(_escape(q.get("question", "")))
    # 关联的概念 id（用于答错时倒推）
    related = q.get("relatedConceptId", "")
    related_ch = q.get("chapterId", "")
    # 每个选项可标注对应误解 id（single 类型）
    opt_mis = q.get("optionMisconceptions", [])
    parts = [f"<div class='quiz-item' data-qid='{qid}' data-type='{qtype}' "
             f"data-concept='{_escape(related)}' data-chapter='{_escape(related_ch)}'>",
             f"<p class='quiz-q'><b>Q{idx}.</b> {question}</p>"]
    if qtype in ("single", "multi"):
        input_type = "radio" if qtype == "single" else "checkbox"
        parts.append("<div class='quiz-opts'>")
        for oi, o in enumerate(opts):
            mis_id = opt_mis[oi] if oi < len(opt_mis) else ""
            mis_attr = f' data-misconception="{_escape(mis_id)}"' if mis_id else ""
            parts.append(
                f"<label class='quiz-opt'><input type='{input_type}' name='{qid}' value='{oi}'{mis_attr}> "
                f"{_inline(_escape(str(o)))}</label>")
        parts.append("</div>")
    elif qtype == "blank":
        parts.append(f"<input class='quiz-blank' type='text' placeholder='填写答案'>")
    parts.append("<div class='quiz-actions'><button class='quiz-check'>检查答案</button>"
                 "<span class='quiz-feedback'></span></div>")
    parts.append("</div>")
    return "".join(parts)


def _render_diagnosis_page(manifest):
    """诊断页：展示一组诊断题，答错时给出倒推建议。"""
    qs = manifest.get("quizzes", [])
    if not qs:
        return "<h1>诊断测试</h1><p class='empty'>本书暂无测验题，无法诊断。</p>"
    h = ["<h1>🩺 诊断测试</h1>",
         "<p>系统会从全书中抽题。答错的题会自动沿知识依赖链回溯，告诉你真正需要补的前置知识点。</p>",
         "<div class='diag-controls'>",
         "<button id='diag-start'>开始诊断（随机抽 5 题）</button>",
         "<span id='diag-progress'></span>",
         "</div>",
         "<div id='diag-stage'></div>",
         "<div id='diag-result'></div>"]
    return "".join(h)


# ----------------------------------------------------------------------------
# HTML 外壳（内嵌 CSS/JS，无外部依赖；KaTeX/mermaid 联网加载）
# ----------------------------------------------------------------------------

_SHELL = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="icon" href="data:,">
<title>__TITLE__</title>
<link rel="stylesheet" href="https://registry.npmmirror.com/katex/0.16.9/files/dist/katex.min.css">
<link rel="stylesheet" href="https://registry.npmmirror.com/picocss/2.0.6/dist/css/pico.min.css">
<link rel="stylesheet" href="https://registry.npmmirror.com/vis-network/9.1.9/dist/dist/vis-network.min.css">
<style>
:root{
  --bg:#f7f7f8; --panel:#ffffff; --text:#1f2328; --muted:#6b7280;
  --accent:#2563eb; --accent-soft:#dbeafe; --border:#e5e7eb;
  --ok:#16a34a; --bad:#dc2626; --code-bg:#f3f4f6;
  --depth-bg:#fef9c3; --depth-border:#ca8a04;
}
[data-theme="dark"]{
  --bg:#111318; --panel:#1a1d24; --text:#e5e7eb; --muted:#9ca3af;
  --accent:#60a5fa; --accent-soft:#1e3a5f; --border:#2d333d;
  --ok:#4ade80; --bad:#f87171; --code-bg:#20242c;
  --depth-bg:#2a2410; --depth-border:#a16207;
}
*{box-sizing:border-box}
html,body{margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;
  background:var(--bg);color:var(--text);line-height:1.7;font-size:15px}
a{color:var(--accent);text-decoration:none}
a:hover{text-decoration:underline}
.layout{display:flex;min-height:100vh}
.sidebar{width:290px;flex:none;background:var(--panel);border-right:1px solid var(--border);
  padding:14px;position:sticky;top:0;height:100vh;overflow-y:auto}
.sidebar h1{font-size:17px;margin:2px 0 2px}
.sidebar .sub{font-size:12px;color:var(--muted);margin-bottom:10px}
#q{width:100%;padding:7px 10px;border:1px solid var(--border);border-radius:8px;background:var(--bg);color:var(--text);margin-bottom:10px}
.nav-sec{font-size:12px;color:var(--muted);margin:12px 0 4px;text-transform:uppercase;letter-spacing:.4px}
.nav-item{display:block;padding:5px 10px;border-radius:6px;color:var(--text);font-size:14px}
.nav-item:hover{background:var(--accent-soft);text-decoration:none}
.nav-item.active{background:var(--accent-soft);color:var(--accent);font-weight:600}
.nav-item .done{float:right;color:var(--ok);font-size:12px}
#nav-toggle{display:none}
.main{flex:1;min-width:0;padding:28px 40px 80px;max-width:920px;margin:0 auto}
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
.page blockquote blockquote{border-color:var(--muted)}
.page img{max-width:100%}
.mermaid{background:var(--code-bg);padding:14px;border-radius:8px;overflow-x:auto;font-family:ui-monospace,Menlo,Consolas,monospace;font-size:12.5px;white-space:pre;color:var(--muted)}
.mermaid-hint{font-size:12px;color:var(--muted);margin:4px 0 14px}
svg{max-width:100%;height:auto}
/* 出处脚注 */
.source-badge{font-size:12px;color:var(--muted);background:var(--code-bg);padding:4px 10px;border-radius:6px;margin:0 0 12px;display:inline-block}
/* 前置知识条 */
.prereq-bar{font-size:13px;color:var(--muted);border-left:3px solid var(--accent);padding:4px 10px;margin:0 0 12px;background:var(--accent-soft)}
.prereq-hard a{color:var(--bad);font-weight:600}
.prereq-soft a{color:var(--muted)}
.prereq-rec a{color:var(--accent)}
.prereq-tag{display:inline-block;font-size:10px;padding:0 4px;border-radius:3px;margin-right:2px;vertical-align:middle}
.prereq-hard .prereq-tag{background:var(--bad);color:#fff}
.prereq-soft .prereq-tag{background:var(--muted);color:#fff}
.prereq-rec .prereq-tag{background:var(--accent);color:#fff}
/* 误解卡片 */
.misconception-card{margin-top:10px;padding:10px 14px;border-left:4px solid var(--bad);background:#fef2f2;border-radius:0 8px 8px 0;font-size:13px}
.misconception-card b{color:var(--bad)}
[data-theme="dark"] .misconception-card{background:#2a1215}
/* 掌握度条 */
.mastery-bar{height:6px;background:var(--border);border-radius:3px;overflow:hidden;margin:4px 0}
.mastery-bar>div{height:100%;background:var(--ok);transition:width .3s}
.mastery-label{font-size:11px;color:var(--muted)}
/* 深度推导片段 */
.depth-fragment{margin:18px 0;border:1px solid var(--depth-border);border-radius:10px;background:var(--depth-bg);overflow:hidden}
.depth-fragment>summary{padding:10px 14px;cursor:pointer;font-weight:600;font-size:14px;list-style:none}
.depth-fragment>summary:hover{filter:brightness(.95)}
.depth-body{padding:14px 18px;border-top:1px dashed var(--depth-border);background:var(--panel)}
.depth-missing{color:var(--bad);font-size:13px;padding:8px;background:var(--code-bg);border-radius:6px}
/* KaTeX */
.katex-inline{font-size:1.05em}
.katex-block{overflow-x:auto;padding:8px 0;text-align:center}
.katex-block .katex{font-size:1.1em}
/* 测验 */
.quiz-item{border:1px solid var(--border);border-radius:10px;padding:14px 16px;margin:14px 0;background:var(--panel)}
.quiz-q{margin:0 0 8px;font-weight:500}
.quiz-opts label{display:block;padding:4px 0;cursor:pointer}
.quiz-blank{width:60%;padding:6px 10px;border:1px solid var(--border);border-radius:6px;background:var(--bg);color:var(--text)}
.quiz-check{margin-top:10px;padding:6px 16px;border:none;border-radius:6px;background:var(--accent);color:#fff;cursor:pointer}
.quiz-feedback{margin-left:12px;font-size:13px}
.fb-ok{color:var(--ok)}.fb-bad{color:var(--bad)}
.quiz-explain{margin-top:8px;font-size:13px;color:var(--muted);border-top:1px dashed var(--border);padding-top:6px}
.quiz-remedy{margin-top:8px;padding:8px 12px;background:var(--accent-soft);border-radius:6px;font-size:13px}
/* 抽认卡 */
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
.search-hit{margin:6px 0}
.search-group{margin:18px 0}
.grp-head{font-size:13px;font-weight:600;color:var(--muted);border-bottom:1px solid var(--border);padding-bottom:5px;margin-bottom:4px}
.grp-count{margin-left:6px;font-weight:400;opacity:.75}
.syn-note{display:inline-block;margin-left:8px;padding:1px 6px;border-radius:4px;background:var(--accent-soft);color:var(--muted);font-size:12px;vertical-align:middle}
.search-hit mark,.hl{background:#fde68a;color:inherit;padding:0 1px;border-radius:2px}
.hit-hl{background:#fbbf24;color:inherit;border-radius:3px;box-shadow:0 0 0 2px #fde68a}
.hit-flash{animation:hitFlash 1.8s ease-out}
@keyframes hitFlash{from{background:#f59e0b}to{background:#fbbf24}}
[data-theme="dark"] .search-hit mark,[data-theme="dark"] .hl{background:#92400e;color:#fef3c7}
[data-theme="dark"] .hit-hl{background:#b45309;color:#fff;box-shadow:0 0 0 2px #78350f}
.topbar{position:sticky;top:0;background:var(--bg);padding:8px 0;display:flex;justify-content:flex-end;z-index:10}
#theme-btn{border:1px solid var(--border);background:var(--panel);color:var(--text);border-radius:8px;padding:5px 12px;cursor:pointer;white-space:nowrap}
#progress-export,#progress-import{border:1px solid var(--border);background:var(--panel);color:var(--text);border-radius:8px;padding:5px 10px;cursor:pointer;font-size:13px;white-space:nowrap;margin-right:8px}
#progress-bar{height:5px;background:var(--border);border-radius:3px;margin:8px 0;overflow:hidden}
#progress-bar>div{height:100%;width:0;background:var(--accent);transition:width .3s}
.empty{color:var(--muted);padding:20px 0}
/* 诊断 */
.diag-controls{margin:14px 0;padding:14px;background:var(--panel);border-radius:10px;border:1px solid var(--border)}
#diag-start{padding:8px 20px;border:none;border-radius:8px;background:var(--accent);color:#fff;cursor:pointer;font-size:14px}
#diag-progress{margin-left:12px;color:var(--muted);font-size:13px}
#diag-stage .quiz-item{margin:10px 0}
#diag-result{margin-top:16px;padding:14px;background:var(--panel);border-radius:10px;border:1px solid var(--border)}
.diag-remedy-item{padding:10px;margin:8px 0;background:var(--accent-soft);border-radius:8px;font-size:14px}
@media print{.sidebar,.topbar,.quiz-actions,.card-actions,.card-controls,.diag-controls{display:none!important}.main{max-width:none;padding:0}}
@media (max-width:760px){.sidebar{width:100%;height:auto;position:static;padding:10px 14px}
  #nav{display:none;max-height:46vh;overflow-y:auto;overscroll-behavior:contain}.sidebar.open #nav{display:block}
  .nav-item{padding:9px 10px}
  #q,#glossary-filter{font-size:16px}
  .quiz-opts label{padding:8px 0;min-height:30px}
  .quiz-check{padding:10px 18px;min-height:40px}
  #diag-start{min-height:40px}
  .card-actions button{min-height:40px}
  #nav-toggle{display:block;width:100%;padding:8px 10px;margin:4px 0;border:1px solid var(--border);border-radius:8px;background:var(--bg);color:var(--text);font-size:14px;text-align:left;cursor:pointer}
  .layout{flex-direction:column}.main{padding:20px 18px 64px;max-width:none;width:100%}
  .page{overflow-wrap:anywhere}.page table{display:block;overflow-x:auto;max-width:100%}
  .page h1,.page h2,.page h3{line-height:1.35}}
</style>
</head>
<body>
<div class="layout">
  <aside class="sidebar">
    <h1>__TITLE__</h1>
    <div class="sub">__SUBTITLE__</div>
    <div id="progress-bar"><div id="progress-fill"></div></div>
    <div class="sub" id="progress-label">进度 0%</div>
    <input id="q" type="search" placeholder="搜索章节 / 概念 / 术语 / 全文…">
    <nav id="nav"></nav>
  </aside>
  <main class="main">
    <div class="topbar"><button id="progress-export">⬇ 导出进度</button><button id="progress-import">⬆ 导入进度</button><button id="theme-btn">🌙 深色</button><input type="file" id="progress-file" accept="application/json" hidden></div>
    <div id="view" class="page"></div>
  </main>
</div>
<script>
const DATA = __DATA_JSON__;
const pages = DATA.rendered;
const manifest = DATA.manifest;
const SYN_GROUPS = __SYN_GROUPS__;
const $ = s => document.querySelector(s);
const $$ = s => document.querySelectorAll(s);
const esc = s => String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const SLUG = manifest.slug || 'book';
const store = {
  get(k){ try{ return JSON.parse(localStorage.getItem(SLUG+':'+k)||'null') }catch(e){ return null } },
  set(k,v){ try{ localStorage.setItem(SLUG+':'+k, JSON.stringify(v)) }catch(e){} }
};
const ZS_VERSION = '1.4.0';
/* ---------- 进度导出 / 导入（跨设备） ---------- */
function exportProgress(){
  const data = {};
  for(let i=0;i<localStorage.length;i++){
    const k = localStorage.key(i);
    if(k && k.indexOf(SLUG+':')===0) data[k]=localStorage.getItem(k);
  }
  const payload = {app:'zhishu', skillVersion:ZS_VERSION, kind:'companion', exportedAt:new Date().toISOString(), prefix:SLUG+':', data};
  const blob = new Blob([JSON.stringify(payload,null,2)], {type:'application/json'});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = (SLUG||'book')+'-progress-'+new Date().toISOString().slice(0,10)+'.json';
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(()=>URL.revokeObjectURL(a.href), 2000);
}
function importProgress(file){
  const fr = new FileReader();
  fr.onload = () => {
    try{
      const p = JSON.parse(fr.result);
      if(!p || p.app!=='zhishu' || !p.data || typeof p.data!=='object') throw new Error('不是知枢进度文件');
      let n = 0;
      Object.keys(p.data).forEach(k=>{ if(k.indexOf(SLUG+':')===0){ localStorage.setItem(k, p.data[k]); n++; } });
      if(!n){ alert('这个文件里没有属于本书的进度（slug 不一致）'); return; }
      alert('已导入 '+n+' 条进度，页面将刷新'); location.reload();
    }catch(e){ alert('导入失败：'+e.message); }
  };
  fr.readAsText(file);
}
let state = { visited: store.get('visited')||[], quiz: store.get('quiz')||{}, cards: store.get('cards')||{}, mastery: store.get('mastery')||{} };

/* ---------- 导航 ---------- */
function renderNav(){
  const nav = $('#nav'); nav.innerHTML='';
  const build = items => items.forEach(it=>{
    if(it.children){
      const sec=document.createElement('div'); sec.className='nav-sec'; sec.textContent=it.label; nav.appendChild(sec);
      it.children.forEach(c=>{
        const a=document.createElement('a'); a.className='nav-item'; a.href=c.href; a.textContent=c.label;
        const id=routeId(c.href);
        if(state.visited.includes(id)) a.innerHTML = esc(c.label)+' <span class="done">✓</span>';
        nav.appendChild(a);
      });
    }else{
      const a=document.createElement('a'); a.className='nav-item'; a.href=it.href; a.textContent=it.label;
      const id=routeId(it.href);
      if(state.visited.includes(id)) a.innerHTML = esc(it.label)+' <span class="done">✓</span>';
      nav.appendChild(a);
    }
  });
  build(DATA.nav);
  updateProgress();
}
function routeId(href){ return href.replace('#/',''); }

/* ---------- 路由 ---------- */
function routeIdFromHash(){
  let h = location.hash.replace(/^#\//,'');
  if(!h) return 'path';
  if(h==='path') return 'path';
  if(h==='diagnosis') return 'diagnosis';
  const m = h.match(/^(chapter|concept)\/(.+)$/);
  if(m) return m[1]+'/'+m[2];
  return h;
}
function showPage(rid){
  let id;
  if(rid==='path') id='__path__';
  else if(rid==='diagnosis') id='__diagnosis__';
  else if(rid==='graph') id='__graph__';
  else if(rid.startsWith('quiz/')) id='__quiz_'+rid.split('/')[1]+'__';
  else if(rid==='cards') id='__cards__';
  else if(rid==='glossary') id='__glossary__';
  else if(rid==='patterns') id='__patterns__';
  else if(rid==='cheatsheet') id='__cheatsheet__';
  else if(rid.startsWith('chapter/')) id=rid.split('/')[1];
  else if(rid.startsWith('concept/')) id=rid.split('/')[1];
  else id=rid;
  const html = pages[id] || '<div class="empty">页面不存在</div>';
  $('#view').innerHTML = html;
  $$('.nav-item').forEach(a=>a.classList.toggle('active', routeId(a.getAttribute('href'))===rid));
  if(!state.visited.includes(rid) && (rid.startsWith('chapter/')||rid.startsWith('concept/'))){
    state.visited.push(rid); store.set('visited', state.visited); renderNav();
  }
  window.scrollTo(0,0);
  if(rid==='cards') initCards();
  if(rid==='glossary') initGlossary();
  if(rid.startsWith('quiz')) initQuizzes(rid);
  if(rid==='diagnosis') initDiagnosis();
  if(rid==='graph') initGraph();
  if(id==='__path__') updatePath();
  renderMath();
  renderMermaid();
  applyPendingHighlight();
}

/* ---------- KaTeX 渲染（多源回退） ---------- */
let katexLoading = false, katexReady = false;
function renderMath(){
  const hasMath = document.querySelector('.katex-inline, .katex-block');
  if(!hasMath) return;
  if(katexReady){ doRenderMath(); return; }
  if(katexLoading) return;
  katexLoading = true;
  const cssUrls = [
    'https://registry.npmmirror.com/katex/0.16.9/files/dist/katex.min.css',
    'https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css',
    'https://unpkg.com/katex@0.16.9/dist/katex.min.css'
  ];
  const jsUrls = [
    'https://registry.npmmirror.com/katex/0.16.9/files/dist/katex.min.js',
    'https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js',
    'https://unpkg.com/katex@0.16.9/dist/katex.min.js'
  ];
  let ci = 0, ji = 0;
  const tryCss = () => {
    if(ci >= cssUrls.length) return;
    const link = document.createElement('link');
    link.rel = 'stylesheet'; link.href = cssUrls[ci++];
    link.onload = tryJs; link.onerror = () => { link.remove(); tryCss(); };
    document.head.appendChild(link);
  };
  const tryJs = () => {
    if(ji >= jsUrls.length){ katexLoading = false; return; }
    const s = document.createElement('script');
    s.src = jsUrls[ji++];
    s.onload = () => { katexReady = true; katexLoading = false; doRenderMath(); };
    s.onerror = () => { s.remove(); tryJs(); };
    document.head.appendChild(s);
  };
  tryCss();
}
function doRenderMath(){
  if(typeof katex === 'undefined') return;
  // 行内公式：.katex-inline 里的内容
  $$('.katex-inline').forEach(el=>{
    try{ katex.render(el.textContent, el, {throwOnError:false}); }catch(e){}
  });
  // 块级公式：.katex-block 里的内容
  $$('.katex-block').forEach(el=>{
    try{ katex.render(el.textContent, el, {displayMode:true, throwOnError:false}); }catch(e){}
  });
}
// 公式内容预处理：把 < 后跟字母的位置转成 &lt;，避免被 HTML 解析器当标签吃掉
// （这是 first-principles-derivation 踩过的坑：$m<n$ 会变成残留 $m）
function sanitizeMathHTML(){
  $$('.katex-inline, .katex-block').forEach(el=>{
    el.innerHTML = el.innerHTML.replace(/<([a-zA-Z])/g, '&lt;$1');
  });
}

/* ---------- 进度 ---------- */
function updateProgress(){
  const chs = (manifest.chapters||[]).length;
  const done = (manifest.chapters||[]).filter(c=>state.visited.includes('chapter/'+c.id)).length;
  const pct = chs? Math.round(done/chs*100) : 0;
  $('#progress-fill').style.width = pct+'%';
  $('#progress-label').textContent = `进度 ${pct}% · 已学 ${done}/${chs} 章`;
}
function updatePath(){
  $$('.path-step').forEach(el=>{
    const step = el.id.replace('path-','');
    const s = (manifest.learningPath||[]).find(x=>x.step===step);
    if(s && (s.chapterIds||[]).every(c=>state.visited.includes('chapter/'+c))){
      el.classList.add('passed');
      const lbl = el.querySelector('.checkpoint-ok'); if(!lbl){ const sp=document.createElement('span'); sp.className='done'; sp.textContent=' ✓ 已完成'; el.appendChild(sp); }
    }
  });
}

/* ---------- 概念/章节依赖查找（用于诊断倒推） ---------- */
function findConcept(id){ return (manifest.concepts||[]).find(c=>c.id===id); }
function findChapter(id){ return (manifest.chapters||[]).find(c=>c.id===id); }
function getPrereqs(node){
  if(!node) return [];
  return node.prerequisites || node.prereqs || [];
}
/**
 * 答错倒推：从错题关联的概念/章节出发，沿 prerequisites 回溯，
 * 返回一串"你可能需要先补的"节点，带跳转链接。
 */
function traceBack(startConceptId, startChapterId){
  const visited = new Set();
  const chain = [];
  const queue = [];
  if(startConceptId){ const c = findConcept(startConceptId); if(c) queue.push({node:c, kind:'concept'}); }
  if(startChapterId){ const c = findChapter(startChapterId); if(c) queue.push({node:c, kind:'chapter'}); }
  while(queue.length && chain.length < 6){
    const {node, kind} = queue.shift();
    if(visited.has(node.id)) continue;
    visited.add(node.id);
    chain.push({node, kind});
    (getPrereqs(node)||[]).forEach(pid=>{
      const cn = findConcept(pid); if(cn){ queue.push({node:cn, kind:'concept'}); return; }
      const ch = findChapter(pid); if(ch) queue.push({node:ch, kind:'chapter'});
    });
  }
  return chain;
}

/* ---------- 测验（带倒推） ---------- */
function initQuizzes(rid){
  $$('.quiz-item').forEach(item=>{
    const btn = item.querySelector('.quiz-check');
    if(!btn || item.dataset.inited){ return }
    item.dataset.inited='1';
    btn.addEventListener('click', ()=>{
      const qid = item.dataset.qid; const type = item.dataset.type;
      const q = (manifest.quizzes||[]).find(x=>x.id===qid); if(!q) return;
      let user, correct=false, fb;
      if(type==='single'){
        const sel = item.querySelector('input:checked');
        user = sel? parseInt(sel.value) : null;
        correct = user===q.answer;
        fb = correct?'✓ 正确':'✗ 错误'+(user==null?'（未作答）':'');
      } else if(type==='multi'){
        user = Array.from(item.querySelectorAll('input:checked')).map(i=>parseInt(i.value)).sort();
        const ans = Array.isArray(q.answer)? q.answer.slice().sort(): [q.answer];
        correct = user.length>0 && JSON.stringify(user)===JSON.stringify(ans);
        fb = correct?'✓ 正确':'✗ 错误';
      } else if(type==='blank'){
        const v = (item.querySelector('.quiz-blank').value||'').trim().toLowerCase();
        const a = String(q.answer).trim().toLowerCase();
        correct = v===a;
        fb = correct?'✓ 正确':'✗ 错误'+(v?'':'（未作答）');
      }
      item.querySelectorAll('input:checked').forEach(i=>{
        const val=parseInt(i.value);
        i.parentElement.style.color = (Array.isArray(q.answer)? q.answer.includes(val) : val===q.answer) ? 'var(--ok)' : 'var(--bad)';
      });
      const feed = item.querySelector('.quiz-feedback');
      feed.className = 'quiz-feedback '+(correct?'fb-ok':'fb-bad');
      feed.textContent = fb;
      let ex = item.querySelector('.quiz-explain');
      if(!ex){ ex=document.createElement('div'); ex.className='quiz-explain'; item.appendChild(ex); }
      ex.innerHTML = '解析：' + esc(q.explain||'');
      // 答错时：倒推前置 + 误解卡片 + 掌握度更新
      if(!correct){
        let remedy = item.querySelector('.quiz-remedy');
        if(!remedy){ remedy = document.createElement('div'); remedy.className='quiz-remedy'; item.appendChild(remedy); }
        const chain = traceBack(item.dataset.concept, item.dataset.chapter);
        if(chain.length > 1){
          const links = chain.slice(1).map(({node,kind})=>{
            const href = kind==='concept' ? `#/concept/${node.id}` : `#/chapter/${node.id}`;
            return `<a href="${href}">${esc(node.title||node.id)}</a>`;
          }).join(' → ');
          remedy.innerHTML = '🔍 可能的根因（沿依赖链回溯）：' + links;
        }
        // 误解卡片：如果选错的选项标注了 misconceptionId
        const checked = item.querySelector('input:checked');
        const misId = checked ? checked.dataset.misconception : '';
        if(misId){
          const mis = (manifest.misconceptions||[]).find(m=>m.id===misId);
          if(mis){
            let misCard = item.querySelector('.misconception-card');
            if(!misCard){ misCard = document.createElement('div'); misCard.className='misconception-card'; item.appendChild(misCard); }
            misCard.innerHTML = `<b>⚠ 常见误解</b><br>你选了「${esc(mis.wrong)}」——${esc(mis.correction)}`;
          }
        }
        // 掌握度下降
        updateMastery(item.dataset.concept, -0.15);
      } else {
        updateMastery(item.dataset.concept, +0.15);
      }
      const ch = q.chapterId||'__all__';
      if(!state.quiz[ch]) state.quiz[ch]={done:0,total:0};
      state.quiz[ch].done = Math.min(state.quiz[ch].total+1, state.quiz[ch].done+1);
      state.quiz[ch].total += 1;
      store.set('quiz', state.quiz);
    });
  });
}

/* ---------- 知识图谱（vis-network） ---------- */
let networkLoaded = false;
function loadVisNetwork(cb){
  if(networkLoaded){ cb(); return; }
  const urls = [
    'https://registry.npmmirror.com/vis-network/9.1.9/dist/dist/vis-network.min.js',
    'https://cdn.jsdelivr.net/npm/vis-network@9.1.9/standalone/umd/vis-network.min.js',
    'https://unpkg.com/vis-network@9.1.9/standalone/umd/vis-network.min.js'
  ];
  let i = 0;
  const tryNext = () => {
    if(i >= urls.length) return;
    const s = document.createElement('script');
    s.src = urls[i++];
    s.onload = () => { networkLoaded = true; cb(); };
    s.onerror = () => { s.remove(); tryNext(); };
    document.head.appendChild(s);
  };
  tryNext();
}
function initGraph(){
  const container = document.getElementById('graph-container');
  if(!container) return;
  loadVisNetwork(() => {
    if(typeof vis === 'undefined'){ container.innerHTML = '<p class="empty">图谱库加载失败，请联网后刷新</p>'; return; }
    const concepts = manifest.concepts || [];
    const chapters = manifest.chapters || [];
    const nodes = [];
    const edges = [];
    concepts.forEach(c => {
      const mastery = Math.round(getMastery(c.id)*100);
      nodes.push({
        id: 'c_' + c.id,
        label: c.title || c.id,
        title: (c.title||c.id) + '（掌握度 ' + mastery + '%）',
        color: mastery > 70 ? '#86efac' : mastery > 40 ? '#fde68a' : '#fca5a5',
        shape: 'dot',
        size: mastery > 70 ? 20 : 14,
        font: { size: 13 }
      });
    });
    chapters.forEach(ch => {
      nodes.push({
        id: 'ch_' + ch.id,
        label: ch.title || ch.id,
        shape: 'box',
        color: '#93c5fd',
        font: { size: 12 }
      });
    });
    // 前置边
    concepts.forEach(c => {
      (c.prerequisites || []).forEach(p => {
        const pid = typeof p === 'string' ? p : p.id;
        const ptype = typeof p === 'string' ? 'hard' : (p.type || 'hard');
        const from = (pid.startsWith('ch') ? 'ch_' : 'c_') + pid;
        const to = 'c_' + c.id;
        if(nodes.find(n => n.id === from)){
          edges.push({
            from: from, to: to,
            color: { color: ptype === 'hard' ? '#dc2626' : ptype === 'soft' ? '#9ca3af' : '#3b82f6' },
            arrows: 'to',
            width: ptype === 'hard' ? 2 : 1,
            dashes: ptype !== 'hard'
          });
        }
      });
    });
    const data = { nodes: new vis.DataSet(nodes), edges: new vis.DataSet(edges) };
    const options = {
      physics: { stabilization: true, barnesHut: { gravitationalConstant: -3000 } },
      interaction: { hover: true, tooltipDelay: 200 }
    };
    const net = new vis.Network(container, data, options);
    net.on('click', params => {
      if(params.nodes.length > 0){
        const nid = params.nodes[0];
        if(nid.startsWith('c_')) location.hash = '#/concept/' + nid.slice(2);
        else if(nid.startsWith('ch_')) location.hash = '#/chapter/' + nid.slice(3);
      }
    });
  });
}

/* ---------- 诊断模式 ---------- */
let diagQueue = [], diagIdx = 0, diagWrong = [];
function initDiagnosis(){
  const startBtn = $('#diag-start');
  if(!startBtn || startBtn.dataset.inited) return;
  startBtn.dataset.inited='1';
  startBtn.addEventListener('click', ()=>{
    const all = (manifest.quizzes||[]).slice();
    // 随机抽 5 题（不够就全抽）
    for(let i = all.length-1; i>0; i--){ const j = Math.floor(Math.random()*(i+1)); [all[i],all[j]]=[all[j],all[i]]; }
    diagQueue = all.slice(0, Math.min(5, all.length));
    diagIdx = 0; diagWrong = [];
    showDiagQuestion();
  });
}
function showDiagQuestion(){
  const stage = $('#diag-stage');
  const result = $('#diag-result');
  result.innerHTML = '';
  if(diagIdx >= diagQueue.length){ finishDiagnosis(); return; }
  const q = diagQueue[diagIdx];
  $('#diag-progress').textContent = `第 ${diagIdx+1} / ${diagQueue.length} 题`;
  const fakeItem = document.createElement('div');
  fakeItem.innerHTML = _renderQuizHTML(q, diagIdx+1);
  stage.innerHTML = fakeItem.innerHTML;
  // 绑定检查按钮
  const item = stage.querySelector('.quiz-item');
  const btn = item.querySelector('.quiz-check');
  btn.addEventListener('click', ()=>{
    const type = item.dataset.type;
    let user, correct=false;
    if(type==='single'){
      const sel = item.querySelector('input:checked');
      user = sel? parseInt(sel.value) : null;
      correct = user===q.answer;
    } else if(type==='multi'){
      user = Array.from(item.querySelectorAll('input:checked')).map(i=>parseInt(i.value)).sort();
      const ans = Array.isArray(q.answer)? q.answer.slice().sort(): [q.answer];
      correct = user.length>0 && JSON.stringify(user)===JSON.stringify(ans);
    } else if(type==='blank'){
      const v = (item.querySelector('.quiz-blank').value||'').trim().toLowerCase();
      correct = v===String(q.answer).trim().toLowerCase();
    }
    if(!correct){
      diagWrong.push(q);
      const chain = traceBack(q.relatedConceptId, q.chapterId);
      if(chain.length > 1){
        const links = chain.slice(1).map(({node,kind})=>{
          const href = kind==='concept' ? `#/concept/${node.id}` : `#/chapter/${node.id}`;
          return `<div class="diag-remedy-item">建议先学：<a href="${href}">${esc(node.title||node.id)}</a></div>`;
        }).join('');
        $('#diag-result').innerHTML = '<h3>这道题答错了，可能的根因：</h3>' + links +
          '<p><button id="diag-next" class="quiz-check">下一题 →</button></p>';
      } else {
        $('#diag-result').innerHTML = '<p><button id="diag-next" class="quiz-check">下一题 →</button></p>';
      }
    } else {
      $('#diag-result').innerHTML = '<p>✓ 正确。<button id="diag-next" class="quiz-check">下一题 →</button></p>';
    }
    $('#diag-next').addEventListener('click', ()=>{ diagIdx++; showDiagQuestion(); });
  });
}
function _renderQuizHTML(q, idx){
  // 复用服务端渲染的 quiz HTML 结构
  const qtype = q.type||'single';
  const qid = q.id||('diag'+idx);
  let html = `<div class='quiz-item' data-qid='${qid}' data-type='${qtype}' data-concept='${esc(q.relatedConceptId||"")}' data-chapter='${esc(q.chapterId||"")}'>`;
  html += `<p class='quiz-q'><b>Q${idx}.</b> ${esc(q.question||"")}</p>`;
  if(qtype==='single'||qtype==='multi'){
    const it = qtype==='single'?'radio':'checkbox';
    html += "<div class='quiz-opts'>";
    (q.options||[]).forEach((o,i)=>{ html += `<label class='quiz-opt'><input type='${it}' name='${qid}' value='${i}'> ${esc(String(o))}</label>`; });
    html += '</div>';
  } else {
    html += `<input class='quiz-blank' type='text' placeholder='填写答案'>`;
  }
  html += `<div class='quiz-actions'><button class='quiz-check'>检查答案</button><span class='quiz-feedback'></span></div></div>`;
  return html;
}
function finishDiagnosis(){
  const total = diagQueue.length;
  const wrong = diagWrong.length;
  const right = total - wrong;
  let html = `<h2>诊断完成：${right}/${total} 正确</h2>`;
  if(wrong === 0){
    html += '<p>🎉 这组题全对，可以继续往下学。</p>';
  } else {
    html += `<p>有 ${wrong} 道题答错。下面是按依赖链回溯的补强建议：</p>`;
    const seen = new Set();
    diagWrong.forEach(q=>{
      const chain = traceBack(q.relatedConceptId, q.chapterId);
      chain.slice(1).forEach(({node,kind})=>{
        if(seen.has(node.id)) return;
        seen.add(node.id);
        const href = kind==='concept' ? `#/concept/${node.id}` : `#/chapter/${node.id}`;
        html += `<div class="diag-remedy-item">📚 <a href="${href}">${esc(node.title||node.id)}</a></div>`;
      });
    });
  }
  html += '<p><button id="diag-restart" class="quiz-check">重新诊断</button></p>';
  $('#diag-stage').innerHTML = '';
  $('#diag-progress').textContent = '';
  $('#diag-result').innerHTML = html;
  $('#diag-restart').addEventListener('click', ()=>{
    $('#diag-start').click();
  });
}

/* ---------- 掌握度（简化 BKT） ---------- */
function getMastery(cid){
  if(!cid) return 0.5;
  const m = (state.mastery||{})[cid];
  return m !== undefined ? m : 0.3;
}
function updateMastery(cid, delta){
  if(!cid) return;
  if(!state.mastery) state.mastery = {};
  const cur = state.mastery[cid] !== undefined ? state.mastery[cid] : 0.3;
  state.mastery[cid] = Math.max(0, Math.min(1, cur + delta));
  store.set('mastery', state.mastery);
}
function masteryBar(cid){
  const v = Math.round(getMastery(cid)*100);
  return `<div class="mastery-bar"><div style="width:${v}%"></div></div><span class="mastery-label">掌握度 ${v}%</span>`;
}

/* ---------- 抽认卡 ---------- */
let cardIdx = 0, cardList = [];
function initCards(){
  const cards = manifest.flashcards||[];
  cardList = cards.slice();
  cardIdx = 0;
  const sel = $('#card-filter');
  sel.innerHTML = '<option value="">全部</option>';
  [...new Set(cards.map(c=>c.chapterId).filter(Boolean))].forEach(c=>{
    const o=document.createElement('option'); o.value=c; o.textContent=manifestChTitle(c); sel.appendChild(o);
  });
  sel.onchange = ()=>{ const v=sel.value; cardList = v? cards.filter(c=>c.chapterId===v): cards.slice(); cardIdx=0; showCard(); };
  $('#flashcard').onclick = ()=>$('#flashcard').classList.toggle('flip');
  $('#card-known-btn').onclick = ()=>{ markCard(true); };
  $('#card-again-btn').onclick = ()=>{ markCard(false); };
  showCard();
}
function showCard(){
  updateCardCounts();
  if(cardIdx>=cardList.length){ $('#card-stage').innerHTML='<div class="empty">本组卡片已全部复习完 🎉</div>'; return; }
  const c = cardList[cardIdx];
  document.querySelector('.fc-front').textContent = c.front;
  document.querySelector('.fc-back').textContent = c.back;
  $('#flashcard').classList.remove('flip');
}
function markCard(known){
  const c = cardList[cardIdx]; if(!c) return;
  state.cards[c.id] = known?'known':'again';
  store.set('cards', state.cards);
  cardIdx++; showCard();
}
function updateCardCounts(){
  const known = Object.values(state.cards).filter(v=>v==='known').length;
  const again = Object.values(state.cards).filter(v=>v==='again').length;
  $('#card-known').textContent = known;
  $('#card-again').textContent = again;
  $('#card-left').textContent = Math.max(0, cardList.length-cardIdx);
}
function manifestChTitle(id){
  const c=(manifest.chapters||[]).find(x=>x.id===id); return c? c.title : id;
}

/* ---------- 术语表 ---------- */
function initGlossary(){
  const input = $('#glossary-filter');
  if(!input || input.dataset.inited) return;
  input.dataset.inited='1';
  input.oninput = ()=>{
    const v = input.value.trim().toLowerCase();
    $$('#glossary-list li').forEach(li=>{
      li.style.display = (!v || li.dataset.term.includes(v)) ? '' : 'none';
    });
  };
}

/* ---------- 搜索 v2：分词 + 多词 + 命中定位 ---------- */
let searchIndex = null;
let pendingHl = [];
function hlEscRe(s){ return s.replace(/[.*+?^${}()|[\]\\]/g,'\\$&'); }
function tokenizeQuery(q){
  q = String(q||'').trim().toLowerCase();
  if(!q) return [];
  const STOP = new Set(['的','了','是','在','和','与','我','你','他','它','这','那','有','就','都','而','及','或',
                        '吗','呢','吧','把','被','对','从','到','为','上','下','里','中','个','一',
                        '什么','怎么','为什么','如何','哪些','这个','那个']);
  const raw = q.split(/[^\p{L}\p{N}]+/u).filter(Boolean);
  const out = [];
  for(const w of raw){
    if(STOP.has(w)) continue;
    if(/^\p{Script=Han}+$/u.test(w) && w.length > 2){
      out.push(w);
      for(let i=0;i+2<=w.length;i++) out.push(w.slice(i,i+2));
    } else out.push(w);
  }
  return [...new Set(out)].slice(0,12);
}
function hlSnippet(text, terms){
  const low = text.toLowerCase();
  let pos = -1, hit = '';
  for(const t of terms){ const i = low.indexOf(t); if(i>=0 && (pos<0 || i<pos)){ pos=i; hit=t; } }
  const start = Math.max(0, (pos<0?0:pos) - 60);
  const end = Math.min(text.length, (pos<0?0:pos) + 140);
  let s = esc(text.slice(start,end));
  let budget = 6;                                 // 每段最多标 6 处，避免常见词把片段糊满
  terms.forEach(t=>{
    if(t.length < 1 || budget <= 0) return;
    s = s.replace(new RegExp(hlEscRe(t),'gi'), m=>{
      if(budget <= 0) return m;
      budget--;
      return '<mark class="hl">' + m + '</mark>';
    });
  });
  return '…' + s + '…';
}
function applyPendingHighlight(){
  const terms = pendingHl.slice(); pendingHl = [];
  if(!terms.length) return;
  const root = $('#view'); if(!root) return;
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, null);
  let node, first = null, idx = -1, term = '';
  while((node = walker.nextNode())){
    if(!node.nodeValue || !node.nodeValue.trim()) continue;
    const low = node.nodeValue.toLowerCase();
    for(const t of terms){
      const i = low.indexOf(t);
      if(i>=0 && (first===null || i<idx || (i===idx && t.length>term.length))){
        first = node; idx = i; term = t;
      }
    }
  }
  if(!first) return;
  try{
    const i = first.nodeValue.toLowerCase().indexOf(term);
    if(i<0) return;
    const range = document.createRange();
    range.setStart(first, i); range.setEnd(first, i+term.length);
    const mark = document.createElement('mark');
    mark.className = 'hit-hl';
    range.surroundContents(mark);
    mark.scrollIntoView({block:'center'});
    mark.classList.add('hit-flash');
    setTimeout(()=>mark.classList.remove('hit-flash'), 1800);
  }catch(e){}
}
document.addEventListener('click', (e)=>{
  const a = (e.target && e.target.closest) ? e.target.closest('.search-hit a') : null;
  if(a && a.dataset.hl) pendingHl = tokenizeQuery(a.dataset.hl);
});
function searchHref(id){
  const map = {'__path__':'#/path','__diagnosis__':'#/diagnosis','__graph__':'#/graph',
               '__cards__':'#/cards','__glossary__':'#/glossary','__patterns__':'#/patterns',
               '__cheatsheet__':'#/cheatsheet'};
  if(map[id]) return map[id];
  if(id.startsWith('__quiz_')) return '#/quiz/'+id.replace('__quiz_','').replace(/__$/,'');
  if(id.startsWith('__')) return '';
  return '#/'+id;
}
function searchLabel(id){
  if((manifest.chapters||[]).some(c=>c.id===id)) return '章节：'+id;
  if((manifest.concepts||[]).some(c=>c.id===id)) return '概念：'+id;
  const map = {'__path__':'学习路径','__diagnosis__':'诊断测试','__graph__':'知识图谱','__cards__':'抽认卡',
               '__glossary__':'术语表','__patterns__':'模式库','__cheatsheet__':'速查表'};
  if(map[id]) return map[id];
  if(id.startsWith('__quiz_')) return '测验';
  return id;
}
function pageTitle(id){
  const ch = (manifest.chapters||[]).find(c=>c.id===id);
  if(ch) return ch.title || id;
  const cp = (manifest.concepts||[]).find(c=>c.id===id);
  if(cp) return cp.title || id;
  const map = {'__path__':'学习路径','__diagnosis__':'诊断测试','__graph__':'知识图谱','__cards__':'抽认卡',
               '__glossary__':'术语表','__patterns__':'模式库','__cheatsheet__':'速查表'};
  if(map[id]) return map[id];
  if(id.startsWith('__quiz_')){
    const q = (manifest.quizzes||[]).find(x=>'__quiz_'+x.id===id);
    return q ? '测验 · '+String(q.question||'').slice(0,14) : '测验';
  }
  return id;
}
function chapOf(id){
  const chs = manifest.chapters || [];
  const ci = chs.findIndex(c=>c.id===id);
  if(ci >= 0) return {key:'ch:'+id, label:chs[ci].title||id, order:ci};
  const cp = (manifest.concepts||[]).find(c=>c.id===id);
  if(cp){
    const chId = (cp.chapterIds||[])[0];
    const i = chs.findIndex(c=>c.id===chId);
    if(i >= 0) return {key:'ch:'+chId, label:chs[i].title||chId, order:i};
    return {key:'zz', label:'未归入章节', order:900};
  }
  return {key:'tools', label:'术语与工具页', order:950, ref:true};
}
function buildSearchIndex(){
  if(searchIndex) return searchIndex;
  searchIndex = [];
  Object.entries(pages).forEach(([id, htmlText])=>{
    const href = searchHref(id);
    if(!href) return;
    const text = htmlText.replace(/<[^>]+>/g,' ').replace(/\s+/g,' ');
    searchIndex.push({id, href, text, label:pageTitle(id), chap:chapOf(id)});
  });
  return searchIndex;
}
function synOf(t){
  const out = [];
  for(const g of SYN_GROUPS){ if(g.indexOf(t) >= 0){ for(const x of g){ if(x !== t) out.push(x); } } }
  return out.slice(0,6);
}
$('#q').addEventListener('input', e=>{
  const v = e.target.value.trim();
  if(!v){ showPage(routeIdFromHash()); return; }
  const terms = tokenizeQuery(v);
  if(!terms.length){ showPage(routeIdFromHash()); return; }
  const grams = [];
  terms.forEach(t=>{ if(t.length >= 2){ for(let i=0;i+2<=t.length;i++) grams.push(t.slice(i,i+2)); } });
  const qGrams = [...new Set(grams)].slice(0,16);
  const snippetTerms = terms.concat(...terms.map(synOf)).slice(0,24);
  const hits = [];
  buildSearchIndex().forEach(p=>{
    const low = p.text.toLowerCase();
    let tHit = 0, sHit = 0, gHit = 0, first = '', viaSyn = '';
    for(const t of terms){
      if(low.includes(t)){ tHit++; if(!first) first = t; continue; }
      for(const s of synOf(t)){
        if(low.includes(s)){ sHit++; if(!viaSyn) viaSyn = s; if(!first) first = s; break; }
      }
    }
    for(const gm of qGrams){ if(low.includes(gm)) gHit++; }
    if(tHit > 0 || sHit > 0 || gHit >= 4){
      hits.push({p, score: tHit*100 + sHit*30 + Math.min(gHit,20), first, viaSyn});
    }
  });
  hits.sort((a,b)=> b.score-a.score || a.p.text.length-b.p.text.length);
  const top = hits.slice(0,20);
  let body;
  if(top.length){
    const gs = {};
    top.forEach(h=>{
      const k = h.p.chap.key;
      (gs[k] = gs[k] || {label:h.p.chap.label, order:h.p.chap.order, ref:!!h.p.chap.ref, hits:[]}).hits.push(h);
    });
    const eff = g => Math.max(...g.hits.map(x=>x.score)) * (g.ref ? 0.55 : 1);
    const order = Object.values(gs).sort((a,b)=> eff(b)-eff(a));
    body = order.map(g=>{
      const inner = g.hits.sort((a,b)=> b.score-a.score).map(h=>
        `<div class="search-hit"><a href="${h.p.href}" data-hl="${esc(h.first)}">${esc(h.p.label)}</a>${h.viaSyn?`<span class="syn-note">同义命中：${esc(h.viaSyn)}</span>`:''}<br><span class="sub">${hlSnippet(h.p.text, snippetTerms)}</span></div>`).join('');
      return `<div class="search-group"><div class="grp-head">${esc(g.label)}<span class="grp-count">${g.hits.length}</span></div>${inner}</div>`;
    }).join('');
  } else {
    body = '<div class="empty">未找到相关内容，试试章节名 / 概念名 / 术语，或减少关键词。</div>';
  }
  $('#view').innerHTML = '<h1>搜索结果：'+esc(v)+'</h1>' + body;
});

/* ---------- Mermaid 懒加载 ---------- */
function renderMermaid(){
  if(!document.querySelector('.mermaid')) return;
  const boot=()=>{ try{
    mermaid.initialize({startOnLoad:false, theme: matchMedia('(prefers-color-scheme: dark)').matches?'dark':'default'});
    document.querySelectorAll('.mermaid').forEach(el=>{
      const code=el.textContent;
      mermaid.render('mm'+Math.random().toString(36).slice(2), code)
        .then(({svg})=>{ el.innerHTML=svg; })
        .catch(()=>{ el.textContent=code; });
    });
  }catch(e){} };
  const urls=['https://registry.npmmirror.com/mermaid/10/files/dist/mermaid.min.js',
              'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js',
              'https://unpkg.com/mermaid@10/dist/mermaid.min.js'];
  let ui=0;
  const tryNext=()=>{
    if(ui>=urls.length) return;
    const s=document.createElement('script');
    s.src=urls[ui++];
    s.onload=boot;
    s.onerror=()=>{ s.remove(); tryNext(); };
    document.head.appendChild(s);
  };
  tryNext();
}

/* ---------- 深色模式 ---------- */
const themeBtn=$('#theme-btn');
themeBtn.onclick=()=>{
  const d = document.body.dataset.theme==='dark';
  document.body.dataset.theme = d? '' : 'dark';
  themeBtn.textContent = d? '🌙 深色' : '☀️ 浅色';
};
/* ---------- 进度按钮绑定 ---------- */
(function(){
  const ex=$('#progress-export'), im=$('#progress-import'), fi=$('#progress-file');
  if(ex) ex.onclick = exportProgress;
  if(im) im.onclick = ()=> fi && fi.click();
  if(fi) fi.onchange = ()=>{ if(fi.files && fi.files[0]) importProgress(fi.files[0]); fi.value=''; };
})();

/* ---------- 启动 ---------- */
renderNav();
window.addEventListener('hashchange', ()=>showPage(routeIdFromHash()));
(function(){
  const sb=document.querySelector('.sidebar'); if(!sb) return;
  const btn=document.createElement('button'); btn.id='nav-toggle'; btn.textContent='目录（点开选择章节）';
  btn.onclick=()=>sb.classList.toggle('open');
  sb.insertBefore(btn, sb.querySelector('#nav'));
  window.addEventListener('hashchange',()=>{ if(window.innerWidth<=760) sb.classList.remove('open'); });
})();
showPage(routeIdFromHash());
</script>
</body>
</html>
"""


# ----------------------------------------------------------------------------
# 主流程
# ----------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="zhishu 知枢：组装单文件 HTML 学习伴侣")
    ap.add_argument("--manifest", required=True, help="manifest.json 路径")
    ap.add_argument("--out", required=True, help="输出 HTML 路径")
    args = ap.parse_args()

    mdir = os.path.dirname(os.path.abspath(args.manifest))
    with open(args.manifest, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    base = mdir
    pages = {}
    for ch in manifest.get("chapters", []):
        fp = os.path.join(base, ch.get("file", ""))
        if not os.path.exists(fp):
            print(f"错误：章节文件不存在 {fp}", file=sys.stderr)
            return 2
        with open(fp, "r", encoding="utf-8") as f:
            pages[ch["id"]] = {"html": md_to_html(f.read()), "kind": "chapter", "title": ch.get("title", ch["id"])}
    for c in manifest.get("concepts", []):
        fp = os.path.join(base, c.get("file", ""))
        if not os.path.exists(fp):
            print(f"错误：概念文件不存在 {fp}", file=sys.stderr)
            return 2
        with open(fp, "r", encoding="utf-8") as f:
            pages[c["id"]] = {"html": md_to_html(f.read()), "kind": "concept", "title": c.get("title", c["id"])}

    data = {"manifest": manifest, "pages": pages, "base_dir": base}
    html_out = build_html(data)

    os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(html_out)

    kb = os.path.getsize(args.out)
    print(f"完成：{args.out}")
    print(f"  章节 {len(manifest.get('chapters', []))} · 概念 {len(manifest.get('concepts', []))} · "
          f"测验 {len(manifest.get('quizzes', []))} · 抽认卡 {len(manifest.get('flashcards', []))} · "
          f"术语 {len(manifest.get('glossary', []))}")
    print(f"  文件大小 {kb/1024:.1f} KB（单文件，可离线打开；公式需联网加载 KaTeX）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
