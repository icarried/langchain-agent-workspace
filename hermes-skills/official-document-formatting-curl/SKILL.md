---
name: official-document-formatting-curl
description: Use curl to send one DOC or DOCX to the official-document-formatting service by server-reachable URL or Base64, decode and verify the returned DOCX, and save it for delivery. Use when Hermes must format Chinese official documents without Python, including MinIO/HTTP(S) URL inputs, local file uploads, Base64 inputs, dry-run checks, and validated file return.
---

# Official Document Formatting with curl

Use the bundled Bash script for every formatting request. It keeps the bearer token out of command history and verifies the returned DOCX before saving it. URL input uses the OpenAI-compatible endpoint; local/Base64 input uses the already deployed unified MCP endpoint.

## Requirements

- Linux Bash 4.2 or newer.
- Commands: `curl`, `base64`, `sha256sum`, `stat`, `unzip`, `realpath`, `mktemp`. A verified static `jq 1.8.1` Linux x86_64 binary is bundled and used when the host has no `jq`; other CPU architectures must provide `jq` on `PATH`.
- No Python, Node.js, or pip package is required.
- A URL input must be reachable from the formatting service container and its path must identify a `.doc` or `.docx` file.
- The URL host must be allowed by the service's `AGENT_FILE_ALLOWED_HOSTS` configuration.

## First-time installation

After extracting this skill to `~/.hermes/skills/official-document-formatting-curl`, run:

```bash
cd ~/.hermes/skills/official-document-formatting-curl
chmod 600 .env.local
chmod +x scripts/*.sh assets/bin/jq-linux-amd64
scripts/check_requirements.sh
```

The archive contains `.env.local` as explicitly requested. Treat the archive and extracted directory as secrets: keep them private and never commit or upload them to a public repository.

The API only writes font names into DOCX and does not render glyphs. For Linux/WPS/LibreOffice preview, the archive includes redistributable Noto CJK substitutes and fontconfig aliases. Install them for the current user with:

```bash
scripts/install_fonts.sh
```

These substitutes help Linux render the document but are not the proprietary 方正小标宋简体、仿宋_GB2312 or 楷体_GB2312 originals. For final production review, use organization-licensed exact fonts in Word/WPS when required.

## Format a document

Choose exactly one input mode.

For a server-reachable URL:

Never put the token directly on the command line. Run:

```bash
export DOCUMENT_URL='http://files.example.internal/input.docx'
bash scripts/format_official_document.sh --url "$DOCUMENT_URL"
unset DOCUMENT_URL
```

For a local DOC/DOCX, let the script encode and send it as Base64 through MCP:

```bash
bash scripts/format_official_document.sh \
  --file /safe/path/input.docx
```

For already encoded Base64 text:

```bash
bash scripts/format_official_document.sh \
  --base64-file /safe/path/input.docx.base64 \
  --filename input.docx
```

Or pipe Base64 without putting it in the process argument list:

```bash
printf '%s' "$DOCUMENT_BASE64" | \
  bash scripts/format_official_document.sh \
    --base64-stdin \
    --filename input.docx
```

The default output directory is `~/.hermes/cache/official-document-formatting`. On success, read the `OUTPUT_FILE`, `SHA256`, and `SIZE` lines. Return the absolute `OUTPUT_FILE` path to the user and attach it as `[[as_document]]` when the Hermes channel supports document attachments.

Useful options:

```bash
bash scripts/format_official_document.sh \
  --url "$DOCUMENT_URL" \
  --output /safe/path/formatted.docx \
  --timeout 180 \
  --force

bash scripts/format_official_document.sh \
  --url "$DOCUMENT_URL" \
  --dry-run
```

Use `--base-url` only when the OpenAI API is not at the value stored in `.env.local`. Base64 mode uses `OFFICIAL_DOCUMENT_FORMATTING_MCP_URL`, or infers `/mcp` from a Base URL ending in `/v1`. The default model is `official-document-formatting-agent`.

## Safety and failures

- Do not use `curl -v`, `set -x`, or print `.env.local`; these can expose the bearer token or a signed source URL.
- Do not download a URL source in Hermes first. The formatting service downloads it under its own host allowlist, size, and timeout controls. Use `--file` only for a file Hermes already has locally.
- Do not pass a large Base64 value as a command-line argument. Use `--file`, `--base64-file`, or `--base64-stdin`; the script avoids OS argument-length limits.
- The script refuses an existing output unless `--force` is present.
- The script rejects non-200 responses without printing the response body, then verifies Base64 decoding, expected size, SHA-256, ZIP integrity, `[Content_Types].xml`, and `word/document.xml` before atomic placement.
- If the container cannot reach a host port, use a hostname or address routable from that container and add only that exact host to `AGENT_FILE_ALLOWED_HOSTS`.
- If dependency checking fails on Debian/Ubuntu, install `curl coreutils unzip`; install `jq` only on non-x86_64 systems. `fontconfig` is only needed for installing/using bundled preview fonts.
