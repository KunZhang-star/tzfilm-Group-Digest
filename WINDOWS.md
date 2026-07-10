# Windows Guide

## 1. Start Chrome

```powershell
powershell -ExecutionPolicy Bypass -File .\start_chrome_debug.ps1 -Url "https://www.douyin.com/chat"
```

Other useful URLs:

```powershell
powershell -ExecutionPolicy Bypass -File .\start_chrome_debug.ps1 -Url "https://web.telegram.org/a/"
powershell -ExecutionPolicy Bypass -File .\start_chrome_debug.ps1 -Url "https://x.com/messages"
```

The script creates a local `.chrome-profile` folder and starts Chrome with:

```text
http://127.0.0.1:9222
```

## 2. Open a Chat

Log in inside that Chrome window, then open the target group chat or DM.

## 3. Extract Messages

```powershell
python .\extract.py --platform telegram --output .\telegram_raw.md
```

## 4. Extract and Publish to Feishu

```powershell
python .\extract.py `
  --platform telegram `
  --output .\telegram_raw.md `
  --create-digest `
  --digest-output .\telegram_digest.md `
  --publish-feishu `
  --feishu-title "Telegram Group Digest"
```

## Supported Platform Values

- `douyin`
- `telegram`
- `twitter`
- `wechat`
- `qq`
- `generic`
