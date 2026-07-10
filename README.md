# Group Digest

> 提取各类平台群聊记录，用 AI/本地规则生成每日精华摘要，并发布到飞书文档。

Export messages from web chat pages, turn them into clean Markdown, generate a local highlight digest, and optionally publish the digest to Feishu/Lark Docs.

The tool works from your logged-in browser session. No browser extension, no unofficial API token, no Python dependencies.

## What It Does

- Extracts visible chat history while scrolling the web chat page
- Writes raw messages to Markdown incrementally
- Deduplicates messages across runs with a local `seen.json`
- Generates a lightweight local digest from the extracted Markdown
- Publishes the digest to Feishu/Lark Docs through `lark-cli`
- Supports Windows by using Chrome DevTools Protocol instead of macOS AppleScript

## Supported Platforms

| Platform | `--platform` | Default tab match |
| --- | --- | --- |
| Douyin | `douyin` | `douyin.com` |
| Telegram Web | `telegram` / `tg` | `web.telegram.org` |
| X / Twitter DM | `twitter` / `x` | `x.com`, `twitter.com` |
| WeChat Web | `wechat` / `wx` | `web.wechat.com`, `wx.qq.com` |
| QQ Web | `qq` | `qq.com` |
| Any web chat | `generic` | first debuggable tab |

WeChat and QQ depend on whether the official web version is available for your account. This project does not bypass login, permissions, or platform restrictions.

## Quick Start

Requirements:

- Python 3.9+
- Google Chrome
- Windows PowerShell for `start_chrome_debug.ps1`

Start Chrome with a debuggable profile:

```powershell
powershell -ExecutionPolicy Bypass -File .\start_chrome_debug.ps1 -Url "https://web.telegram.org/a/"
```

Log in, open the target chat, then run:

```powershell
python .\extract.py --platform telegram --output .\telegram_raw.md
```

Create a digest:

```powershell
python .\extract.py --platform telegram --output .\telegram_raw.md --create-digest
```

Publish the digest to Feishu/Lark Docs:

```powershell
python .\extract.py `
  --platform telegram `
  --output .\telegram_raw.md `
  --create-digest `
  --digest-output .\telegram_digest.md `
  --publish-feishu `
  --feishu-title "Telegram Group Digest"
```

## Platform Examples

```powershell
# Douyin, click a group by exact name first
python .\extract.py --platform douyin --group "Your Group Name" --output .\douyin_raw.md

# Telegram, extract the currently opened chat
python .\extract.py --platform telegram --output .\telegram_raw.md

# X / Twitter DM
python .\extract.py --platform twitter --output .\twitter_dm_raw.md

# Generic fallback for other web chats
python .\extract.py --platform generic --tab-match "example.com" --output .\chat_raw.md
```

## Feishu/Lark Setup

Install the official CLI:

```powershell
powershell -ExecutionPolicy Bypass -File .\setup_feishu_cli.ps1
```

Configure and authorize:

```powershell
lark-cli config init
lark-cli auth login --recommend
lark-cli auth status
```

After `auth status` shows a ready user identity, `--publish-feishu` can create documents.

See [FEISHU.md](FEISHU.md) for details.

## Common Options

```text
--platform, -p       douyin / telegram / twitter / wechat / qq / generic
--group, -g          optional chat name to click before extraction
--output, -o         raw Markdown output
--seen               JSON deduplication state
--create-digest      generate a local digest after extraction
--digest-output      digest Markdown output path
--digest-max-items   maximum digest bullet count
--publish-feishu     publish digest through lark-cli
--feishu-title       Feishu/Lark document title
--tab-match          comma-separated browser tab keywords
--step               scroll step in pixels, default 500
--list-platforms     list built-in platform adapters
```

## How It Works

The script connects to Chrome through the local DevTools endpoint at `127.0.0.1:9222`, finds the target tab, injects small JavaScript snippets to scroll and read DOM text, then writes each new message to Markdown.

This is intentionally simple. It works best when the chat page is already open and loaded. If a platform changes its DOM, try `--platform generic` or adjust the selectors in `extract.py`.

## Privacy

Your browser profile, extracted messages, digest files, Feishu auth QR codes, and local logs are ignored by `.gitignore`. Review generated Markdown before sharing or committing anything.

## License

MIT
"# tzfilm-Group-Digest-windows-" 
