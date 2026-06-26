# GMI · 全球股市情报终端

每日自动抓取 **A股 / 港股 / 美股** 的指数、新闻、企业动态、新股 IPO，
单文件页面 + GitHub Actions 定时抓取 + GitHub Pages 托管，**全程免费、无后端**。

```
index.html              单文件页面（零依赖，可直接双击打开预览）
fetch_data.py           数据抓取脚本（Finnhub + akshare，容错设计）
requirements.txt        Python 依赖
.github/workflows/      GitHub Actions 定时任务
data/{cn,hk,us}.json    各市场数据（脚本自动生成/更新）
```

## 部署步骤

1. **新建一个 GitHub 仓库**，把这些文件全部传上去。

2. **申请 Finnhub 免费 Key**（美股数据用）：
   - 去 https://finnhub.io 注册，拿到 API Key
   - 仓库 → Settings → Secrets and variables → Actions → New repository secret
   - Name 填 `FINNHUB_API_KEY`，Value 填你的 key

3. **开启 GitHub Pages**：
   - 仓库 → Settings → Pages → Source 选 `main` 分支根目录
   - 几分钟后访问 `https://你的用户名.github.io/仓库名/`

4. **开启 Actions 写权限**：
   - Settings → Actions → General → Workflow permissions
   - 选 `Read and write permissions`

5. **手动跑一次**验证：Actions → 每日抓取股市数据 → Run workflow

之后脚本会按 `.github/workflows/fetch.yml` 里的时间自动跑：
A股收盘后(北京15:30)、港股收盘后(16:00)、美股开盘(美东09:00)各一次。

## 数据源

| 市场 | 来源 | 说明 |
|------|------|------|
| 美股 | Finnhub 免费版 | 市场新闻、IPO 日历、财报日历，最稳 |
| A股  | akshare（封装东财/新浪） | 指数、全球快讯、新股申购、概念板块 |
| 港股 | akshare | 恒指等指数（新闻/新股待完善） |

## 行业优先（重点关注：AI / 科技 / 能源 / 太空 / 通信 / 生物科学）

每条新闻、企业动态、新股都会按关键词自动打上**赛道标签**，命中关注赛道的条目**排到最前**（不丢弃其它内容）。页面顶部有赛道筛选条，点一下只看该赛道。

- **美股**：额外按赛道维护重点个股清单（如 NVDA / RKLB / FSLR / MRNA…），抓 company-news —— 这是真正的行业内容，而非大盘噪音。
- **A股**：额外抓概念板块，挑出关注赛道里的热门板块，显示在「指数概览」下方。
- 赛道关键词、美股个股清单都在 `fetch_data.py` 顶部 `SECTORS` / `US_WATCH`，随时可改。

## 已知限制与后续可做

- **akshare 在境外节点（GitHub Actions 美国服务器）抓国内接口偶尔会 403/超时**。
  脚本已做容错：任一接口失败 → 保留上次成功的数据，不会写空覆盖。
  若失败频繁，可在 Action 里加代理，或改用直连 HTTP 接口。
- **港股的新闻 / 新股**目前留空，后续可接港交所披露易（HKEX）的公开数据。
- **美股新闻是英文**，页面中英切换时英文条目两栏都显示原文（未翻译）。
  如需中文，可在脚本里接入翻译 API。
- Finnhub 免费版**不含**国际行情，所以 A股/港股不能用它，已分别用 akshare。

## 本地预览

直接双击 `index.html` 即可——抓取不到 `data/*.json` 时会自动用内置示例数据渲染。
