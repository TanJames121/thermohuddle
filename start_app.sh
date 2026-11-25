#!/usr/bin/env bash
# ThermoHuddle app launcher (Linux / Raspberry Pi / macOS)
cd "$(dirname "$0")"
URL="http://localhost:8422/index.html"

( sleep 1
  xdg-open "$URL" 2>/dev/null \
    || open "$URL" 2>/dev/null ) &

if python3 -c "import socket,sys; s=socket.socket(); s.settimeout(0.3); r=s.connect_ex(('127.0.0.1',8422)); s.close(); sys.exit(0 if r==0 else 1)"; then
  echo "ThermoHuddle already serving on :8422 -> $URL"
  wait
else
  python3 -m http.server 8422
fi
