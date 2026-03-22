"""PDF深度总结模块 - 下载arXiv PDF后传给LLM读取并总结"""

import os
import re
import base64
import yaml
import anthropic
import urllib.request

from concurrent.futures import ThreadPoolExecutor, as_completed


DEEP_SUMMARY_PROMPT = """你是一位资深AI研究员。请对这篇论文进行精炼的深度分析。

请用{language}按以下格式输出，总字数控制在500字以内，不要使用LaTeX公式，用纯文字描述数学概念：

## 一句话总结
（一句话概括核心贡献）

## 研究动机
（要解决什么问题？现有方法的不足？2-3句话）

## 核心方法
（论文提出的关键方法和创新设计，用简洁的文字描述，避免公式）

## 实验结果
（关键实验结论和数据指标，用文字表述，不用表格）

## 优势与局限
- 优势：（1-2点）
- 局限：（1-2点）
"""


DAILY_OVERVIEW_PROMPT = """你是一位资深AI研究员。以下是今天精选的{count}篇论文的深度总结。
请用{language}生成一份综合研究报告，要求：

1. **今日研究全景**（200字）：总结今天这批论文整体覆盖的研究方向和趋势
2. **核心技术洞察**（300字）：跨论文分析共性的技术路线、方法创新和关键发现
3. **潜在研究方向**（300字）：基于这些论文的工作，提出3-5个你认为值得继续深入研究的具体方向，每个方向说明为什么值得做、可能的切入点

以下是各论文的总结：

{summaries}
"""


def _to_pdf_url(url: str) -> str:
    """将任意 arXiv URL 转换为 PDF 直链"""
    match = re.search(r"(\d{4}\.\d{4,5})(v\d+)?", url)
    if match:
        return f"https://arxiv.org/pdf/{match.group(0)}"
    raise ValueError(f"无法从URL中提取arXiv ID: {url}")


def _download_pdf(pdf_url: str) -> bytes:
    """下载PDF文件并返回字节内容"""
    req = urllib.request.Request(pdf_url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


def deep_summarize_one(url: str, client: anthropic.Anthropic,
                       model: str, max_tokens: int, language: str) -> str:
    """对单篇论文进行基于PDF的深度总结"""
    pdf_url = _to_pdf_url(url)
    print(f"[DeepSummary] 正在下载: {pdf_url}")
    pdf_data = _download_pdf(pdf_url)
    pdf_b64 = base64.standard_b64encode(pdf_data).decode("ascii")
    print(f"[DeepSummary] 正在总结: {pdf_url} ({len(pdf_data)//1024}KB)")

    msg = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "document",
                    "source": {
                        "type": "base64",
                        "media_type": "application/pdf",
                        "data": pdf_b64,
                    },
                },
                {
                    "type": "text",
                    "text": DEEP_SUMMARY_PROMPT.format(language=language),
                },
            ],
        }],
    )
    return msg.content[0].text


def generate_daily_overview(results: dict[str, str], client: anthropic.Anthropic,
                            model: str, max_tokens: int, language: str) -> str:
    """根据所有论文的深度总结，生成一份综合研究报告"""
    summaries = "\n\n---\n\n".join(
        f"**论文 {i+1}** ({url}):\n{summary}"
        for i, (url, summary) in enumerate(results.items())
        if not summary.startswith("*深度总结生成失败")
    )

    print(f"[DeepSummary] 正在生成综合研究报告...")
    msg = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        messages=[{
            "role": "user",
            "content": DAILY_OVERVIEW_PROMPT.format(
                count=len(results), language=language, summaries=summaries
            ),
        }],
    )
    return msg.content[0].text


def deep_summarize(urls: list[str], config: dict, concurrency: int = 5,
                   progress_callback=None) -> tuple[dict[str, str], str]:
    """
    批量深度总结 + 生成综合报告。

    Args:
        urls: arXiv论文URL列表
        config: 配置字典
        concurrency: 并发数
        progress_callback: 可选回调函数 callback(completed, total, phase)

    Returns:
        (各论文总结字典, 综合报告文本)
    """
    llm = config.get("llm", {})
    base_url = llm.get("base_url", "https://api.anthropic.com")
    api_key = llm.get("api_key", "")
    if not api_key:
        api_key = os.environ.get(llm.get("api_key_env", "LLM_API_KEY"), "")
    model = llm.get("model", "claude-sonnet-4-20250514")
    max_tokens = llm.get("max_tokens", 4096)
    language = llm.get("language", "中文")

    client = anthropic.Anthropic(base_url=base_url, api_key=api_key)
    results = {}

    total_steps = len(urls) + 1  # +1 for overview
    print(f"[DeepSummary] 开始深度总结 {len(urls)} 篇论文 (concurrency={concurrency})")

    # 阶段1：并发总结各论文
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = {
            executor.submit(deep_summarize_one, url, client, model, max_tokens, language): url
            for url in urls
        }
        done_count = 0
        for future in as_completed(futures):
            url = futures[future]
            done_count += 1
            try:
                results[url] = future.result()
                print(f"[DeepSummary] 完成 ({done_count}/{len(urls)}): {url}")
            except Exception as e:
                print(f"[DeepSummary] 失败 {url}: {e}")
                results[url] = f"*深度总结生成失败: {e}*"
            if progress_callback:
                progress_callback(done_count, total_steps, "summarizing")

    # 阶段2：生成综合研究报告
    overview = ""
    try:
        overview = generate_daily_overview(results, client, model, max_tokens, language)
        print(f"[DeepSummary] 综合报告生成完成")
    except Exception as e:
        print(f"[DeepSummary] 综合报告生成失败: {e}")
        overview = f"*综合报告生成失败: {e}*"

    if progress_callback:
        progress_callback(total_steps, total_steps, "done")

    return results, overview


def save_deep_report(results: dict[str, str], overview: str = "",
                     output_dir: str = "outputs", titles: dict[str, str] = None,
                     target_date: str = "") -> str:
    """将深度总结保存为Markdown和PDF文件"""
    from datetime import datetime, timezone
    from reporter import _create_pdf
    os.makedirs(output_dir, exist_ok=True)

    report_date = target_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    filename = f"{report_date}_deep.md"
    filepath = os.path.join(output_dir, filename)

    lines = [
        f"# Deep Paper Summary - {report_date}",
        "",
        f"> {len(results)} papers",
        "",
    ]

    # 综合研究报告
    if overview:
        lines.extend([
            "---",
            "",
            "# Daily Research Overview",
            "",
            overview,
            "",
        ])

    lines.extend(["---", ""])

    for i, (url, summary) in enumerate(results.items(), 1):
        title = (titles or {}).get(url, f"Paper {i}")
        lines.extend([
            f"# {i}. {title}",
            "",
            f"**Link**: [{url}]({url})",
            "",
            summary,
            "",
            "---",
            "",
        ])

    report = "\n".join(lines)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"[DeepSummary] 深度报告已保存: {filepath}")

    # 生成 PDF
    pdf_path = os.path.splitext(filepath)[0] + ".pdf"
    try:
        _create_pdf(report, pdf_path)
        print(f"[DeepSummary] PDF 报告已保存: {pdf_path}")
    except Exception as e:
        print(f"[DeepSummary] PDF 生成失败: {e}")

    return filepath


if __name__ == "__main__":
    import argparse
    import io, sys
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="arXiv 论文 PDF 深度总结")
    parser.add_argument("urls", nargs="+", help="arXiv论文URL列表")
    parser.add_argument("-c", "--config", default="config.yaml", help="配置文件路径")
    parser.add_argument("-n", "--concurrency", type=int, default=5, help="并发数")
    args = parser.parse_args()

    with open(args.config, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    results, overview = deep_summarize(args.urls, config, concurrency=args.concurrency)
    filepath = save_deep_report(results, overview)
    print(f"\n完成! 报告: {filepath}")
