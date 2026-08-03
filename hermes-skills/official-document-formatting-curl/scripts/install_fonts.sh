#!/usr/bin/env bash
set -Eeuo pipefail
umask 022

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
SKILL_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd -P)"
SOURCE_DIR="$SKILL_DIR/assets/fonts"
TARGET_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/fonts/official-document-formatting"
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/fontconfig/conf.d"

for command_name in fc-cache fc-match install; do
  command -v "$command_name" >/dev/null 2>&1 || {
    printf 'ERROR: missing %s; install fontconfig and coreutils first.\n' "$command_name" >&2
    exit 1
  }
done

[[ -f "$SOURCE_DIR/NotoSansSC-VF.ttf" ]] || { printf 'ERROR: bundled Noto Sans SC font is missing.\n' >&2; exit 1; }
[[ -f "$SOURCE_DIR/NotoSerifSC-VF.ttf" ]] || { printf 'ERROR: bundled Noto Serif SC font is missing.\n' >&2; exit 1; }
[[ -f "$SOURCE_DIR/64-official-document-formatting-fonts.conf" ]] || { printf 'ERROR: bundled fontconfig mapping is missing.\n' >&2; exit 1; }

mkdir -p -- "$TARGET_DIR" "$CONFIG_DIR"
install -m 0644 "$SOURCE_DIR/NotoSansSC-VF.ttf" "$TARGET_DIR/NotoSansSC-VF.ttf"
install -m 0644 "$SOURCE_DIR/NotoSerifSC-VF.ttf" "$TARGET_DIR/NotoSerifSC-VF.ttf"
install -m 0644 "$SOURCE_DIR/64-official-document-formatting-fonts.conf" "$CONFIG_DIR/64-official-document-formatting-fonts.conf"
fc-cache -f "$TARGET_DIR" >/dev/null

printf 'Installed redistributable preview fonts in %s\n' "$TARGET_DIR"
printf '方正小标宋简体 -> %s\n' "$(fc-match -f '%{family}\n' '方正小标宋简体' | head -n 1)"
printf '仿宋_GB2312 -> %s\n' "$(fc-match -f '%{family}\n' '仿宋_GB2312' | head -n 1)"
printf '黑体 -> %s\n' "$(fc-match -f '%{family}\n' '黑体' | head -n 1)"
printf 'These are Noto CJK substitutes. Use licensed exact fonts for final production review when required.\n'

