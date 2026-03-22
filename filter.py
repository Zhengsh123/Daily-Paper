"""论文筛选模块 - 模糊匹配 + 同义词扩展 + 排除规则"""

import re
from fetcher import Paper

# 内置同义词表：用户写任意一个，自动扩展匹配所有相关变体
BUILTIN_ALIASES = {
    "LLM": ["large language model", "large language models", "LLMs"],
    "large language model": ["LLM", "LLMs", "large language models"],
    "diffusion": ["diffusion model", "diffusion models", "denoising diffusion"],
    "multimodal": ["multi-modal", "multi modal", "multimodality"],
    "RAG": ["retrieval augmented generation", "retrieval-augmented"],
    "GAN": ["generative adversarial network", "generative adversarial networks", "GANs"],
    "RL": ["reinforcement learning"],
    "reinforcement learning": ["RL"],
    "transformer": ["transformers", "self-attention"],
    "video": ["video generation", "video understanding", "video synthesis"],
    "agent": ["agents", "agentic", "multi-agent"],
    "VLM": ["vision language model", "vision-language model", "VLMs"],
    "NLP": ["natural language processing"],
    "CV": ["computer vision"],
    "3D": ["3d", "three-dimensional", "NeRF", "gaussian splatting"],
    "robot": ["robotics", "robotic", "manipulation", "locomotion"],
}


def _expand_keywords(keywords: list[str], custom_aliases: dict[str, list[str]] | None = None) -> list[str]:
    """将关键词列表通过同义词表扩展"""
    merged_aliases = {k.lower(): [v.lower() for v in vs] for k, vs in BUILTIN_ALIASES.items()}
    if custom_aliases:
        for k, vs in custom_aliases.items():
            key = k.lower()
            existing = merged_aliases.get(key, [])
            merged_aliases[key] = list(set(existing + [v.lower() for v in vs]))

    expanded = set()
    for kw in keywords:
        expanded.add(kw.lower())
        # 查找同义词
        kw_lower = kw.lower()
        if kw_lower in merged_aliases:
            expanded.update(merged_aliases[kw_lower])

    return list(expanded)


def _build_patterns(keywords: list[str]) -> list[re.Pattern]:
    """构建模糊匹配正则：支持通配符 * 和子串匹配"""
    patterns = []
    for kw in keywords:
        if "*" in kw:
            # 通配符模式: "diffus*" -> "diffus\w*"
            regex = re.escape(kw).replace(r"\*", r"\w*")
        else:
            # 默认子串匹配（不要求全词边界）
            regex = re.escape(kw)
        patterns.append(re.compile(regex, re.IGNORECASE))
    return patterns


def filter_papers(papers: list[Paper], config: dict) -> list[Paper]:
    """
    根据配置筛选论文：关键词包含匹配 + 排除匹配。

    config.filter 支持:
      keywords: 包含关键词列表
      mode: "any" | "all"
      exclude_keywords: 排除关键词列表（命中任一则排除）
      aliases: 自定义同义词映射
    """
    filter_cfg = config.get("filter", {})
    keywords = filter_cfg.get("keywords", [])
    mode = filter_cfg.get("mode", "any")
    exclude_keywords = filter_cfg.get("exclude_keywords", [])
    exclude_categories = set(filter_cfg.get("exclude_categories", []))
    custom_aliases = filter_cfg.get("aliases", {})

    # 获取用户配置的 arXiv 分类列表
    allowed_categories = set(config.get("arxiv", {}).get("categories", []))

    before = len(papers)

    # --- 第零步：primary_category 必须在配置的分类列表内 ---
    if allowed_categories:
        kept = [p for p in papers if p.primary_category in allowed_categories]
        removed = before - len(kept)
        if removed:
            print(f"[Filter] 分类过滤: 移除 {removed} 篇 (primary_category 不在 {sorted(allowed_categories)} 中)")
        papers = kept

    # --- 第〇.五步：排除带有特定标签的论文（检查所有 categories，不只是 primary） ---
    if exclude_categories:
        kept = [p for p in papers if not (set(p.categories) & exclude_categories)]
        removed = len(papers) - len(kept)
        if removed:
            print(f"[Filter] 标签排除: 移除 {removed} 篇 (含标签 {sorted(exclude_categories)})")
        papers = kept

    # --- 第一步：排除不需要的领域 ---
    if exclude_keywords:
        exclude_expanded = _expand_keywords(exclude_keywords, custom_aliases)
        exclude_patterns = _build_patterns(exclude_expanded)
        kept = []
        for paper in papers:
            text = f"{paper.title} {paper.abstract}"
            if not any(p.search(text) for p in exclude_patterns):
                kept.append(paper)
        excluded_count = len(papers) - len(kept)
        papers = kept
        print(f"[Filter] 排除规则: 移除 {excluded_count} 篇 (exclude={exclude_keywords})")

    # --- 第二步：关键词包含匹配 ---
    if keywords:
        expanded = _expand_keywords(keywords, custom_aliases)
        patterns = _build_patterns(expanded)

        filtered = []
        for paper in papers:
            text = f"{paper.title} {paper.abstract}"
            matches = [p.search(text) is not None for p in patterns]

            if mode == "all" and all(matches):
                filtered.append(paper)
            elif mode == "any" and any(matches):
                filtered.append(paper)

        papers = filtered
        print(f"[Filter] 关键词匹配: {before} -> {len(papers)} 篇 "
              f"(mode={mode}, keywords={keywords}, 扩展后共 {len(expanded)} 个匹配词)")
    else:
        print(f"[Filter] 未设置关键词，保留全部 {len(papers)} 篇")

    return papers
