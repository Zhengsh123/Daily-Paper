"""arXiv论文抓取模块"""

import arxiv
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone


@dataclass
class Paper:
    """论文数据结构"""
    title: str
    authors: list[str]
    abstract: str
    url: str          # 论文页面链接 (abs)
    pdf_url: str      # PDF 直链
    categories: list[str]
    published: datetime
    primary_category: str
    summary: str = ""  # LLM生成的总结
    category: str = ""  # LLM主题分类 (LLM/Large Multimodal Model, Video, Embodied, Other)

    def __repr__(self):
        return f"Paper(title='{self.title[:50]}...', published={self.published.date()})"


def _auto_days_back() -> int:
    """根据星期自动计算回溯天数（arXiv周末不更新）"""
    weekday = datetime.now(timezone.utc).weekday()  # 0=Mon
    if weekday == 0:  # 周一：回溯3天（覆盖周五~周日）
        return 3
    elif weekday == 6:  # 周日
        return 2
    elif weekday == 5:  # 周六
        return 1
    return 1


def fetch_papers(categories: list[str], max_results: int = 200, days_back: int = 0) -> list[Paper]:
    """
    从arXiv抓取指定分类的最新论文。

    Args:
        categories: arXiv分类列表, 如 ["cs.AI", "cs.CL"]
        max_results: 每个分类最大查询数量
        days_back: 抓取过去N天的论文, 0=自动根据星期决定

    Returns:
        论文列表
    """
    if days_back <= 0:
        days_back = _auto_days_back()

    # 计算日期范围
    now = datetime.now(timezone.utc)
    date_from = (now - timedelta(days=days_back)).strftime("%Y%m%d")
    date_to = now.strftime("%Y%m%d")
    print(f"[Fetcher] 查询日期范围: {date_from} ~ {date_to} (回溯{days_back}天)")

    all_papers: dict[str, Paper] = {}  # 用URL去重

    for category in categories:
        query = f"cat:{category} AND submittedDate:[{date_from}0000 TO {date_to}2359]"

        client = arxiv.Client()
        search = arxiv.Search(
            query=query,
            max_results=max_results,
            sort_by=arxiv.SortCriterion.SubmittedDate,
            sort_order=arxiv.SortOrder.Descending,
        )

        for result in client.results(search):
            url = result.entry_id
            if url not in all_papers:
                all_papers[url] = Paper(
                    title=result.title.replace("\n", " ").strip(),
                    authors=[a.name for a in result.authors],
                    abstract=result.summary.replace("\n", " ").strip(),
                    url=url,
                    pdf_url=result.pdf_url,
                    categories=[c for c in result.categories],
                    published=result.published,
                    primary_category=result.primary_category,
                )

    papers = list(all_papers.values())
    papers.sort(key=lambda p: p.published, reverse=True)

    print(f"[Fetcher] 从 {len(categories)} 个分类中抓取到 {len(papers)} 篇论文")
    return papers
