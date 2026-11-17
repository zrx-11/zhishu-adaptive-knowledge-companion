#!/usr/bin/env python3
"""给知枢产物注入深色视觉层（只改样式，不改结构）。

用法：
  python3 scripts/apply_visual_theme.py --file <page.html>
  python3 scripts/apply_visual_theme.py --root <目录>
  python3 scripts/apply_visual_theme.py --root <目录> --all-html
  python3 scripts/apply_visual_theme.py --root <目录> --dry-run

默认处理 index.html 和 *学习伴侣.html；--all-html 处理目录内全部 HTML。
脚本可重复执行：已有的 #zs-visual-theme 会被替换，不会叠加。
"""
import argparse
import re
import sys
from pathlib import Path

CSS_PATH = Path(__file__).resolve().parent.parent / "assets" / "visual-theme.css"

STYLE_OPEN = '<style id="zs-visual-theme">'
STYLE_CLOSE = "</style>"

INIT_JS = """<script id="zs-visual-init">
(function(){
  try{
    var B=document.body, H=document.documentElement;
    if(!B.dataset.theme && !H.dataset.theme) B.dataset.theme='dark';
    var EMOJI=/[\\u{1F000}-\\u{1FAFF}\\u{2600}-\\u{27BF}\\u{2B00}-\\u{2BFF}\\u{FE0F}\\u{200D}]/gu;
    var scope=document.querySelectorAll('header, .topbar, .topbar-fixed, #topbar, .sidebar, .tabs, .hdr-right, .card-actions, .card-controls, .section-title, .card .icon, .icon-label');
    for(var i=0;i<scope.length;i++){
      var w=document.createTreeWalker(scope[i],NodeFilter.SHOW_TEXT,null,false), n;
      while(n=w.nextNode()){
        if(EMOJI.test(n.nodeValue)){
          n.nodeValue=n.nodeValue.replace(EMOJI,'').replace(/[ \\t]+/g,' ').replace(/^ | $/g,'');
        }
      }
    }
    var btn=document.getElementById('theme-btn')||document.getElementById('theme')||document.getElementById('themeToggle');
    function label(){
      if(!btn) return;
      var light=B.dataset.theme==='light'||H.getAttribute('data-theme')==='light'||B.dataset.theme==='';
      if(btn.textContent.trim()===''||/浅色|深色/.test(btn.textContent)) btn.textContent=light?'深色':'浅色';
    }
    label();
    if(btn){
      new MutationObserver(label).observe(B,{attributes:true,attributeFilter:['data-theme']});
      new MutationObserver(label).observe(H,{attributes:true,attributeFilter:['data-theme']});
      btn.addEventListener('click',function(){setTimeout(label,0);},true);
    }
  }catch(e){}
})();
</script>"""


def build_style(css: str) -> str:
    return f'{STYLE_OPEN}\n{css}\n{STYLE_CLOSE}'


def apply_file(path: Path, css: str, dry_run: bool = False, force_dark: bool = False) -> bool:
    s = path.read_text(encoding="utf-8", errors="replace")
    orig = s
    style = build_style(css)

    if force_dark:
        # 只改初始属性；页面自己的主题按钮仍可在运行时切回浅色。
        s = re.sub(r'(<html[^>]*\bdata-theme=")light(")', r'\1dark\2', s, count=1)
        s = re.sub(r'(<body[^>]*\bdata-theme=")light(")', r'\1dark\2', s, count=1)

    style_re = re.compile(r'<style id="zs-visual-theme">.*?</style>', re.S)
    if style_re.search(s):
        s2 = style_re.sub(lambda _m: style, s, count=1)
    else:
        if "</head>" not in s:
            raise ValueError("没有 </head>，不是完整 HTML 页面")
        s2 = s.replace("</head>", style + "\n</head>", 1)

    init_re = re.compile(r'<script id="zs-visual-init">.*?</script>', re.S)
    if init_re.search(s2):
        s2 = init_re.sub(lambda _m: INIT_JS, s2, count=1)
    else:
        if "</body>" not in s2:
            raise ValueError("没有 </body>，不是完整 HTML 页面")
        s2 = s2.replace("</body>", INIT_JS + "\n</body>", 1)

    if s2 == orig:
        return False
    if not dry_run:
        path.write_text(s2, encoding="utf-8")
    return True


def iter_targets(root: Path, all_html: bool):
    if not all_html:
        for p in root.rglob("index.html"):
            yield p
        for p in root.rglob("*学习伴侣.html"):
            yield p
    else:
        for p in root.rglob("*.html"):
            yield p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", action="append", default=[], help="单个 HTML，可重复")
    ap.add_argument("--root", help="目录；默认只处理 index.html 与 *学习伴侣.html")
    ap.add_argument("--all-html", action="store_true", help="处理目录内全部 HTML")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force-dark", action="store_true", help="把初始 data-theme=light 改成 dark；运行时仍可切浅色")
    args = ap.parse_args()

    if not CSS_PATH.exists():
        sys.exit(f"找不到样式文件：{CSS_PATH}")
    css = CSS_PATH.read_text(encoding="utf-8")

    targets = []
    for f in args.file:
        targets.append(Path(f))
    if args.root:
        targets.extend(iter_targets(Path(args.root), args.all_html))

    seen = set()
    changed = 0
    skipped = 0
    for p in targets:
        p = p.resolve()
        if p in seen or not p.exists():
            continue
        seen.add(p)
        try:
            ok = apply_file(p, css, args.dry_run, args.force_dark)
            print(("APPLY " if ok else "SAME  ") + str(p))
            if ok:
                changed += 1
            else:
                skipped += 1
        except Exception as e:
            print(f"FAIL  {p} | {e}")
            skipped += 1

    print(f"\n{'DRY-RUN' if args.dry_run else 'DONE'}：{changed} 个更新，{skipped} 个未变化/跳过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
