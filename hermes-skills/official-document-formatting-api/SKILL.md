---
name: official-document-formatting-api
description: Format one Chinese official-document DOC or DOCX through the OpenAI-compatible official-document-formatting-agent using a server-reachable HTTP(S) URL, then validate and save the returned DOCX. Use when Hermes is asked to standardize an official document, apply company document formatting, format a DOC/DOCX link, or return a downloadable formatted Word file without rewriting its content.
---

# Official Document Formatting API

Use the bundled script to call the deterministic formatter. Do not reformat the document locally and do not rewrite its text.

## Prerequisites

- Require Python 3.8 or newer; the script uses only the standard library.
- Read the API key in this order: process environment, skill-local `.env.local`, then `~/.hermes/secrets/official-document-formatting-api.env`.
- Read the gateway base URL from `OFFICIAL_DOCUMENT_FORMATTING_BASE_URL`; default to `http://127.0.0.1:10085/v1`.
- Require the input URL to be reachable from the `official-document-formatting` service, not merely from Hermes.
- Require the URL path to end in `.doc` or `.docx`. Preserve signed query parameters exactly.

Never print the API key or the input URL. Presigned URLs commonly contain credentials in their query string.

This delivery includes a skill-local `.env.local`. After extracting the ZIP, restrict it to the Hermes user:

```bash
chmod 600 "$HOME/.hermes/skills/official-document-formatting-api/.env.local"
```

For later key rotation, either update this `.env.local` or move the same variables to `~/.hermes/secrets/official-document-formatting-api.env`.

## Format a document

Run:

```bash
python3 scripts/format_official_document.py \
  --url "$DOCUMENT_URL" \
  --output-dir "$HOME/.hermes/cache/official-document-formatting"
```

The script calls `POST <base-url>/chat/completions` with model `official-document-formatting-agent`, `stream=false`, and the URL as an OpenAI `file_url` content part. It validates Base64, declared size, SHA-256 and required DOCX ZIP members before atomically saving the file.

If the user only wants a validation report, add `--dry-run`. A dry run deliberately produces no DOCX.

Use `--output /absolute/path/result.docx` when the caller provides an exact destination. Never overwrite the source document. The script refuses to overwrite an existing output unless `--force` is explicit.

## Return the result

Read `OUTPUT_FILE=` from successful script output. In the final Hermes response:

1. Briefly summarize the returned formatting report.
2. Put the absolute DOCX path on its own line.
3. Add `[[as_document]]` on its own line so the gateway delivers it as a file.

```text
公文已按公司规范完成格式化并通过完整性校验。

/home/user/.hermes/cache/official-document-formatting/通知-公文格式化.docx

[[as_document]]
```

## Failure handling

- HTTP `401`: confirm `OFFICIAL_DOCUMENT_FORMATTING_API_KEY` matches `AGENT_GATEWAY_API_KEY` on the gateway.
- Secret-file rejection: set the skill-local `.env.local` or Hermes secret file to mode `600`.
- HTTP `400`: confirm exactly one URL was supplied and its path ends in `.doc` or `.docx`.
- Download failure: test the URL from the formatting container. `127.0.0.1` in the URL means the container itself.
- Host denied: add only the required hostname and port to `AGENT_FILE_ALLOWED_HOSTS`, then recreate the formatting worker.
- Hash, size or DOCX validation failure: do not deliver the file; report the verification error.
- Never fall back to editing the document with an LLM.

## Verification

Treat the operation as successful only when the script exits with code 0 and prints `STATUS=completed`, an absolute `OUTPUT_FILE`, a 64-character `SHA256`, and a positive `SIZE`.
