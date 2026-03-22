"""Daily Paper Web 服务 - 浏览论文 + 触发深度总结"""

import io
import os
import sys
import glob
import threading
from datetime import datetime, date, timedelta, timezone

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import yaml
import markdown
from flask import Flask, render_template, request, jsonify, redirect, url_for

from reporter import parse_report
from deep_summary import deep_summarize, save_deep_report

app = Flask(__name__)

BJT = timezone(timedelta(hours=8))

# --- 全局状态 ---
_task = {"status": "idle", "completed": 0, "total": 0, "results": {}, "overview": ""}
_task_lock = threading.Lock()


def _load_config(path="config.yaml"):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _compute_target_date() -> date:
    """根据北京时间计算目标论文日期。"""
    today = datetime.now(BJT).date()
    weekday = today.weekday()
    if weekday == 0:
        return today - timedelta(days=3)
    elif weekday == 5:
        return today - timedelta(days=2)
    elif weekday == 6:
        return today - timedelta(days=3)
    else:
        return today - timedelta(days=1)


def _target_report(output_dir="outputs"):
    """找到当前 target_date 对应的日报文件"""
    target_str = _compute_target_date().isoformat()
    path = os.path.join(output_dir, f"{target_str}.md")
    return path if os.path.exists(path) else None


@app.route("/")
def index():
    md_path = _target_report()
    if not md_path:
        return "<h1>No report found. Run main.py first.</h1>", 404

    papers = parse_report(md_path)
    date = os.path.splitext(os.path.basename(md_path))[0]

    # 按分类分组，保持顺序
    cat_order = ["LLM/Large Multimodal Model", "Video", "Embodied", "Other"]
    grouped_dict: dict[str, list] = {}
    for p in papers:
        grouped_dict.setdefault(p["category"], []).append(p)
    grouped = [(cat, grouped_dict[cat]) for cat in cat_order if cat in grouped_dict]

    return render_template("index.html", date=date, total=len(papers), grouped=grouped)


@app.route("/deep", methods=["POST"])
def deep_submit():
    picks = request.form.getlist("picks")
    if not picks:
        return redirect(url_for("index"))

    md_path = _target_report()
    papers = parse_report(md_path)
    date_str = os.path.splitext(os.path.basename(md_path))[0]

    pick_indices = set(int(p) for p in picks)
    selected = [p for p in papers if p["index"] in pick_indices]
    urls = [p["url"] for p in selected]
    titles = {p["url"]: p["title"] for p in selected}

    if not urls:
        return redirect(url_for("index"))

    config = _load_config()

    with _task_lock:
        if _task["status"] == "running":
            return redirect(url_for("deep_result"))
        _task["status"] = "running"
        _task["completed"] = 0
        _task["total"] = len(urls)
        _task["results"] = {}
        _task["overview"] = ""
        _task["titles"] = titles

    def _run():
        def _on_progress(completed, total, phase=""):
            with _task_lock:
                _task["completed"] = completed

        try:
            results, overview = deep_summarize(urls, config, concurrency=5, progress_callback=_on_progress)
            save_deep_report(results, overview, titles=titles, target_date=date_str)
            with _task_lock:
                _task["results"] = results
                _task["overview"] = overview
                _task["status"] = "done"
        except Exception as e:
            print(f"[Server] Deep summary failed: {e}")
            with _task_lock:
                _task["status"] = "error"

    threading.Thread(target=_run, daemon=True).start()
    return redirect(url_for("deep_result"))


@app.route("/deep/status")
def deep_status():
    with _task_lock:
        return jsonify({
            "status": _task["status"],
            "completed": _task["completed"],
            "total": _task["total"],
        })


@app.route("/deep/result")
def deep_result():
    with _task_lock:
        status = _task["status"]
        completed = _task["completed"]
        total = _task["total"]
        results = _task["results"]
        overview = _task["overview"]
        titles = _task.get("titles", {})

    date = ""
    md_path = _target_report()
    if md_path:
        date = os.path.splitext(os.path.basename(md_path))[0]

    pct = int(completed / total * 100) if total > 0 else 0
    content = ""
    overview_html = ""

    if status == "done" and results:
        # 渲染综合报告
        if overview:
            overview_html = markdown.markdown(overview, extensions=["extra"])

        # 渲染各论文总结
        lines = []
        for i, (url, summary) in enumerate(results.items(), 1):
            title = titles.get(url, f"Paper {i}")
            lines.extend([f"# {i}. {title}", "", f"**Link**: [{url}]({url})", "", summary, "", "---", ""])
        md_text = "\n".join(lines)
        content = markdown.markdown(md_text, extensions=["extra"])

    return render_template("deep_result.html",
                           status=status, completed=completed, total=total,
                           pct=pct, date=date, content=content,
                           overview_html=overview_html)


if __name__ == "__main__":
    print("=" * 50)
    print("Daily Paper Web Server")
    print("Open http://0.0.0.0:5000/ in your browser")
    print("=" * 50)
    app.run(host="0.0.0.0", port=5000, debug=False)
