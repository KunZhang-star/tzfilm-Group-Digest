---
name: douyin-group-digest
description: Extract Douyin group chat messages, generate AI daily digests, publish to Feishu Docs. Runs as a daily cron job.
tags: [douyin, feishu, chat, digest, cron]
---

# Douyin Group Chat Daily Digest

Extract Douyin group chat messages → AI summary → Feishu Doc.

## Prerequisites

- macOS with Chrome open and logged into douyin.com
- Chrome "Allow JavaScript from Apple Events" enabled
- Feishu app credentials in `~/.hermes/.env` (`FEISHU_APP_ID`, `FEISHU_APP_SECRET`)

## How It Works

### 1. Extraction (`extract.py`)

1. Click into the target group from the conversation list
2. Scroll through the virtual list (`.messageMessageListlist`) in 500px steps
3. Sample `.TextMessageTextpureText` at each position
4. Deduplicate using a `Set`; write to Markdown incrementally

### 2. 24h Boundary Detection

Douyin's DOM does not expose timestamps. Instead:

1. Save yesterday's extraction to `/tmp/<group>_昨天.md`
2. Extract today's messages (newest first)
3. Find overlapping messages between yesterday and today
4. Trim overlap → remainder is strictly last 24h

### 3. AI Summarization

Feed the Markdown to any LLM agent with a prompt structured for:
- Stats header
- Thematic sections (AI tools, business, content strategy, etc.)
- One-line takeaway

### 4. Feishu Doc Publishing

Use Feishu Doc API:
```
POST /open-apis/auth/v3/tenant_access_token/internal  → token
POST /open-apis/docx/v1/documents                      → doc_id
POST /open-apis/docx/v1/documents/{id}/blocks/{id}/children  → content
```

Only `block_type: 2` (text) is tested and working.

## Cron Setup

```bash
hermes cron add douyin-daily-digest \
  --schedule "0 0 * * *" \
  --prompt "Extract messages from Douyin group chat, detect 24h boundary, generate summary, publish to Feishu Doc."
```

## Key Pitfalls

- **Virtual list**: Use `scrollTop = N`, not `scrollBy()`
- **No timestamps**: Use overlap detection with yesterday's file
- **Chrome must be open**: Cron requires active Chrome window
- **Group name must match exactly**: Including emoji and special chars
- **Only block_type 2** works reliably for Feishu Doc API
