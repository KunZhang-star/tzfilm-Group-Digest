# Feishu / Lark Publishing

This project can publish generated digests to Feishu/Lark Docs with the official `lark-cli`.

## Install CLI

```powershell
powershell -ExecutionPolicy Bypass -File .\setup_feishu_cli.ps1
```

The script runs:

```powershell
npx @larksuite/cli@latest install
```

If the CLI is already installed:

```powershell
powershell -ExecutionPolicy Bypass -File .\setup_feishu_cli.ps1 -SkipInstall
```

## Configure and Authorize

```powershell
lark-cli config init
lark-cli auth login --recommend
lark-cli auth status
```

`auth status` must show a ready user identity before publishing.

## Publish a Digest

```powershell
python .\extract.py `
  --platform telegram `
  --output .\telegram_raw.md `
  --create-digest `
  --digest-output .\telegram_digest.md `
  --publish-feishu `
  --feishu-title "Telegram Group Digest"
```

Internally, the script calls:

```powershell
lark-cli docs +create --doc-format markdown --title "Telegram Group Digest" --content "@telegram_digest.md"
```

## Notes

- The built-in digest is local and extractive. It does not call an LLM.
- Use `--create-digest` without `--publish-feishu` if you only want a local digest.
- Review the digest before publishing sensitive chat content.
