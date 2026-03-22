# Daily Paper

**arXiv 每日论文追踪器** — 自动抓取、智能筛选、LLM 摘要、深度总结，一站式科研论文阅读工具。

**Daily arXiv Paper Tracker** — Automated fetching, smart filtering, LLM-powered summarization, and deep analysis for your daily research reading.

---

## Features / 功能特性

- **Automated Fetching** / 自动抓取 — Pull papers from multiple arXiv categories daily
- **Smart Filtering** / 智能筛选 — Keyword matching with synonym expansion + exclusion rules to reduce noise
- **LLM Summarization** / LLM 摘要 — Concurrent AI-powered one-line summaries and topic classification
- **Deep Summary** / 深度总结 — Select papers for full PDF-based deep analysis (research motivation, methods, results, pros/cons)
- **Daily Overview** / 每日综合报告 — Cross-paper research trend analysis and future direction suggestions
- **Web UI** / 网页界面 — Mobile-friendly interface for browsing and selecting papers
- **Multi-format Output** / 多格式输出 — Markdown + PDF reports
- **Email Notification** / 邮件通知 — Optional email delivery of daily reports
- **Deduplication** / 去重机制 — Skip regeneration if the report for a target date already exists

## Architecture / 架构概览

```
main.py                     # Entry point: fetch → filter → summarize → report
├── fetcher.py              # arXiv API client, Paper dataclass
├── filter.py               # Keyword matching, synonym expansion, exclusion rules
├── summarizer.py           # LLM concurrent summarization + topic classification
├── reporter.py             # Markdown + PDF report generation
├── notifier.py             # Email notification (SMTP)
├── deep_summary.py         # PDF-based deep analysis with daily overview
├── server.py               # Flask web server for browsing + deep summary
├── config.example.yaml     # Configuration template
└── templates/
    ├── index.html          # Paper list with category folding + checkboxes
    └── deep_result.html    # Deep summary results with progress bar
```

## Pipeline / 工作流程

```
Auto compute target_date (Beijing Time)
        │
        ▼
  Dedup check ──── exists? ──→ Reuse report & exit
        │ (no)
        ▼
  Fetch from arXiv (multi-category, configurable lookback)
        │
        ▼
  Filter by date (target_date only)
        │
        ▼
  Smart keyword filter (include + exclude + synonym expansion)
        │
        ▼
  LLM classify + summarize (concurrent, 4 topic categories)
        │
        ▼
  Generate report (Markdown + PDF)
        │
        ▼
  Email notification (optional)
        │
        ▼
  Web server (browse + select papers for deep summary)
        │
        ▼
  Deep summary (download PDF → base64 → LLM analysis → daily overview)
```

## Date Rules / 日期规则

All dates use **Beijing Time (UTC+8)**. The target date determines which papers to recommend:

| Today (BJT) | Target Date | Explanation |
|-------------|-------------|-------------|
| Tue–Fri | Yesterday | 周二至周五推荐前一天的论文 |
| Monday | Last Friday | 周一推荐上周五的论文 |
| Saturday | Thursday | 周六推荐周四的论文 |
| Sunday | Thursday | 周日推荐周四的论文 |

Output filenames always match the target date (e.g., running on 2026-03-22 for 2026-03-19 papers produces `2026-03-19.md`).

输出文件名始终与目标日期一致（例如在 3 月 22 日生成 3 月 19 日的论文，文件名为 `2026-03-19.md`）。

## Quick Start / 快速开始

### 1. Install / 安装

```bash
git clone https://github.com/yourname/Daily_Paper.git
cd Daily_Paper
pip install -r requirements.txt
```

### 2. Configure / 配置

```bash
cp config.example.yaml config.yaml
```

Edit `config.yaml` and fill in your LLM API settings:

编辑 `config.yaml`，填入你的 LLM API 配置：

```yaml
llm:
  base_url: "https://api.anthropic.com"   # Or any compatible endpoint
  api_key: "your-api-key-here"            # Or use api_key_env
  model: "claude-sonnet-4-20250514"       # Model name for your provider
```

### 3. Run / 运行

**Generate daily report / 生成日报：**

```bash
python main.py --no-email
```

**Launch web server / 启动网页服务：**

```bash
python server.py
```

Then open http://localhost:5000 in your browser (or access via LAN IP on mobile).

然后在浏览器打开 http://localhost:5000（手机可通过局域网 IP 访问）。

### 4. Deep Summary / 深度总结

1. Browse papers on the web UI, grouped by topic category
2. Check the papers you're interested in
3. Click **"Generate Deep Summary"**
4. Wait for PDF-based deep analysis (concurrent, ~1 min per paper)
5. View the daily research overview + individual paper analyses

---

1. 在网页上浏览按主题分类的论文列表
2. 勾选感兴趣的论文
3. 点击 **"Generate Deep Summary"**
4. 等待基于 PDF 的深度分析（并发处理，每篇约 1 分钟）
5. 查看每日综合研究报告 + 各论文详细分析

## CLI Options / 命令行参数

| Option | Description | Default |
|--------|-------------|---------|
| `--date YYYY-MM-DD` | Override target date (skip dedup) / 手动指定目标日期 | Auto |
| `--no-summary` | Skip LLM summarization / 跳过 LLM 摘要 | Off |
| `--no-email` | Skip email notification / 跳过邮件 | Off |
| `-c path` | Config file path / 配置文件路径 | `config.yaml` |

## Topic Categories / 论文分类

Papers are classified by the LLM into 4 categories:

论文由 LLM 自动分为 4 类：

| Category | Description |
|----------|-------------|
| **LLM/Large Multimodal Model** | LLMs, multimodal models, vision-language models / 大语言模型、多模态大模型 |
| **Video** | Video generation, understanding, editing / 视频生成、理解、编辑 |
| **Embodied** | Embodied AI, robotics, physical interaction / 具身智能、机器人 |
| **Other** | Everything else / 其他研究 |

## Output / 输出文件

| File | Description |
|------|-------------|
| `outputs/{date}.md` | Daily report (Markdown) / 日报 |
| `outputs/{date}.pdf` | Daily report (PDF) / 日报 PDF |
| `outputs/{date}_deep.md` | Deep summary (Markdown) / 深度总结 |
| `outputs/{date}_deep.pdf` | Deep summary (PDF) / 深度总结 PDF |

## Configuration / 配置说明

See `config.example.yaml` for full options. Key sections:

详见 `config.example.yaml`，主要配置项：

| Section | Description |
|---------|-------------|
| `arxiv.categories` | arXiv categories to track / 追踪的 arXiv 分类 |
| `filter.keywords` | Include keywords (with synonym expansion) / 包含关键词 |
| `filter.exclude_keywords` | Exclude keywords / 排除关键词 |
| `filter.exclude_categories` | Exclude arXiv tags / 排除标签 |
| `llm.*` | LLM API settings (url, key, model, concurrency) / LLM 配置 |
| `email.*` | SMTP email settings / 邮件配置 |

## Requirements / 依赖

- Python 3.10+
- [arxiv](https://pypi.org/project/arxiv/) — arXiv API client
- [anthropic](https://pypi.org/project/anthropic/) — Claude SDK (or any compatible API)
- [flask](https://pypi.org/project/Flask/) — Web server
- [fpdf2](https://pypi.org/project/fpdf2/) — PDF generation
- [pyyaml](https://pypi.org/project/PyYAML/) — Config parsing
- [markdown](https://pypi.org/project/Markdown/) — MD→HTML conversion

## License

MIT
