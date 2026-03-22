"""LLM摘要总结模块 - 通过 Anthropic SDK 调用，支持并发"""

import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
import anthropic
from fetcher import Paper


SUMMARIZE_PROMPT = """你是一位AI研究论文分析专家。请对以下arXiv论文进行分类和总结。

论文标题: {title}
论文摘要: {abstract}

请用{language}按以下格式输出:

**分类**: （从以下四个类别中选一个：LLM/Large Multimodal Model, Video, Embodied, Other）
分类说明：
- LLM/Large Multimodal Model：关于大语言模型、多模态大模型、视觉语言模型的研究
- Video：关于视频生成、视频理解、视频编辑等视频相关的研究
- Embodied：关于具身智能、机器人、物理交互等具身相关的研究
- Other：不属于以上三类的其他研究

**一句话总结**: （用一句话概括这篇论文的核心贡献）

**关键创新点**:
- （创新点1）
- （创新点2）

**潜在应用**: （简述该研究的潜在应用场景）
"""

# 有效分类标签
VALID_CATEGORIES = ["LLM/Large Multimodal Model", "Video", "Embodied", "Other"]


class Summarizer:
    """
    LLM 摘要总结器。
    通过 Anthropic SDK 调用，支持自定义 base_url 和并发请求。
    """

    def __init__(self, base_url: str, api_key: str, model: str,
                 max_tokens: int = 1024, language: str = "中文", concurrency: int = 5):
        self.model = model
        self.max_tokens = max_tokens
        self.language = language
        self.concurrency = concurrency
        self.client = anthropic.Anthropic(base_url=base_url, api_key=api_key)

    def _call_api(self, prompt: str) -> str:
        message = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text

    def summarize(self, paper: Paper) -> str:
        prompt = SUMMARIZE_PROMPT.format(
            title=paper.title,
            abstract=paper.abstract,
            language=self.language,
        )
        return self._call_api(prompt)

    def _parse_category(self, text: str) -> str:
        """从 LLM 返回文本中解析分类标签"""
        m = re.search(r'\*\*分类\*\*\s*[:：]\s*(.+)', text)
        if m:
            raw = m.group(1).strip()
            for cat in VALID_CATEGORIES:
                if cat.lower() in raw.lower():
                    return cat
        return "Other"

    def _strip_category_line(self, text: str) -> str:
        """从 summary 文本中去除分类行"""
        return re.sub(r'\*\*分类\*\*\s*[:：].*\n*', '', text).lstrip('\n')

    def _summarize_one(self, index: int, total: int, paper: Paper) -> tuple[int, Paper]:
        """总结单篇论文（供线程池调用）"""
        print(f"[Summarizer] 正在总结 ({index+1}/{total}): {paper.title[:60]}...")
        try:
            result = self.summarize(paper)
            paper.category = self._parse_category(result)
            paper.summary = self._strip_category_line(result)
        except Exception as e:
            print(f"[Summarizer] 总结失败 ({index+1}/{total}): {e}")
            paper.summary = f"*总结生成失败: {e}*"
            paper.category = "Other"
        return index, paper

    def summarize_batch(self, papers: list[Paper]) -> list[Paper]:
        """并发批量生成论文摘要"""
        total = len(papers)
        print(f"[Summarizer] 开始并发总结 {total} 篇论文 (concurrency={self.concurrency})")

        with ThreadPoolExecutor(max_workers=self.concurrency) as executor:
            futures = {
                executor.submit(self._summarize_one, i, total, paper): i
                for i, paper in enumerate(papers)
            }
            done_count = 0
            for future in as_completed(futures):
                done_count += 1
                idx, _ = future.result()
                if done_count % 10 == 0:
                    print(f"[Summarizer] 进度: {done_count}/{total}")

        print(f"[Summarizer] 全部完成: {total} 篇")
        return papers


def create_summarizer(config: dict) -> Summarizer:
    """根据配置创建摘要总结器"""
    llm = config.get("llm", {})

    base_url = llm.get("base_url", "https://api.anthropic.com")
    api_key = llm.get("api_key", "")
    if not api_key:
        api_key_env = llm.get("api_key_env", "LLM_API_KEY")
        api_key = os.environ.get(api_key_env, "")
    model = llm.get("model", "claude-sonnet-4-20250514")
    max_tokens = llm.get("max_tokens", 1024)
    language = llm.get("language", "中文")
    concurrency = llm.get("concurrency", 5)

    if not api_key:
        raise ValueError("未找到 API Key，请在 config.yaml 中设置 api_key 或 api_key_env")

    print(f"[Summarizer] base_url={base_url}, model={model}, concurrency={concurrency}")
    return Summarizer(
        base_url=base_url,
        api_key=api_key,
        model=model,
        max_tokens=max_tokens,
        language=language,
        concurrency=concurrency,
    )
