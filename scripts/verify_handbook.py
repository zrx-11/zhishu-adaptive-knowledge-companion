#!/usr/bin/env python3
"""对点化总入口 index.html 做端到端验证（Playwright）。

用法：
  python3 scripts/verify_handbook.py --index <root>/index.html
  python3 scripts/verify_handbook.py --index ... --chromium /usr/local/bin/chromium --report report.json

覆盖：首页与书卡、所有总览页、每本书首/末章、全部测验作答与解析、抽认卡翻转与计数、
      术语过滤、全局搜索、进度跨刷新持久、深色模式、控制台错误。
退出码：0 全通过；1 有失败。
"""
import argparse
import json
import os
import re
import sys

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sys.exit("需要 playwright：pip install playwright（浏览器可用系统 chromium，通过 --chromium 指定）")


def find_chromium(explicit=None):
    if explicit:
        return explicit
    for c in (os.environ.get("CHROMIUM"), "/usr/local/bin/chromium", "/usr/bin/chromium",
              "/usr/bin/chromium-browser", "/opt/browser/chrome"):
        if c and os.path.exists(c):
            return c
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", required=True)
    ap.add_argument("--chromium", default=None)
    ap.add_argument("--report", default=None)
    args = ap.parse_args()

    url = "file://" + os.path.abspath(args.index)
    results = []

    def check(name, ok, extra=""):
        results.append({"check": name, "pass": bool(ok), "extra": extra})
        print(("PASS " if ok else "FAIL ") + name + (" | " + extra if extra else ""))

    with sync_playwright() as p:
        exe = find_chromium(args.chromium)
        kw = {"args": ["--no-sandbox", "--disable-gpu"]}
        if exe:
            kw["executable_path"] = exe
        browser = p.chromium.launch(**kw)
        page = browser.new_page()
        errors = []

        def on_console(m):
            if m.type != "error":
                return
            txt = m.text or ""
            if re.search(r"mermaid\.min\.js|net::|ERR_", txt):
                return
            errors.append(txt)

        page.on("console", on_console)
        page.on("pageerror", lambda e: errors.append(str(e)))

        # 1 首页（默认路由即第一篇总览）
        page.goto(url)
        page.wait_for_timeout(1200)
        meta = page.evaluate("META")
        cross_meta = page.evaluate("CROSS_META")
        check("首页渲染", "学习总手册" in page.inner_text("#view"))
        cards = page.eval_on_selector_all(".book-card", "els=>els.length")
        check("书卡数量", cards == len(meta), f"{cards}/{len(meta)}")

        # 2 所有总览页
        for c in cross_meta:
            page.evaluate(f"location.hash='#/cross/{c['key']}'")
            page.wait_for_timeout(700)
            txt = page.inner_text("#view")
            check(f"总览页：{c['label']}", len(txt) > 200, f"{len(txt)} 字符")

        # 3 每本书首/末章
        for m in meta:
            k = m["key"]
            chs = page.evaluate(f"BOOKS['{k}'].manifest.chapters")
            if not chs:
                check(f"{k} 章节为空", False)
                continue
            for label, ch in (("首章", chs[0]["id"]), ("末章", chs[-1]["id"])):
                page.evaluate(f"location.hash='#/book/{k}/chapter/{ch}'")
                page.wait_for_timeout(700)
                txt = page.inner_text("#view")
                check(f"{k} {label}渲染", len(txt) > 300, f"{len(txt)} 字符")

        # 4 每本书测验：数量 + 第一题正确作答
        for m in meta:
            k = m["key"]
            page.evaluate(f"location.hash='#/book/{k}/quiz/all'")
            page.wait_for_timeout(700)
            n = page.eval_on_selector_all(".quiz-item", "els=>els.length")
            check(f"{k} 测验题数", n > 0, f"{n} 题")
            if n == 0:
                continue
            info = page.evaluate("""()=>{
                const el=document.querySelector('.quiz-item');
                const qid=el.dataset.qid, type=el.dataset.type;
                const B=BOOKS[cur.book];
                const q=(B.manifest.quizzes||[]).find(x=>x.id===qid);
                return q?{qid:qid,type:q.type,answer:q.answer}:null;
            }""")
            if not info:
                check(f"{k} 测验数据一致性", False, "页面题目在 manifest 中找不到")
                continue
            sel = f".quiz-item[data-qid='{info['qid']}']"
            if info["type"] == "single":
                page.click(f"{sel} input[value='{info['answer']}']")
            elif info["type"] == "multi":
                for a in info["answer"]:
                    page.click(f"{sel} input[value='{a}']")
            else:
                page.fill(f"{sel} .quiz-blank", str(info["answer"]))
            page.click(f"{sel} .quiz-check")
            page.wait_for_timeout(300)
            fb = page.inner_text(f"{sel} .quiz-feedback")
            check(f"{k} 测验正确反馈", "正确" in fb, fb)
            check(f"{k} 测验解析", page.eval_on_selector_all(".quiz-explain", "els=>els.length") > 0)

        # 5 抽认卡（第一本书）
        k0 = meta[0]["key"]
        page.evaluate(f"location.hash='#/book/{k0}/cards'")
        page.wait_for_timeout(700)
        front = page.inner_text(".fc-front").strip()
        check("抽认卡正面有内容", front != "", front[:24])
        page.click("#flashcard")
        check("抽认卡翻转", page.eval_on_selector("#flashcard", "el=>el.classList.contains('flip')"))
        page.click("#card-known-btn")
        check("认识计数增加", page.inner_text("#card-known") == "1", page.inner_text("#card-known"))

        # 6 术语过滤
        page.evaluate(f"location.hash='#/book/{k0}/glossary'")
        page.wait_for_timeout(700)
        total = page.eval_on_selector_all("#glossary-list li", "els=>els.length")
        term = (page.inner_text("#glossary-list li").split("—")[0].strip()[:4]) if total else ""
        page.fill("#glossary-filter", term)
        page.wait_for_timeout(300)
        visible = page.eval_on_selector_all("#glossary-list li",
                                            "els=>els.filter(e=>e.style.display!=='none').length")
        check("术语表过滤", total > 0 and 0 < visible <= total, f"共{total} 过滤后{visible}（{term}）")

        # 7 全局搜索
        page.evaluate("location.hash='#/cross/'+(typeof FIRST_DOC!=='undefined'?FIRST_DOC:'doc1')")
        page.wait_for_timeout(600)
        page.fill("#q", term or "算法")
        page.wait_for_timeout(600)
        hits = page.eval_on_selector_all(".search-hit", "els=>els.length")
        check("全局搜索命中", hits > 0, f"{hits} 条")

        # 8 进度持久 + 路径标记
        chs0 = page.evaluate(f"BOOKS['{k0}'].manifest.chapters")
        if len(chs0) >= 2:
            for ch in (chs0[0]["id"], chs0[1]["id"]):
                page.evaluate(f"location.hash='#/book/{k0}/chapter/{ch}'")
                page.wait_for_timeout(500)
            page.evaluate(f"location.hash='#/book/{k0}/path'")
            page.wait_for_timeout(500)
            label = page.inner_text("#progress-label")
            page.reload()
            page.wait_for_timeout(900)
            label2 = page.inner_text("#progress-label")
            check("进度跨刷新持久", label == label2 and "已学" in label2, f"{label} → {label2}")
            check("学习路径完成标记", "已完成" in page.inner_text("#view"))

        # 9 知枢新增：诊断页、深度片段、出处
        page.evaluate(f"location.hash='#/book/{k0}/diagnosis'")
        page.wait_for_timeout(700)
        diag_txt = page.inner_text("#view")
        check("诊断页可打开", "诊断" in diag_txt and "diag-start", "diag-start" in page.content())
        # 深度片段（如果有）
        page.evaluate(f"location.hash='#/book/{k0}/chapter/{chs0[0]['id']}'")
        page.wait_for_timeout(500)
        has_depth = page.eval_on_selector_all("details.depth-fragment", "els=>els.length")
        if has_depth > 0:
            page.click("details.depth-fragment > summary")
            page.wait_for_timeout(300)
            check("深度片段可展开", page.eval_on_selector("details.depth-fragment", "el=>el.open"))
        else:
            check("深度片段（本书无，跳过）", True, "本书无深度片段")
        # 出处脚注
        has_source = page.eval_on_selector_all(".source-badge", "els=>els.length")
        check("出处脚注存在", has_source > 0, f"{has_source} 处")

        # 10 深色模式
        page.click("#theme-btn")
        check("深色模式", page.eval_on_selector("body", "el=>el.dataset.theme") == "dark")

        check("控制台无错误", len(errors) == 0, " || ".join(errors[:5]))
        browser.close()

    ok = sum(1 for r in results if r["pass"])
    print(f"\n=== {ok}/{len(results)} 通过 ===")
    report = args.report or os.path.join(os.path.dirname(os.path.abspath(args.index)), "_build", "verify_report.json")
    try:
        os.makedirs(os.path.dirname(report), exist_ok=True)
        json.dump(results, open(report, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"报告：{report}")
    except Exception:
        pass
    sys.exit(0 if ok == len(results) else 1)


if __name__ == "__main__":
    main()
