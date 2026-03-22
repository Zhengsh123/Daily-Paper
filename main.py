"""Daily arXiv Paper Tracker - 主入口"""

import argparse
import io
import os
import sys
from datetime import datetime, date, timedelta, timezone
import yaml

# 修复 Windows 终端 GBK 编码问题
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from fetcher import fetch_papers
from filter import filter_papers
from summarizer import create_summarizer
from reporter import generate_report, save_report
from notifier import send_email

BJT = timezone(timedelta(hours=8))


def load_config(path: str = "config.yaml") -> dict:
    """加载配置文件"""
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _compute_target_date() -> date:
    """根据北京时间计算目标论文日期。
    周二~周五 → 昨天，周一 → 上周五，周六 → 周四，周日 → 周四。
    """
    today = datetime.now(BJT).date()
    weekday = today.weekday()  # 0=Mon ... 6=Sun
    if weekday == 0:  # 周一 → 上周五
        return today - timedelta(days=3)
    elif weekday == 5:  # 周六 → 周四
        return today - timedelta(days=2)
    elif weekday == 6:  # 周日 → 周四
        return today - timedelta(days=3)
    else:  # 周二~周五 → 昨天
        return today - timedelta(days=1)


def _days_back_for(target: date) -> int:
    """根据 target_date 和当前日期推算需要回溯的天数（多留 1 天余量）。"""
    today = datetime.now(BJT).date()
    gap = (today - target).days
    return max(gap + 1, 2)


def main():
    parser = argparse.ArgumentParser(description="Daily arXiv Paper Tracker")
    parser.add_argument("-c", "--config", default="config.yaml", help="配置文件路径")
    parser.add_argument("--no-summary", action="store_true", help="跳过LLM摘要总结")
    parser.add_argument("--no-email", action="store_true", help="跳过邮件发送")
    parser.add_argument("--date", type=str, default="",
                        help="手动指定目标日期 (格式: YYYY-MM-DD)，跳过周末检查和去重检查")
    args = parser.parse_args()

    # 1. 加载配置
    print("=" * 60)
    print("Daily arXiv Paper Tracker")
    print("=" * 60)

    config = load_config(args.config)
    output_dir = config.get("output", {}).get("dir", "outputs")

    # 2. 确定 target_date
    if args.date:
        target = datetime.strptime(args.date, "%Y-%m-%d").date()
        target_str = target.isoformat()
        print(f"\n[日期] 手动指定目标日期: {target_str}")
    else:
        target = _compute_target_date()
        target_str = target.isoformat()
        print(f"\n[日期] 自动计算目标日期: {target_str} (北京时间)")

        # 去重检查：已存在则复用，不重新生成
        existing = os.path.join(output_dir, f"{target_str}.md")
        if os.path.exists(existing):
            print(f"[日期] {existing} 已存在，复用已有报告。")
            print(f"\n{'=' * 60}")
            print(f"完成! 报告: {existing}")
            print(f"{'=' * 60}")
            sys.exit(0)

    days_back = _days_back_for(target)

    # 3. 抓取论文
    arxiv_config = config.get("arxiv", {})
    categories = arxiv_config.get("categories", ["cs.AI"])
    max_results = arxiv_config.get("max_results", 200)

    print(f"\n[1/5] 抓取论文 (分类: {categories})")
    papers = fetch_papers(categories, max_results=max_results, days_back=days_back)

    if not papers:
        print("未抓取到任何论文，退出。")
        sys.exit(0)

    # 按 target_date 过滤
    before = len(papers)
    papers = [p for p in papers if p.published.date() == target]
    print(f"[Date] 日期过滤: {before} -> {len(papers)} 篇 (published={target_str})")
    if not papers:
        print("目标日期没有论文，退出。")
        sys.exit(0)

    # 4. 关键词筛选
    print(f"\n[2/5] 关键词筛选")
    papers = filter_papers(papers, config)

    if not papers:
        print("筛选后没有匹配的论文，生成空报告。")

    # 5. LLM 摘要总结
    if papers and not args.no_summary:
        print(f"\n[3/5] LLM 摘要总结 ({len(papers)} 篇)")
        try:
            summarizer = create_summarizer(config)
            papers = summarizer.summarize_batch(papers)
        except Exception as e:
            print(f"[Summarizer] 初始化失败: {e}")
            print("[Summarizer] 将跳过摘要总结，继续生成报告")
    else:
        print(f"\n[3/5] 跳过 LLM 摘要总结")

    # 6. 生成报告
    print(f"\n[4/5] 生成 Markdown 报告")
    report = generate_report(papers, config, target_date=target_str)
    filepath = save_report(report, config, target_date=target_str)

    # 7. 邮件通知
    if not args.no_email:
        print(f"\n[5/5] 发送邮件通知")
        try:
            send_email(report, config)
        except Exception as e:
            print(f"邮件发送失败: {e}")
    else:
        print(f"\n[5/5] 跳过邮件发送")

    print(f"\n{'=' * 60}")
    print(f"完成! 共 {len(papers)} 篇论文。报告: {filepath}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
