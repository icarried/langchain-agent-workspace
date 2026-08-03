#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
SKILL_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd -P)"
ENV_FILE="$SKILL_DIR/.env.local"

usage() {
  cat <<'EOF'
Usage: format_official_document.sh INPUT [options]

Choose exactly one input:
  --url URL              Server-reachable DOC/DOCX URL
  --file PATH            Local DOC/DOCX; transfer its content as Base64 through MCP
  --base64-file PATH     File containing Base64 text; requires --filename
  --base64-stdin         Read Base64 text from stdin; requires --filename

Options:
  --filename NAME        Original .doc/.docx name for Base64 text input
  --output PATH          Exact output .docx path
  --output-dir DIR       Output directory when --output is omitted
  --base-url URL         Override OpenAI Base URL used for URL input
  --mcp-url URL          Override MCP URL used for Base64 input
  --model NAME           Model name (default: official-document-formatting-agent)
  --timeout SECONDS      Total curl timeout (default: 180)
  --max-input-bytes N    Base64/local-file size limit (default: 20971520)
  --dry-run              Validate request without returning a file
  --force                Replace an existing output file
  -h, --help             Show this help
EOF
}

die() {
  printf 'ERROR: %s\n' "$1" >&2
  exit 1
}

load_env_file() {
  [[ -f "$ENV_FILE" ]] || return 0

  local mode name value
  mode="$(stat -c '%a' "$ENV_FILE" 2>/dev/null || true)"
  if [[ -n "$mode" && "$mode" != "600" && "$mode" != "400" ]]; then
    die '.env.local permissions are too broad; run: chmod 600 .env.local'
  fi

  while IFS='=' read -r name value || [[ -n "$name" ]]; do
    name="${name%$'\r'}"
    value="${value%$'\r'}"
    [[ -z "$name" || "$name" == \#* ]] && continue
    case "$name" in
      OFFICIAL_DOCUMENT_FORMATTING_API_KEY|OFFICIAL_DOCUMENT_FORMATTING_BASE_URL|OFFICIAL_DOCUMENT_FORMATTING_MCP_URL)
        if [[ -z "${!name:-}" ]]; then
          printf -v "$name" '%s' "$value"
          export "$name"
        fi
        ;;
    esac
  done <"$ENV_FILE"
}

for command_name in curl base64 sha256sum stat unzip realpath mktemp basename dirname tr; do
  command -v "$command_name" >/dev/null 2>&1 || die "missing required command: $command_name"
done

load_env_file

if command -v jq >/dev/null 2>&1; then
  JQ="$(command -v jq)"
elif [[ "$(uname -m)" == 'x86_64' && -x "$SKILL_DIR/assets/bin/jq-linux-amd64" ]]; then
  JQ="$SKILL_DIR/assets/bin/jq-linux-amd64"
else
  die 'missing required command: jq (bundled fallback supports Linux x86_64 only)'
fi
"$JQ" --version >/dev/null 2>&1 || die 'jq is not executable'

document_url=''
local_file=''
base64_file=''
base64_stdin='false'
input_filename=''
output_path=''
output_dir="${HOME}/.hermes/cache/official-document-formatting"
base_url="${OFFICIAL_DOCUMENT_FORMATTING_BASE_URL:-http://127.0.0.1:10085/v1}"
mcp_url="${OFFICIAL_DOCUMENT_FORMATTING_MCP_URL:-}"
model='official-document-formatting-agent'
timeout_seconds='180'
max_input_bytes='20971520'
dry_run='false'
force='false'

while (($# > 0)); do
  case "$1" in
    --url) [[ $# -ge 2 ]] || die '--url requires a value'; document_url="$2"; shift 2 ;;
    --file) [[ $# -ge 2 ]] || die '--file requires a value'; local_file="$2"; shift 2 ;;
    --base64-file) [[ $# -ge 2 ]] || die '--base64-file requires a value'; base64_file="$2"; shift 2 ;;
    --base64-stdin) base64_stdin='true'; shift ;;
    --filename) [[ $# -ge 2 ]] || die '--filename requires a value'; input_filename="$2"; shift 2 ;;
    --output) [[ $# -ge 2 ]] || die '--output requires a value'; output_path="$2"; shift 2 ;;
    --output-dir) [[ $# -ge 2 ]] || die '--output-dir requires a value'; output_dir="$2"; shift 2 ;;
    --base-url) [[ $# -ge 2 ]] || die '--base-url requires a value'; base_url="$2"; shift 2 ;;
    --mcp-url) [[ $# -ge 2 ]] || die '--mcp-url requires a value'; mcp_url="$2"; shift 2 ;;
    --model) [[ $# -ge 2 ]] || die '--model requires a value'; model="$2"; shift 2 ;;
    --timeout) [[ $# -ge 2 ]] || die '--timeout requires a value'; timeout_seconds="$2"; shift 2 ;;
    --max-input-bytes) [[ $# -ge 2 ]] || die '--max-input-bytes requires a value'; max_input_bytes="$2"; shift 2 ;;
    --dry-run) dry_run='true'; shift ;;
    --force) force='true'; shift ;;
    -h|--help) usage; exit 0 ;;
    *) die "unknown argument: $1" ;;
  esac
done

input_count=0
[[ -n "$document_url" ]] && ((input_count += 1))
[[ -n "$local_file" ]] && ((input_count += 1))
[[ -n "$base64_file" ]] && ((input_count += 1))
[[ "$base64_stdin" == 'true' ]] && ((input_count += 1))
[[ "$input_count" == '1' ]] || die 'choose exactly one of --url, --file, --base64-file, or --base64-stdin'
[[ "$timeout_seconds" =~ ^[1-9][0-9]*$ ]] || die '--timeout must be a positive integer'
[[ "$max_input_bytes" =~ ^[1-9][0-9]*$ ]] || die '--max-input-bytes must be a positive integer'
[[ -n "${OFFICIAL_DOCUMENT_FORMATTING_API_KEY:-}" ]] || die 'OFFICIAL_DOCUMENT_FORMATTING_API_KEY is not configured'

base_url="${base_url%/}"
if [[ -z "$mcp_url" && "$base_url" == */v1 ]]; then
  mcp_url="${base_url%/v1}/mcp"
fi
mcp_url="${mcp_url%/}"

temp_dir="$(mktemp -d)"
temp_output=''
cleanup() {
  if [[ -n "$temp_output" && -f "$temp_output" ]]; then
    rm -f -- "$temp_output"
  fi
  if [[ -n "$temp_dir" && -d "$temp_dir" ]]; then
    rm -rf -- "$temp_dir"
  fi
}
trap cleanup EXIT

request_file="$temp_dir/request.json"
response_file="$temp_dir/response.json"
decoded_file="$temp_dir/formatted.docx"

if [[ -n "$document_url" ]]; then
  [[ "$document_url" =~ ^https?:// ]] || die '--url must use http:// or https://'
  [[ -n "$base_url" ]] || die 'base URL is empty'

  "$JQ" -n \
    --arg model "$model" \
    --arg source_url "$document_url" \
    --argjson dry_run "$dry_run" \
    '{
      model: $model,
      stream: false,
      dry_run: $dry_run,
      messages: [{
        role: "user",
        content: [
          {type: "text", text: "请按党政机关公文格式规范格式化附件，保持正文内容不变。"},
          {type: "file_url", file_url: {url: $source_url}}
        ]
      }]
    }' >"$request_file"

  http_code=''
  if ! http_code="$(curl \
    --silent \
    --show-error \
    --connect-timeout 15 \
    --max-time "$timeout_seconds" \
    --request POST \
    --header "Authorization: Bearer ${OFFICIAL_DOCUMENT_FORMATTING_API_KEY}" \
    --header 'Content-Type: application/json' \
    --data-binary "@$request_file" \
    --output "$response_file" \
    --write-out '%{http_code}' \
    "$base_url/chat/completions")"; then
    die 'curl could not reach the formatting API'
  fi
  [[ "$http_code" == '200' ]] || die "formatting API returned HTTP $http_code"
else
  [[ -n "$mcp_url" ]] || die 'MCP URL is not configured and cannot be inferred from a Base URL ending in /v1'
  encoded_file="$temp_dir/input.base64"
  source_check="$temp_dir/source-check"

  if [[ -n "$local_file" ]]; then
    [[ -f "$local_file" ]] || die '--file does not exist or is not a regular file'
    input_filename="$(basename -- "$local_file")"
    source_size="$(stat -c '%s' "$local_file")"
    [[ "$source_size" -le "$max_input_bytes" ]] || die 'input document exceeds --max-input-bytes'
    base64 -w 0 "$local_file" >"$encoded_file"
  elif [[ -n "$base64_file" ]]; then
    [[ -f "$base64_file" ]] || die '--base64-file does not exist or is not a regular file'
    [[ -n "$input_filename" ]] || die '--filename is required with --base64-file'
    tr -d '[:space:]' <"$base64_file" >"$encoded_file"
  else
    [[ -n "$input_filename" ]] || die '--filename is required with --base64-stdin'
    tr -d '[:space:]' >"$encoded_file"
  fi

  input_filename="$(basename -- "$input_filename")"
  [[ "$input_filename" =~ \.[dD][oO][cC]([xX])?$ ]] || die 'Base64 input filename must end in .doc or .docx'
  [[ -s "$encoded_file" ]] || die 'Base64 input is empty'
  base64 --decode <"$encoded_file" >"$source_check" 2>/dev/null || die 'input is not valid Base64'
  source_size="$(stat -c '%s' "$source_check")"
  [[ "$source_size" -le "$max_input_bytes" ]] || die 'decoded input document exceeds --max-input-bytes'

  "$JQ" -n \
    --arg filename "$input_filename" \
    --rawfile content_base64 "$encoded_file" \
    --argjson dry_run "$dry_run" \
    '{
      jsonrpc: "2.0",
      id: 1,
      method: "tools/call",
      params: {
        name: "official_document_format",
        arguments: {
          document: {filename: $filename, content_base64: $content_base64},
          dry_run: $dry_run
        }
      }
    }' >"$request_file"

  mcp_wire_file="$temp_dir/mcp-wire.txt"
  http_code=''
  if ! http_code="$(curl \
    --silent \
    --show-error \
    --connect-timeout 15 \
    --max-time "$timeout_seconds" \
    --request POST \
    --header "Authorization: Bearer ${OFFICIAL_DOCUMENT_FORMATTING_API_KEY}" \
    --header 'Accept: application/json, text/event-stream' \
    --header 'Content-Type: application/json' \
    --header 'MCP-Protocol-Version: 2025-11-25' \
    --data-binary "@$request_file" \
    --output "$mcp_wire_file" \
    --write-out '%{http_code}' \
    "$mcp_url")"; then
    die 'curl could not reach the formatting MCP endpoint'
  fi
  [[ "$http_code" == '200' ]] || die "formatting MCP returned HTTP $http_code"

  mcp_event_file="$temp_dir/mcp-event.json"
  "$JQ" -Rsc '
    split("\n")
    | map(select(startswith("data: ")) | ltrimstr("data: ") | fromjson?)
    | map(select(.id == 1))[0]
  ' "$mcp_wire_file" >"$mcp_event_file"
  "$JQ" -e '.result and (.result.isError == false)' "$mcp_event_file" >/dev/null \
    || die 'formatting MCP tool call failed'

  mcp_payload_file="$temp_dir/mcp-payload.json"
  "$JQ" -e '
    .result.structuredContent
    // ([.result.content[]? | select(.type == "text") | .text | fromjson?][0])
    | select(type == "object")
  ' "$mcp_event_file" >"$mcp_payload_file" \
    || die 'formatting MCP response does not contain structured output'

  "$JQ" -n \
    --slurpfile payload "$mcp_payload_file" \
    --argjson dry_run "$dry_run" \
    '{choices:[{message:{
      content: ($payload[0].report // ""),
      file: (if $dry_run then null else {
        status: "completed",
        filename: $payload[0].filename,
        file_type: "docx",
        mime_type: $payload[0].mime_type,
        encoding: "base64",
        content_base64: $payload[0].content_base64,
        sha256: $payload[0].sha256,
        size: $payload[0].size
      } end)
    }}]}' >"$response_file"
fi

"$JQ" -e '.choices[0].message | type == "object"' "$response_file" >/dev/null \
  || die 'API response does not contain choices[0].message'

report="$("$JQ" -r '.choices[0].message.content // ""' "$response_file")"
if [[ -n "$document_url" && "$report" == *"$document_url"* ]]; then
  report='Formatting completed; API report hidden because it echoed the input URL.'
fi

if [[ "$dry_run" == 'true' ]]; then
  printf 'STATUS=dry-run\n'
  printf '%s\n' 'REPORT_BEGIN'
  printf '%s\n' "$report"
  printf '%s\n' 'REPORT_END'
  exit 0
fi

"$JQ" -e '.choices[0].message.file | type == "object"' "$response_file" >/dev/null \
  || die 'formatting response does not contain a file payload'

api_status="$("$JQ" -er '.choices[0].message.file.status' "$response_file")" \
  || die 'file payload is missing status'
[[ "$api_status" == 'completed' || "$api_status" == 'success' ]] \
  || die "formatting file status is not successful: $api_status"

api_filename="$("$JQ" -er '.choices[0].message.file.filename' "$response_file")" \
  || die 'file payload is missing filename'
api_filename="$(basename -- "$api_filename")"
[[ "$api_filename" =~ \.[dD][oO][cC][xX]$ ]] || die 'formatted filename is not a DOCX file'

expected_sha="$("$JQ" -er '.choices[0].message.file.sha256 | ascii_downcase' "$response_file")" \
  || die 'file payload is missing sha256'
[[ "$expected_sha" =~ ^[0-9a-f]{64}$ ]] || die 'file payload sha256 is invalid'

expected_size="$("$JQ" -er '.choices[0].message.file.size' "$response_file")" \
  || die 'file payload is missing size'
[[ "$expected_size" =~ ^[0-9]+$ ]] || die 'file payload size is invalid'

"$JQ" -er '.choices[0].message.file.content_base64' "$response_file" \
  | base64 --decode >"$decoded_file" 2>/dev/null \
  || die 'file payload is not valid Base64'

actual_size="$(stat -c '%s' "$decoded_file")"
[[ "$actual_size" == "$expected_size" ]] || die 'decoded file size does not match response metadata'

actual_sha="$(sha256sum "$decoded_file")"
actual_sha="${actual_sha%% *}"
[[ "$actual_sha" == "$expected_sha" ]] || die 'decoded file SHA-256 does not match response metadata'

[[ "$(dd if="$decoded_file" bs=2 count=1 status=none)" == 'PK' ]] || die 'decoded file is not a ZIP/DOCX container'
unzip -tqq "$decoded_file" >/dev/null || die 'decoded DOCX ZIP integrity check failed'
zip_entries="$(unzip -Z1 "$decoded_file")"
grep -Fxq '[Content_Types].xml' <<<"$zip_entries" || die 'DOCX is missing [Content_Types].xml'
grep -Fxq 'word/document.xml' <<<"$zip_entries" || die 'DOCX is missing word/document.xml'

if [[ -n "$output_path" ]]; then
  [[ "$output_path" =~ \.[dD][oO][cC][xX]$ ]] || die '--output must end in .docx'
  output_path="$(realpath -m -- "$output_path")"
  output_dir="$(dirname -- "$output_path")"
else
  output_dir="$(realpath -m -- "$output_dir")"
  output_path="$output_dir/$api_filename"
fi

mkdir -p -- "$output_dir"
if [[ -e "$output_path" && "$force" != 'true' ]]; then
  die 'output already exists; use --force to replace it'
fi

temp_output="$(mktemp --tmpdir="$output_dir" ".${api_filename}.XXXXXX")"
cp -- "$decoded_file" "$temp_output"
chmod 600 "$temp_output"
if [[ "$force" == 'true' ]]; then
  mv -f -- "$temp_output" "$output_path"
else
  [[ ! -e "$output_path" ]] || die 'output appeared during processing; use --force to replace it'
  mv -- "$temp_output" "$output_path"
fi
temp_output=''

printf 'STATUS=completed\n'
printf 'OUTPUT_FILE=%s\n' "$output_path"
printf 'SHA256=%s\n' "$actual_sha"
printf 'SIZE=%s\n' "$actual_size"
printf '%s\n' 'REPORT_BEGIN'
printf '%s\n' "$report"
printf '%s\n' 'REPORT_END'
