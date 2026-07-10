# Group Digest

> 提取各类网页群聊记录，生成 Markdown 和每日精华摘要，并可自动发布到飞书文档。  
> Export web chat messages to Markdown, generate highlight digests, and optionally publish them to Feishu/Lark Docs.

Group Digest 通过浏览器页面读取平台的群聊内容，提炼里面的精华内容做成markdown文档，可用于AI录入知识库或生成社群周报，还可以一个命令做成文档上传至飞书。

Group Digest reads group chat content from platforms via browser pages, extracts core highlights and compiles them into Markdown documents. These documents can be imported into AI knowledge bases or used to generate community weekly reports, and can also be created and uploaded to Lark with a single command.

## 功能亮点 / Highlights

- 滚动网页聊天页时增量提取消息  
  Extract messages while scrolling the web chat page
- 实时写入原始 Markdown  
  Write raw messages to Markdown incrementally
- 使用本地 `seen.json` 跨次运行去重  
  Deduplicate messages across runs with a local `seen.json`
- 从原始记录生成本地精华摘要  
  Generate a local highlight digest from extracted messages
- 通过 `lark-cli` 发布到飞书/Lark 文档  
  Publish the digest to Feishu/Lark Docs via `lark-cli`
- Windows 可用，通过 Chrome DevTools Protocol 控制浏览器  
  Windows-ready through Chrome DevTools Protocol

## 支持平台 / Supported Platforms

| 平台 / Platform | 参数 / `--platform` | 默认匹配标签页 / Tab match |
| --- | --- | --- |
| 抖音 / Douyin | `douyin` | `douyin.com` |
| Telegram Web | `telegram` / `tg` | `web.telegram.org` |
| X / Twitter 私信 | `twitter` / `x` | `x.com`, `twitter.com` |
| 微信网页版 / WeChat Web | `wechat` / `wx` | `web.wechat.com`, `wx.qq.com` |
| QQ 网页版 / QQ Web | `qq` | `qq.com` |
| 通用网页聊天 / Generic web chat | `generic` | first debuggable tab |

微信和 QQ 是否可用取决于官方网页端是否支持你的账号。本项目不会绕过登录、权限或平台限制。

WeChat and QQ depend on whether the official web version is available for your account. This project does not bypass login, permissions, or platform restrictions.

## 快速开始 / Quick Start

环境要求 / Requirements:

- Python 3.9+
- Google Chrome
- Windows PowerShell

启动带调试端口的 Chrome / Start Chrome with a debuggable profile:

```powershell
powershell -ExecutionPolicy Bypass -File .\start_chrome_debug.ps1 -Url "https://web.telegram.org/a/"
```

登录账号并打开目标群聊后运行 / Log in, open the target chat, then run:

```powershell
python .\extract.py --platform telegram --output .\telegram_raw.md
```

生成本地摘要 / Create a local digest:

```powershell
python .\extract.py --platform telegram --output .\telegram_raw.md --create-digest
```

生成摘要并发布到飞书 / Create and publish a digest to Feishu/Lark Docs:

```powershell
python .\extract.py `
  --platform telegram `
  --output .\telegram_raw.md `
  --create-digest `
  --digest-output .\telegram_digest.md `
  --publish-feishu `
  --feishu-title "Telegram Group Digest"
```

## 使用示例 / Examples

```powershell
# 抖音：按群名点击后提取
# Douyin: click the group by exact name before extraction
python .\extract.py --platform douyin --group "Your Group Name" --output .\douyin_raw.md

# Telegram：提取当前打开的聊天页
# Telegram: extract the currently opened chat
python .\extract.py --platform telegram --output .\telegram_raw.md

# X / Twitter 私信
# X / Twitter DM
python .\extract.py --platform twitter --output .\twitter_dm_raw.md

# 通用模式：适配其他网页聊天
# Generic fallback for other web chats
python .\extract.py --platform generic --tab-match "example.com" --output .\chat_raw.md
```

## 飞书/Lark 配置 / Feishu/Lark Setup

安装官方 CLI / Install the official CLI:

```powershell
powershell -ExecutionPolicy Bypass -File .\setup_feishu_cli.ps1
```

配置并授权 / Configure and authorize:

```powershell
lark-cli config init
lark-cli auth login --recommend
lark-cli auth status
```

当 `auth status` 显示 user identity ready 后，即可使用 `--publish-feishu` 创建飞书文档。

After `auth status` shows a ready user identity, `--publish-feishu` can create documents.

More details: [FEISHU.md](FEISHU.md)

## 常用参数 / Common Options

```text
--platform, -p       平台：douyin / telegram / twitter / wechat / qq / generic
                     Platform adapter
--group, -g          可选，提取前按群聊名称点击
                     Optional chat name to click before extraction
--output, -o         原始 Markdown 输出路径
                     Raw Markdown output path
--seen               去重状态 JSON 文件
                     JSON deduplication state
--create-digest      提取后生成本地摘要
                     Generate a local digest after extraction
--digest-output      摘要 Markdown 输出路径
                     Digest Markdown output path
--digest-max-items   摘要最多条目数
                     Maximum digest bullet count
--publish-feishu     通过 lark-cli 发布摘要
                     Publish digest through lark-cli
--feishu-title       飞书/Lark 文档标题
                     Feishu/Lark document title
--tab-match          浏览器标签页匹配关键词，支持逗号分隔
                     Comma-separated browser tab keywords
--step               每次滚动像素，默认 500
                     Scroll step in pixels, default 500
--list-platforms     查看内置平台适配器
                     List built-in platform adapters
```

## 工作原理 / How It Works

脚本连接本机 Chrome DevTools 端点 `127.0.0.1:9222`，找到目标标签页，注入小段 JavaScript 来滚动页面并读取 DOM 文本，然后把新消息写入 Markdown。

The script connects to Chrome through the local DevTools endpoint at `127.0.0.1:9222`, finds the target tab, injects small JavaScript snippets to scroll and read DOM text, then writes each new message to Markdown.

如果某个平台前端结构发生变化，可以先尝试 `--platform generic`，或在 `extract.py` 中调整对应平台的选择器。

If a platform changes its DOM, try `--platform generic` first or adjust the selectors in `extract.py`.

## 隐私说明 / Privacy

浏览器登录态、聊天记录、摘要文件、飞书授权二维码和本地日志都已加入 `.gitignore`。上传或分享前，请自行检查生成的 Markdown 内容。

Browser profiles, extracted messages, digest files, Feishu auth QR codes, and local logs are ignored by `.gitignore`. Review generated Markdown before sharing or committing anything.

## 许可证 / License

MIT
