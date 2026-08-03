#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
SKILL_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd -P)"
required=(bash curl base64 sha256sum stat unzip realpath mktemp tr)
missing=()

for command_name in "${required[@]}"; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    missing+=("$command_name")
  fi
done

if ! command -v jq >/dev/null 2>&1; then
  if [[ "$(uname -m)" == 'x86_64' && -x "$SKILL_DIR/assets/bin/jq-linux-amd64" ]]; then
    "$SKILL_DIR/assets/bin/jq-linux-amd64" --version >/dev/null 2>&1 \
      || missing+=('jq (bundled binary is not executable)')
  else
    missing+=('jq')
  fi
fi

if ((${#missing[@]} > 0)); then
  printf 'Missing required commands: %s\n' "${missing[*]}" >&2
  printf 'Debian/Ubuntu: sudo apt-get install curl jq coreutils unzip\n' >&2
  exit 1
fi

printf 'All required curl-skill commands are available.\n'
