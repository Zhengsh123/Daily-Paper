# Skill: 每日论文推荐

当用户说"推荐文章"、"推荐论文"、"今天有什么论文"等类似语句时，执行以下流程。

## 执行步骤

### Step 1: 生成日报（main.py）

```bash
cd D:/Code/python/Vibe/Daily_Paper
python main.py --no-email
```

- 自动按北京时间计算 target_date，所有文件名与 target_date 一致
- 已存在 `outputs/{target_date}.md` 时自动复用，不重复生成

### Step 2: 启动 Web 服务（server.py）

```bash
cd D:/Code/python/Vibe/Daily_Paper
python server.py
```

- 后台运行，自动加载 target_date 对应的报告
- 电脑访问 http://127.0.0.1:5000，手机访问 http://<电脑IP>:5000
- 用户在网页上勾选论文后可触发深度总结

### Step 3: 告知用户

告诉用户：
1. 今天推荐的是哪天（target_date）的论文、共几篇
2. Web 服务地址
3. 可在网页勾选论文生成深度总结（基于 PDF 的详细分析）

## 日期规则（北京时间 UTC+8）

| 今天 | target_date |
|------|-------------|
| 周二~周五 | 昨天 |
| 周一 | 上周五 |
| 周六 | 周四 |
| 周日 | 周四 |

## 参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--date YYYY-MM-DD` | 手动指定目标日期（跳过去重） | 空（自动） |
| `--no-summary` | 跳过 LLM 分类+摘要 | 关闭 |
| `--no-email` | 跳过邮件发送 | 关闭 |

## 输出文件

| 文件 | 说明 |
|------|------|
| `outputs/{target_date}.md` | 日报 Markdown |
| `outputs/{target_date}.pdf` | 日报 PDF |
| `outputs/{target_date}_deep.md` | 深度总结 Markdown（网页触发后生成） |
| `outputs/{target_date}_deep.pdf` | 深度总结 PDF（网页触发后生成） |

## 注意事项

- 已存在的目标日期报告直接复用（`--date` 手动模式除外）
- server.py 按 target_date 加载对应报告，不是取最新文件
- 深度总结先下载 arXiv PDF，再以 base64 传给 LLM 分析
- LLM 配置在 `config.yaml` 的 `llm` 段
- PDF 渲染依赖 Windows 系统字体 `C:/Windows/Fonts/simhei.ttf`
