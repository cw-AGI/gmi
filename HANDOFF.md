# GMI 项目交接文档（给 Claude Code）

这是一个已经写好、本地验证通过的项目，现在需要你帮忙完成 **GitHub 部署**。
代码不用改，主要做仓库创建、推送、配置和触发首次运行。

---

## 一、项目是什么

**GMI · 全球股市情报终端** —— 每日自动抓取 A股 / 港股 / 美股 的指数、新闻、企业动态、新股 IPO，
按关注赛道（AI / 科技 / 能源 / 太空 / 通信 / 生物科学）优先排序，单页面展示。

架构：**GitHub Actions 定时抓取 → 写静态 JSON → GitHub Pages 托管单文件页面**。
全程免费、无后端、无数据库。

## 二、文件清单

```
index.html              单文件前端（零依赖 vanilla JS，中英双语，localStorage，红涨绿跌）
fetch_data.py           数据抓取脚本（Finnhub 抓美股 + akshare 抓 A股/港股）
requirements.txt        Python 依赖（akshare / requests / pandas）
.github/workflows/fetch.yml   定时任务（cron）+ 手动触发
data/cn.json            A股数据（脚本自动覆盖更新）
data/hk.json            港股数据
data/us.json            美股数据
README.md               面向用户的部署说明
```

## 三、技术要点（已实现，勿改坏）

- **前端**：`index.html` 用 `fetch('./data/{cn,hk,us}.json')` 读数据；读不到时回退到内置 `SAMPLE`。
  顶部有市场 Tab（A股/港股/美股）+ 赛道筛选条；四个面板：指数概览 / 每日新闻 / 企业动态 / 新股 IPO。
- **赛道机制**：`fetch_data.py` 顶部 `SECTORS`（关键词）和 `US_WATCH`（美股重点个股清单）。
  每条数据按关键词打 `sectors` 标签，命中关注赛道的排到最前。
- **容错**：每个数据块独立 try/except；抓取失败时**保留上一次成功的 JSON**，不写空覆盖。
  已本地验证：所有接口失败时脚本零崩溃、数据不丢。

## 四、需要你做的 GitHub 部署步骤

> 假设用户已装好 git / gh CLI 并已登录。如果没有，先引导安装 `gh` 并 `gh auth login`。

1. **创建仓库并推送**（仓库名可与用户确认，默认 `gmi`，需 Public 才能用免费 Pages）
   ```bash
   cd <项目目录>
   git init
   git add .
   git commit -m "init: GMI 全球股市情报终端"
   gh repo create gmi --public --source=. --push
   ```
   ⚠️ 确认 `.github/workflows/fetch.yml` 这个路径原样推上去了，不要改动目录结构。

2. **设置 Finnhub API Key 为仓库 Secret**（美股数据需要，名字必须叫 `FINNHUB_API_KEY`）
   - 用户需先去 https://finnhub.io 注册拿免费 key，然后：
   ```bash
   gh secret set FINNHUB_API_KEY
   # 粘贴 key 回车
   ```

3. **开启 Actions 写权限**（脚本要 commit 数据回仓库）
   - 这一步 gh CLI 不好直接设，请引导用户在网页操作：
     Settings → Actions → General → Workflow permissions → 选 **Read and write permissions** → Save。

4. **开启 GitHub Pages**
   ```bash
   # 网页操作更稳：Settings → Pages → Source 选 main 分支 / root → Save
   # 或用 API（需确认 gh 版本支持）
   ```
   页面地址：`https://<用户名>.github.io/gmi/`

5. **手动触发首次抓取验证**
   ```bash
   gh workflow run fetch.yml
   gh run watch          # 看运行结果
   ```
   - 跑完后 `data/*.json` 会被自动更新并 commit。
   - **预期**：美股（Finnhub）一般成功；A股/港股（akshare）若报 403/超时是东财对境外节点的反爬，属正常，脚本会保留旧数据，不算失败。

## 五、可能踩的坑

- **Pages 没生效**：仓库必须 Public（免费版），且 Source 要选对分支/目录，等 1-2 分钟。
- **Actions 跑了但没 commit**：多半是第 3 步写权限没开。
- **A股/港股长期抓不到**：akshare 在 GitHub Actions（美国节点）抓东财偶尔被墙。
  备选方案：在 workflow 里加代理，或把 akshare 换成直连 HTTP 接口。先观察几次再说。
- **美股抓不到**：检查 `FINNHUB_API_KEY` secret 是否设对。

## 六、后续可做（非部署必需）

- 港股的新闻/新股目前留空，后续可接港交所披露易（HKEX）公开数据。
- 美股新闻是英文，可在脚本里接翻译 API 补中文。
- 赛道关键词 / 美股个股清单按用户实际关注细化（改 `fetch_data.py` 顶部即可）。
