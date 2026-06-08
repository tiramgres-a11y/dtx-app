#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# start_servers.sh — DTx Development Environment Launcher
#
# Usage:
#   chmod +x start_servers.sh
#   ./start_servers.sh
#
# This script opens TWO new terminal tabs/windows:
#   Tab 1 → FastAPI backend  (http://localhost:8000)
#   Tab 2 → Expo frontend    (QR code + browser option)
#
# Prerequisites (run once):
#   pip install -r backend/requirements.txt
#   cd frontend && npm install
# ─────────────────────────────────────────────────────────────────────────────

set -e
REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"

BACKEND_CMD="cd \"$REPO_ROOT\" && echo '🚀 FastAPI starting on http://localhost:8000' && python -m uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000"
FRONTEND_CMD="cd \"$REPO_ROOT/frontend\" && echo '🚀 Expo starting — press w for browser, scan QR for Expo Go' && npx expo start"

# ── macOS (Terminal / iTerm) ──────────────────────────────────────────────────
if [[ "$OSTYPE" == "darwin"* ]]; then
  osascript <<EOF
tell application "Terminal"
  activate
  do script "$BACKEND_CMD"
  delay 1
  do script "$FRONTEND_CMD"
end tell
EOF
  echo "✅  Two Terminal windows opened."

# ── Linux (gnome-terminal) ────────────────────────────────────────────────────
elif command -v gnome-terminal &>/dev/null; then
  gnome-terminal --tab -- bash -c "$BACKEND_CMD; exec bash"
  gnome-terminal --tab -- bash -c "$FRONTEND_CMD; exec bash"
  echo "✅  Two gnome-terminal tabs opened."

# ── Linux (xterm fallback) ────────────────────────────────────────────────────
elif command -v xterm &>/dev/null; then
  xterm -title "DTx Backend"  -e bash -c "$BACKEND_CMD; bash" &
  xterm -title "DTx Frontend" -e bash -c "$FRONTEND_CMD; bash" &
  echo "✅  Two xterm windows opened."

# ── Windows Git Bash / WSL ────────────────────────────────────────────────────
elif command -v cmd.exe &>/dev/null; then
  echo "Windows detected — use start_servers.bat instead:"
  echo "  Double-click start_servers.bat in Explorer, or run:"
  echo "  cmd /c start_servers.bat"

else
  echo "──────────────────────────────────────────────────────"
  echo "Could not detect a supported terminal emulator."
  echo "Open TWO separate terminals and run:"
  echo ""
  echo "  TERMINAL 1 (Backend):"
  echo "  $BACKEND_CMD"
  echo ""
  echo "  TERMINAL 2 (Frontend):"
  echo "  $FRONTEND_CMD"
  echo "──────────────────────────────────────────────────────"
fi
