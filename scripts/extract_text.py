#!/usr/bin/env python3
"""book-enlighten: 多格式书籍文本抽取脚本。

用法：
  python3 extract_text.py --check
  python3 extract_text.py <file_or_dir>... [--out <dir>]

支持格式：PDF / EPUB / DOCX / TXT / MD / HTML / RTF。
抽取策略：每种格式按可用解析器顺序尝试，取第一个成功者。
数学类 PDF 若抽取出现大量乱码（cid:/□），会给出强警告：
此时应改用 Read 工具按页读 PDF 截图，不要使用乱码文本。
"""
import argparse
import html as html_mod
import os
import re
import shutil
import sys
import zipfile
from html.parser import HTMLParser

# ----------------------------------------------------------------------------
# 解析器可用性探测
# ----------------------------------------------------------------------------

def _probe():
    avail = {"fitz": False, "pdfplumber": False, "pdftotext": False,
             "docx": False, "ebooklib": False}
    try:
        import fitz  # noqa: F401
        avail["fitz"] = True
    except Exception:
        pass
    try:
        import pdfplumber  # noqa: F401
        avail["pdfplumber"] = True
    except Exception:
        pass
    avail["pdftotext"] = shutil.which("pdftotext") is not None
    try:
        import docx  # noqa: F401
        avail["docx"] = True
    except Exception:
        pass
    try:
        import ebooklib  # noqa: F401
        avail["ebooklib"] = True
    except Exception:
        pass
    return avail


def check_report():
    avail = _probe()
    lines = []
    for k, v in avail.items():
        lines.append(f"  {k:12s} {'可用' if v else '缺失'}")
    lines.append("")
    lines.append("建议安装：pip install pymupdf pdfplumber python-docx ebooklib")
    lines.append("或系统包：poppler-utils（提供 pdftotext）")
    print("\n".join(lines))
    return avail


# ----------------------------------------------------------------------------
# 抽取器
# ----------------------------------------------------------------------------

class _TextExtractor(HTMLParser):
    """收集 HTML/EPUB 内文本。"""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip_depth += 1
        if tag in ("p", "div", "br", "li", "h1", "h2", "h3", "h4", "tr", "section"):
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self.skip_depth > 0:
            self.skip_depth -= 1
        if tag in ("p", "div", "li", "h1", "h2", "h3", "h4", "tr"):
            self.parts.append("\n")

    def handle_data(self, data):
        if self.skip_depth == 0:
            self.parts.append(data)


def _extract_pdf(path):
    """返回 (text, warnings)。按 fitz → pdfplumber → pdftotext 顺序。"""
    warnings = []
    text = None
    try:
        try:
            import pymupdf as fitz  # PyMuPDF 新包名
        except Exception:
            import fitz  # 旧包名（有弃用警告）
        doc = fitz.open(path)
        text = "\n".join(page.get_text() for page in doc)
        doc.close()
    except Exception:
        pass
    if text is None or not text.strip():
        try:
            import pdfplumber
            with pdfplumber.open(path) as pdf:
                text = "\n".join((page.extract_text() or "") for page in pdf.pages)
        except Exception:
            pass
    if text is None or not text.strip():
        if shutil.which("pdftotext"):
            import subprocess
            r = subprocess.run(["pdftotext", "-layout", path, "-"],
                               capture_output=True, text=True)
            if r.returncode == 0:
                text = r.stdout
    if text is None:
        raise RuntimeError("PDF 抽取失败：没有可用的解析器（fitz/pdfplumber/pdftotext）")
    # 乱码检测：cid: 引用、替换符、公式丢失
    cid = len(re.findall(r"\(cid:\d+\)", text))
    repl = text.count("\ufffd")
    if cid > 20 or repl > 200:
        warnings.append(
            f"检测到疑似乱码（cid:{cid} 处 / 替换符 {repl} 个）。"
            "若为数学/公式类 PDF，请改用 Read 工具按页读 PDF 截图，"
            "不要基于本乱码文本生成内容。")
    return text, warnings


def _extract_epub(path):
    text_parts = []
    with zipfile.ZipFile(path) as zf:
        names = [n for n in zf.namelist()
                 if n.lower().endswith((".xhtml", ".html", ".htm"))]
        names.sort()
        for n in names:
            data = zf.read(n).decode("utf-8", errors="replace")
            p = _TextExtractor()
            p.feed(data)
            text_parts.append("".join(p.parts))
    return "\n\n".join(text_parts), []


def _extract_docx(path):
    try:
        import docx as docxmod
        d = docxmod.Document(path)
        parts = []
        for para in d.paragraphs:
            parts.append(para.text)
        for table in d.tables:
            for row in table.rows:
                parts.append(" | ".join(cell.text for cell in row.cells))
        return "\n".join(parts), []
    except Exception:
        pass
    # 回退：直接解包 document.xml
    text_parts = []
    with zipfile.ZipFile(path) as zf:
        data = zf.read("word/document.xml").decode("utf-8", errors="replace")
    # 段落边界
    data = re.sub(r"</w:p>", "\n", data)
    data = re.sub(r"</w:tc>", " | ", data)
    data = re.sub(r"<[^>]+>", "", data)
    data = html_mod.unescape(data)
    return data, []


def _extract_plain(path):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read(), []


def _extract_html(path):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        data = f.read()
    p = _TextExtractor()
    p.feed(data)
    return "".join(p.parts), []


def _extract_rtf(path):
    with open(path, "r", encoding="cp1252", errors="replace") as f:
        data = f.read()
    # 移除组；保留 \par 为换行；移除控制字
    data = re.sub(r"\{\*?\\[^{}]*\}", "", data)
    data = data.replace("\\par", "\n").replace("\\pard", "\n")
    data = re.sub(r"\\[a-zA-Z]+-?\d* ?", "", data)
    data = re.sub(r"[{}]", "", data)
    return data, []


# ----------------------------------------------------------------------------
# 章节标题探测（辅助结构拆解）
# ----------------------------------------------------------------------------

CHAPTER_RE = re.compile(
    r"^\s*(第\s*[0-9一二三四五六七八九十百零〇]+\s*[章节部篇卷]"
    r"|Chapter\s+\d+|CHAPTER\s+\d+|Part\s+\d+|PART\s+\d+)",
    re.IGNORECASE)


def _detect_heads(text, max_heads=200):
    heads = []
    for line in text.splitlines():
        line = line.strip()
        if not line or len(line) > 80:
            continue
        if CHAPTER_RE.match(line):
            heads.append(line)
        if len(heads) >= max_heads:
            break
    return heads


# ----------------------------------------------------------------------------
# 主流程
# ----------------------------------------------------------------------------

def _iter_inputs(paths):
    for p in paths:
        if os.path.isdir(p):
            for root, _, files in os.walk(p):
                for f in sorted(files):
                    yield os.path.join(root, f)
        else:
            yield p


EXT_MAP = {
    ".pdf": _extract_pdf,
    ".epub": _extract_epub,
    ".docx": _extract_docx,
    ".txt": _extract_plain,
    ".md": _extract_plain,
    ".markdown": _extract_plain,
    ".rst": _extract_plain,
    ".html": _extract_html,
    ".htm": _extract_html,
    ".rtf": _extract_rtf,
}


def main():
    ap = argparse.ArgumentParser(description="多格式书籍文本抽取")
    ap.add_argument("paths", nargs="*", help="文件或目录")
    ap.add_argument("--out", default=None, help="输出目录")
    ap.add_argument("--check", action="store_true", help="检查可用解析器")
    args = ap.parse_args()

    if args.check:
        check_report()
        return 0

    if not args.paths:
        print("错误：未提供输入文件/目录。", file=sys.stderr)
        return 2

    out_dir = args.out or "raw"
    os.makedirs(out_dir, exist_ok=True)
    total_chars = 0
    for fp in _iter_inputs(args.paths):
        ext = os.path.splitext(fp)[1].lower()
        if ext not in EXT_MAP:
            print(f"跳过（不支持格式）: {fp}")
            continue
        try:
            text, warnings = EXT_MAP[ext](fp)
        except Exception as e:
            print(f"失败: {fp} -> {e}", file=sys.stderr)
            continue
        for w in warnings:
            print(f"警告 [{os.path.basename(fp)}]: {w}", file=sys.stderr)
        if not text.strip():
            print(f"警告 [{os.path.basename(fp)}]: 抽取文本为空", file=sys.stderr)
            continue
        stem = os.path.splitext(os.path.basename(fp))[0]
        safe = re.sub(r"[^\w\u4e00-\u9fff-]+", "_", stem)[:60] or "book"
        out_file = os.path.join(out_dir, f"{safe}_{ext[1:]}.txt")
        with open(out_file, "w", encoding="utf-8") as f:
            f.write(text)
        heads = _detect_heads(text)
        total_chars += len(text)
        print(f"OK   {os.path.basename(fp)} -> {out_file}  "
              f"字符 {len(text):,} 疑似章节标题 {len(heads)}")
        for h in heads[:12]:
            print(f"     · {h}")
    print(f"\n完成：共 {total_chars:,} 字符。"
          f"章节标题仅是辅助线索，最终结构以实际精读为准。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
