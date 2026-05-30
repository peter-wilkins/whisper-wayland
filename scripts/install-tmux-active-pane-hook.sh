#!/usr/bin/env bash
set -euo pipefail

active_pane_file="${TEXT_TMUX_ACTIVE_PANE_FILE:-${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/whisper-wayland/active-tmux-pane}"

if ! command -v tmux >/dev/null 2>&1; then
  echo "tmux is not installed" >&2
  exit 1
fi

if ! tmux display-message -p '#{pane_id}' >/dev/null 2>&1; then
  echo "No running tmux server found" >&2
  exit 1
fi

mkdir -p "$(dirname "$active_pane_file")"
export WHISPER_WAYLAND_TMUX_ACTIVE_PANE_FILE="$active_pane_file"
tmux set-environment -g WHISPER_WAYLAND_TMUX_ACTIVE_PANE_FILE "$active_pane_file"

write_current='run-shell -b '\''mkdir -p "$(dirname "$WHISPER_WAYLAND_TMUX_ACTIVE_PANE_FILE")"; printf "%s\n" "#{pane_id}" > "$WHISPER_WAYLAND_TMUX_ACTIVE_PANE_FILE"'\'''

tmux set-option -gq focus-events on
tmux set-hook -g client-focus-in "$write_current"
tmux set-hook -g after-select-pane "$write_current"
tmux set-hook -g after-select-window "$write_current"
tmux set-hook -g client-session-changed "$write_current"
tmux set-hook -g client-attached "$write_current"

tmux display-message -p '#{pane_id}' > "$active_pane_file"
echo "Whisper Wayland tmux active-pane hook installed: $active_pane_file"
