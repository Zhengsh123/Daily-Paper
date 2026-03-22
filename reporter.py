"""Markdown报告生成模块 - 输出 MD + PDF"""

import os
import re
from datetime import datetime, timezone
import markdown
from fpdf import FPDF
from fetcher import Paper

_FONT_PATH = "C:/Windows/Fonts/simhei.ttf"


def generate_report(papers: list[Paper], config: dict, target_date: str = "") -> str:
    """
    生成Markdown格式的每日论文报告。

    Args:
        papers: 已筛选和总结的论文列表
        config: 配置字典
        target_date: 目标日期字符串 (YYYY-MM-DD)

    Returns:
        Markdown格式的报告字符串
    """
    report_date = target_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    keywords = config.get("filter", {}).get("keywords", [])

    lines = [
        f"# Daily arXiv Paper Report - {report_date}",
        "",
        f"> 筛选关键词: {', '.join(keywords)}  ",
        f"> 论文数量: {len(papers)}  ",
        f"> 生成时间: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "---",
        "",
    ]

    if not papers:
        lines.append("今日没有匹配的论文。")
        return "\n".join(lines)

    # 按 LLM 主题分类分组，固定顺序
    CATEGORY_ORDER = ["LLM/Large Multimodal Model", "Video", "Embodied", "Other"]
    grouped: dict[str, list[Paper]] = {}
    for paper in papers:
        cat = paper.category if paper.category in CATEGORY_ORDER else "Other"
        grouped.setdefault(cat, []).append(paper)

    for category in CATEGORY_ORDER:
        cat_papers = grouped.get(category, [])
        if not cat_papers:
            continue
        lines.append(f"## {category} ({len(cat_papers)} 篇)")
        lines.append("")

        for i, paper in enumerate(cat_papers, 1):
            authors_str = ", ".join(paper.authors[:5])
            if len(paper.authors) > 5:
                authors_str += f" 等 ({len(paper.authors)} 位作者)"

            lines.extend([
                f"### {i}. {paper.title}",
                "",
                f"**作者**: {authors_str}  ",
                f"**论文页面**: [{paper.url}]({paper.url})  ",
                f"**PDF链接**: [{paper.pdf_url}]({paper.pdf_url})  ",
                f"**发布日期**: {paper.published.strftime('%Y-%m-%d')}  ",
                f"**分类**: {', '.join(paper.categories)}",
                "",
            ])

            if paper.summary:
                lines.extend([
                    "#### AI 总结",
                    "",
                    paper.summary,
                    "",
                ])

            lines.extend([
                "---",
                "",
            ])

    return "\n".join(lines)


def _fix_markdown_for_pdf(text: str) -> str:
    """修复 markdown 文本以确保列表和换行在 HTML 转换后正确渲染。

    在非列表行后紧跟的首个 '- ' 列表项前插入空行（markdown 要求列表前有空行才识别为列表）。
    连续的 '- ' 列表项之间不插入空行，保持紧凑列表。
    """
    lines = text.split('\n')
    result = []
    for i, line in enumerate(lines):
        # 当前行是列表项，前一行非空且不是列表项 → 插入空行
        if line.startswith('- ') and i > 0 and result and result[-1] != '' and not result[-1].startswith('- '):
            result.append('')
        result.append(line)
    return '\n'.join(result)


def _html_lists_to_dashes(html: str) -> str:
    """将 HTML 无序列表转为 '- ' 前缀段落，避免 fpdf2 渲染 bullet 字符缺失。"""
    html = html.replace('<ul>', '').replace('</ul>', '')
    html = re.sub(r'<li>(.*?)</li>', r'<p style="margin-left:20px;">- \1</p>', html, flags=re.DOTALL)
    return html


def _create_pdf(report: str, pdf_path: str):
    """将 Markdown 报告转为 PDF（使用 fpdf2）"""
    fixed = _fix_markdown_for_pdf(report)
    html_body = markdown.markdown(fixed, extensions=["extra"])
    html_body = _html_lists_to_dashes(html_body)

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    # 注册中文字体（常规/粗体/斜体/粗斜体均用同一字体文件）
    pdf.add_font("SimHei", "", _FONT_PATH)
    pdf.add_font("SimHei", "B", _FONT_PATH)
    pdf.add_font("SimHei", "I", _FONT_PATH)
    pdf.add_font("SimHei", "BI", _FONT_PATH)
    pdf.set_font("SimHei", size=11)

    pdf.write_html(html_body)
    pdf.output(pdf_path)


def parse_report(md_path: str) -> list[dict]:
    """从 markdown 报告中解析论文列表，返回结构化数据。

    Returns:
        [{index, title, category, url, pdf_url, date, tags, one_line_summary}]
    """
    with open(md_path, "r", encoding="utf-8") as f:
        content = f.read()

    papers = []
    current_category = ""
    current_paper: dict | None = None

    for line in content.split("\n"):
        # 分类标题: ## LLM/Large Multimodal Model (29 篇)
        if line.startswith("## ") and "篇)" in line:
            current_category = re.match(r"## (.+?)\s*\(", line).group(1)
            continue

        # 论文标题: ### 1. Title Here
        m = re.match(r"### (\d+)\.\s+(.+)", line)
        if m:
            if current_paper:
                papers.append(current_paper)
            current_paper = {
                "index": len(papers),
                "num": m.group(1),
                "title": m.group(2),
                "category": current_category,
                "url": "", "pdf_url": "", "date": "", "tags": "",
                "one_line_summary": "",
            }
            continue

        if not current_paper:
            continue

        # 元数据行
        if line.startswith("**论文页面**"):
            m2 = re.search(r"\((.+?)\)", line)
            if m2:
                current_paper["url"] = m2.group(1)
        elif line.startswith("**PDF链接**"):
            m2 = re.search(r"\((.+?)\)", line)
            if m2:
                current_paper["pdf_url"] = m2.group(1)
        elif line.startswith("**发布日期**"):
            current_paper["date"] = line.split(":")[-1].strip().rstrip("  ")
        elif line.startswith("**分类**"):
            current_paper["tags"] = line.split(":")[-1].strip()
        elif "一句话总结" in line:
            current_paper["one_line_summary"] = re.sub(
                r"\*\*一句话总结\*\*\s*[:：]\s*", "", line
            ).strip()

    if current_paper:
        papers.append(current_paper)

    return papers


def save_report(report: str, config: dict, target_date: str = "") -> str:
    """
    保存报告到 MD 和 PDF 文件。

    Returns:
        MD 文件路径
    """
    output_dir = config.get("output", {}).get("dir", "outputs")

    os.makedirs(output_dir, exist_ok=True)
    if target_date:
        filename = f"{target_date}.md"
    else:
        filename_format = config.get("output", {}).get("filename_format", "%Y-%m-%d.md")
        filename = datetime.now(timezone.utc).strftime(filename_format)
    md_path = os.path.join(output_dir, filename)

    # 保存 Markdown
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"[Reporter] MD 报告已保存: {md_path}")

    # 生成 PDF
    pdf_path = os.path.splitext(md_path)[0] + ".pdf"
    try:
        _create_pdf(report, pdf_path)
        print(f"[Reporter] PDF 报告已保存: {pdf_path}")
    except Exception as e:
        print(f"[Reporter] PDF 生成失败: {e}")

    return md_path
