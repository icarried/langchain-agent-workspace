#!/usr/bin/env bash
set -Eeuo pipefail

REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd -P)"
SOURCE_SKILL="$REPO_ROOT/hermes-skills/official-document-formatting-curl"
TEST_ROOT="$(mktemp -d)"
trap 'rm -rf -- "$TEST_ROOT"' EXIT

SKILL_COPY="$TEST_ROOT/skill"
MOCK_BIN="$TEST_ROOT/mock-bin"
FIXTURE_DOCX="$REPO_ROOT/tests/skills/fixtures/minimal.docx"
mkdir -p "$MOCK_BIN"
cp -a -- "$SOURCE_SKILL" "$SKILL_COPY"
chmod 600 "$SKILL_COPY/.env.local"
chmod +x "$SKILL_COPY/scripts/"*.sh "$SKILL_COPY/assets/bin/jq-linux-amd64"

cp -- "$FIXTURE_DOCX" "$TEST_ROOT/formatted.docx"

JQ="$SKILL_COPY/assets/bin/jq-linux-amd64"
FIXTURE_BASE64="$(base64 -w 0 "$TEST_ROOT/formatted.docx")"
FIXTURE_SHA="$(sha256sum "$TEST_ROOT/formatted.docx")"
FIXTURE_SHA="${FIXTURE_SHA%% *}"
FIXTURE_SIZE="$(stat -c '%s' "$TEST_ROOT/formatted.docx")"

"$JQ" -n \
  --arg content "$FIXTURE_BASE64" \
  --arg sha "$FIXTURE_SHA" \
  --argjson size "$FIXTURE_SIZE" \
  '{choices:[{message:{content:"Formatting test completed.",file:{status:"completed",filename:"input-公文格式化.docx",file_type:"docx",mime_type:"application/vnd.openxmlformats-officedocument.wordprocessingml.document",encoding:"base64",content_base64:$content,sha256:$sha,size:$size}}}]}' \
  >"$TEST_ROOT/response.json"

MCP_STRUCTURED="$("$JQ" -nc \
  --arg content "$FIXTURE_BASE64" \
  --arg sha "$FIXTURE_SHA" \
  --argjson size "$FIXTURE_SIZE" \
  '{report:"MCP Base64 formatting test completed.",dry_run:false,filename:"input-公文格式化.docx",mime_type:"application/vnd.openxmlformats-officedocument.wordprocessingml.document",content_base64:$content,sha256:$sha,size:$size}')"
"$JQ" -nc \
  --argjson structured "$MCP_STRUCTURED" \
  '{jsonrpc:"2.0",id:1,result:{content:[{type:"text",text:($structured|tojson)}],structuredContent:$structured,isError:false}}' \
  | while IFS= read -r line; do printf 'event: message\ndata: %s\n\n' "$line"; done \
  >"$TEST_ROOT/mcp-response.sse"

cat >"$MOCK_BIN/curl" <<'MOCK_CURL'
#!/usr/bin/env bash
set -Eeuo pipefail
output=''
request=''
authorization=''
endpoint=''
mcp_protocol=''
while (($# > 0)); do
  case "$1" in
    --silent|--show-error) shift ;;
    --connect-timeout|--max-time|--request|--write-out) shift 2 ;;
    --header)
      if [[ "$2" == Authorization:* ]]; then authorization="${2#Authorization: }"; fi
      if [[ "$2" == MCP-Protocol-Version:* ]]; then mcp_protocol="${2#MCP-Protocol-Version: }"; fi
      shift 2
      ;;
    --data-binary) request="${2#@}"; shift 2 ;;
    --output) output="$2"; shift 2 ;;
    http://*|https://*) endpoint="$1"; shift ;;
    *) printf 'unexpected curl argument\n' >&2; exit 91 ;;
  esac
done
[[ "$authorization" == 'Bearer test-token' ]] || exit 92
if [[ "$endpoint" == 'http://mock-api.invalid/v1/chat/completions' ]]; then
  "$MOCK_JQ" -e --arg url "$EXPECTED_SOURCE_URL" '
    .model == "official-document-formatting-agent" and
    .stream == false and
    .dry_run == false and
    .messages[0].content[1].type == "file_url" and
    .messages[0].content[1].file_url.url == $url
  ' "$request" >/dev/null || exit 94
  cp -- "$MOCK_OPENAI_RESPONSE" "$output"
elif [[ "$endpoint" == 'http://mock-api.invalid/mcp' ]]; then
  [[ "$mcp_protocol" == '2025-11-25' ]] || exit 95
  "$MOCK_JQ" -e --arg content "$EXPECTED_BASE64" '
    .jsonrpc == "2.0" and
    .method == "tools/call" and
    .params.name == "official_document_format" and
    .params.arguments.dry_run == false and
    .params.arguments.document.filename == "formatted.docx" and
    .params.arguments.document.content_base64 == $content
  ' "$request" >/dev/null || exit 96
  cp -- "$MOCK_MCP_RESPONSE" "$output"
else
  exit 93
fi
printf '200'
MOCK_CURL
chmod +x "$MOCK_BIN/curl"

SOURCE_URL='http://files.example.internal/input.docx?signature=must-not-leak'
OUTPUT_FILE="$TEST_ROOT/output/result.docx"
PATH="$MOCK_BIN:$PATH" \
OFFICIAL_DOCUMENT_FORMATTING_API_KEY='test-token' \
OFFICIAL_DOCUMENT_FORMATTING_BASE_URL='http://mock-api.invalid/v1' \
MOCK_JQ="$JQ" \
MOCK_OPENAI_RESPONSE="$TEST_ROOT/response.json" \
MOCK_MCP_RESPONSE="$TEST_ROOT/mcp-response.sse" \
EXPECTED_SOURCE_URL="$SOURCE_URL" \
EXPECTED_BASE64="$FIXTURE_BASE64" \
bash "$SKILL_COPY/scripts/format_official_document.sh" \
  --url "$SOURCE_URL" \
  --output "$OUTPUT_FILE" \
  >"$TEST_ROOT/stdout.txt" \
  2>"$TEST_ROOT/stderr.txt"

cmp -- "$TEST_ROOT/formatted.docx" "$OUTPUT_FILE"
grep -Fxq 'STATUS=completed' "$TEST_ROOT/stdout.txt"
grep -Fxq "OUTPUT_FILE=$OUTPUT_FILE" "$TEST_ROOT/stdout.txt"
grep -Fxq "SHA256=$FIXTURE_SHA" "$TEST_ROOT/stdout.txt"
if grep -Fq 'test-token' "$TEST_ROOT/stdout.txt" "$TEST_ROOT/stderr.txt"; then
  printf 'secret leaked to output\n' >&2
  exit 95
fi
if grep -Fq 'must-not-leak' "$TEST_ROOT/stdout.txt" "$TEST_ROOT/stderr.txt"; then
  printf 'signed URL leaked to output\n' >&2
  exit 96
fi

MCP_OUTPUT_FILE="$TEST_ROOT/output/result-mcp.docx"
PATH="$MOCK_BIN:$PATH" \
OFFICIAL_DOCUMENT_FORMATTING_API_KEY='test-token' \
OFFICIAL_DOCUMENT_FORMATTING_BASE_URL='http://mock-api.invalid/v1' \
OFFICIAL_DOCUMENT_FORMATTING_MCP_URL='http://mock-api.invalid/mcp' \
MOCK_JQ="$JQ" \
MOCK_OPENAI_RESPONSE="$TEST_ROOT/response.json" \
MOCK_MCP_RESPONSE="$TEST_ROOT/mcp-response.sse" \
EXPECTED_SOURCE_URL="$SOURCE_URL" \
EXPECTED_BASE64="$FIXTURE_BASE64" \
bash "$SKILL_COPY/scripts/format_official_document.sh" \
  --file "$TEST_ROOT/formatted.docx" \
  --output "$MCP_OUTPUT_FILE" \
  >"$TEST_ROOT/mcp-stdout.txt" \
  2>"$TEST_ROOT/mcp-stderr.txt"

cmp -- "$TEST_ROOT/formatted.docx" "$MCP_OUTPUT_FILE"
grep -Fxq 'STATUS=completed' "$TEST_ROOT/mcp-stdout.txt"
grep -Fxq "OUTPUT_FILE=$MCP_OUTPUT_FILE" "$TEST_ROOT/mcp-stdout.txt"
grep -Fxq "SHA256=$FIXTURE_SHA" "$TEST_ROOT/mcp-stdout.txt"
if grep -Fq 'test-token' "$TEST_ROOT/mcp-stdout.txt" "$TEST_ROOT/mcp-stderr.txt"; then
  printf 'secret leaked from MCP mode\n' >&2
  exit 97
fi

printf 'curl skill URL and Base64 mock API tests passed.\n'
