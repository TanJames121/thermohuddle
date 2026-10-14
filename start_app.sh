#!/usr/bin/env bash
# ThermoHuddle app launcher (Linux / Raspberry Pi / macOS)
cd "$(dirname "$0")"
( sleep 1
  xdg-open "http://localhost:8422/brooder_tracker.html" 2>/dev/null \
    || open "http://localhost:8422/brooder_tracker.html" 2>/dev/null ) &
python3 -m http.server 8422
