# ssq-checker

中国福利彩票双色球（SSQ）结果查询 + 中奖比对工具。**纯 Python stdlib，零运行时依赖。**

## 为什么有这个 repo

原本是 Hermes 上一个调 AI 的 cron job：抓官网 → 比对号码 → 发消息。但这件事根本不需要 AI 判断，规则全部硬编码就行。剥离成独立 repo 可以：

- 零 token 烧钱，跑得快、确定
- 可被多种调度方式调用：本地 cron、Hermes cron `no_agent=True` 模式、GitHub Actions
- 单测覆盖所有奖级，规则有问题立刻能查出来

## 数据源

`https://www.17500.cn/getData/ssq.TXT` — 唯一靠谱的、可 curl 直拉的双色球开奖数据源。`cwl.gov.cn` 官网会 403 屏蔽机房 IP，`datachart.500.com` 是 SPA 拉不到内容。详见 `chinese-lottery-data` 技能。

## 安装

```bash
pip install -e .
```

或不安装直接跑（无依赖）：

```bash
PYTHONPATH=src python -m ssq_checker
```

## 使用

默认就是 Logan 的固定号码（红 01 02 03 04 08 09，蓝 07）：

```bash
ssq-checker
```

自定义号码：

```bash
ssq-checker --reds 05 12 18 22 27 33 --blue 11
```

JSON 输出（适合管道/解析）：

```bash
ssq-checker --json
```

## 输出示例

```
🎱 双色球第2026070期开奖（06月21日）

🔴 红球：03 06 08 14 26 27
🔵 蓝球：08

你的号码：🔴 01 02 03 04 08 09  🔵 07
红球命中：2个（03 08）
蓝球命中：❌

中奖结论：未中奖
```

## 测试

```bash
pip install -e .[dev]
pytest -v
```

覆盖：每个奖级（一到六等奖、不中）+ 数据解析 + 数字规范化。

## 调度

### 本地 cron

```cron
0 22 * * 0,2,4  ssq-checker | tee -a ~/lottery.log
```

### Hermes cron（`no_agent=True`，零 token）

```python
cronjob(action='create', name='双色球',
        schedule='0 22 * * 0,2,4',
        no_agent=True,
        script='/home/logan/Projects/ssq-checker/run.sh',
        deliver='telegram:-1004407117408')
```

`run.sh` 内容：

```bash
#!/usr/bin/env bash
exec /home/logan/Projects/ssq-checker/venv/bin/ssq-checker
```

### GitHub Actions

见 `.github/workflows/draw.yml`。注意：GH Actions schedule 触发延迟 5-15 分钟，对于 22:00 的播报不算严重，但要追求精确投递时间还是用本地调度更稳。

## 奖级表（参考）

| 红球命中 | 蓝球命中 | 奖级 | 金额 |
|---------|---------|------|------|
| 6 | ✅ | 一等奖 | 奖池/浮动 |
| 6 | ❌ | 二等奖 | 奖池/浮动 |
| 5 | ✅ | 三等奖 | ¥3,000 |
| 5 | ❌ | 四等奖 | ¥200 |
| 4 | ✅ | 四等奖 | ¥200 |
| 4 | ❌ | 五等奖 | ¥10 |
| 3 | ✅ | 五等奖 | ¥10 |
| 2 | ✅ | 六等奖 | ¥5 |
| 1 | ✅ | 六等奖 | ¥5 |
| 0 | ✅ | 六等奖 | ¥5 |

## License

MIT
