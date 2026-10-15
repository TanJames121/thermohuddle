#!/usr/bin/env python3
"""FigCraft single-session build: one JSON script, IDs pre-computed.

ID allocation: in a fresh file the page starts with node id 1 reserved;
the first created layer gets id 2, next 3, etc. We emit all node.create
calls in one run script and reference parents by pre-computed ids.
"""
import json, subprocess, sys

CLI = r"C:\Program Files\FigCraft\figcraft-cli.exe"
FILE = "ThermoHuddle_App_Design.figcraft"

cmds = [{"command": "file.new", "params": {"name": "ThermoHuddle App Design"}}]
_next = [2]           # first created layer id in a fresh file
def alloc():
    i = _next[0]; _next[0] += 1; return i

def node(**params):
    cmds.append({"command": "node.create", "params": params})
    return alloc()

def T(parent, x, y, text, size=12, color="#55606e", bold=False, width=None, spacing=None):
    props = {"fontSize": size, "fill": color}
    if bold: props["fontStyle"] = "bold"
    if spacing: props["letterSpacing"] = spacing
    p = {"type": "text", "x": x, "y": y, "text": text, "parent": parent, "props": props}
    if width: p["width"] = width
    return node(**p)

def R(parent, x, y, w, h, fill, extra=None):
    props = {"fill": fill}
    if extra: props.update(extra)
    return node(type="rectangle", x=x, y=y, width=w, height=h, parent=parent, props=props)

def E(parent, x, y, w, h, fill, extra=None):
    props = {"fill": fill}
    if extra: props.update(extra)
    return node(type="ellipse", x=x, y=y, width=w, height=h, parent=parent, props=props)

def F(x, y, w, h, name, fill, radius=None, stroke=None, sw=1, clip=False, parent=None):
    props = {"fill": fill}
    if radius: props["cornerRadius"] = radius
    if stroke: props.update({"stroke": stroke, "strokeWeight": sw})
    if clip: props["clip"] = True
    p = {"type": "frame", "x": x, "y": y, "width": w, "height": h, "name": name, "props": props}
    if parent: p["parent"] = parent
    return node(**p)

# ============ build ============
node(type="rectangle", x=0, y=0, width=1440, height=760, name="bg", props={"fill": "#cdd0d4"})
T(None, 48, 28, "ThermoHuddle — App UI Design", 28, "#1c2430", bold=True)
T(None, 48, 62, "Edge AI Smart Brooder · CpE 404 Capstone · Screens at 390×844 (iPhone 14)", 13, "#55606e")

screen1 = F(48, 100, 390, 844, "screen1", "#f5f7fa", radius=40, clip=True)
statusbar1 = F(0, 44, 390, 44, "statusbar1", "#24457e", parent=screen1)
viewport1 = F(0, 88, 390, 380, "viewport1", "#d7dde8", clip=True, parent=screen1)
hud1 = F(16, 484, 358, 330, "hud1", "#ffffff", radius=16, stroke="#dfe4ea", parent=screen1)

screen2 = F(520, 100, 390, 844, "screen2", "#f5f7fa", radius=40, clip=True)
statusbar2 = F(0, 44, 390, 44, "statusbar2", "#24457e", parent=screen2)
viewport2 = F(0, 88, 390, 380, "viewport2", "#d7dde8", clip=True, parent=screen2)
hud2 = F(16, 484, 358, 330, "hud2", "#ffffff", radius=16, stroke="#dfe4ea", parent=screen2)

# ---- screen 1 content ----
T(statusbar1, 24, 12, "9:41", 14, "#ffffff", bold=True)
T(viewport1, 16, 16, "◉ LIVE · 47 chicks tracked", 13, "#0d6e5c", bold=True)
E(viewport1, 55, 90, 280, 180, "#c8ab7a", {"stroke": "#8a7450", "strokeWeight": 2})
E(viewport1, 140, 140, 110, 80, "#ffb84d", {"opacity": 0.30})
# huddle dots under the lamp
for dx in range(6):
    for dy in range(3):
        E(viewport1, 160+dx*13, 155+dy*11, 6, 6, "#f5f0e2", {"stroke": "#c9a24a", "strokeWeight": 1})
# stragglers
for sx, sy in [(85,130),(90,225),(300,135),(295,225)]:
    E(viewport1, sx, sy, 6, 6, "#f5f0e2", {"stroke": "#c9a24a", "strokeWeight": 1})
T(viewport1, 16, 282, "TOO COLD · flock huddling under lamp", 12, "#2d7dd2", bold=True)
T(viewport1, 16, 302, "NND 4.2 cm · entropy 0.46 · Clark–Evans R 0.41", 11, "#455062")

T(hud1, 18, 14, "COMFORT STATE", 11, "#8b95a5", spacing=1)
T(hud1, 18, 30, "TOO COLD", 24, "#2d7dd2", bold=True)
T(hud1, 18, 64, "Huddle pattern → trim +0.5°C (dwell 10 min)", 12, "#55606e")
R(hud1, 18, 90, 322, 1, "#eef1f5")
rows1 = [("Brooding day","1","#1c2430"),("Baseline setpoint","34.0°C","#1c2430"),
         ("Behavioral trim","+0.5°C","#2d7dd2"),("Floor temp (PV)","31.2°C","#1c2430"),
         ("Lamp duty","72 %","#1c2430"),("NH₃ (MQ-137)","8 ppm","#1c2430"),
         ("Crowding rule","clear","#28a745")]
for i,(lbl,val,col) in enumerate(rows1):
    T(hud1, 18, 102+i*22, lbl, 12, "#55606e")
    T(hud1, 250, 102+i*22, val, 12, col, bold=True)
R(screen1, 0, 780, 390, 64, "#ffffff", {"stroke": "#dfe4ea", "strokeSides": [False, False, True, False]})

# ---- screen 2 content ----
T(statusbar2, 24, 12, "9:41", 14, "#ffffff", bold=True)
T(viewport2, 16, 16, "⚠ CROWDING — max cell fraction 58%", 13, "#d97706", bold=True)
E(viewport2, 55, 90, 280, 180, "#c8ab7a", {"stroke": "#8a7450", "strokeWeight": 2})
E(viewport2, 150, 140, 100, 90, "#e8b04b", {"opacity": 0.9, "stroke": "#c43425", "strokeWeight": 3})
for sx, sy in [(80,120),(95,230),(300,130),(310,220),(70,180),(280,100)]:
    E(viewport2, sx, sy, 6, 6, "#f5f0e2", {"stroke": "#c9a24a", "strokeWeight": 1})
T(viewport2, 16, 282, "ALARM — vent burst + notification", 12, "#b3261e", bold=True)
T(viewport2, 16, 302, "Re-alerts every 5 min until acknowledged", 11, "#455062")

T(hud2, 18, 14, "CROWDING RULE", 11, "#8b95a5", spacing=1)
T(hud2, 18, 30, "ALARM ACTIVE", 22, "#b3261e", bold=True)
T(hud2, 18, 58, "Deterministic override — outside the classifier", 12, "#55606e")
R(hud2, 18, 84, 322, 1, "#eef1f5")
alarmbox = F(18, 96, 322, 64, "alarmbox", "#fdeceb", radius=12, stroke="#c43425", parent=hud2)
T(alarmbox, 14, 8, "⚠ ALARM — acknowledge required", 13, "#b3261e", bold=True)
T(alarmbox, 14, 30, "Alarm + ventilation burst + notification sent. Re-alerts every 5 min until a human acknowledges.", 11, "#7a2a22", width=296)
rows2 = [("Max cell fraction","58%","#d97706"),("Consecutive windows","3 / 3","#b3261e"),
         ("Ventilation burst","running","#d97706"),("Floor temp (PV)","33.4°C","#1c2430"),
         ("Setpoint (baseline + trim)","33.5°C","#1c2430")]
for i,(lbl,val,col) in enumerate(rows2):
    T(hud2, 18, 176+i*22, lbl, 12, "#55606e")
    T(hud2, 250, 176+i*22, val, 12, col, bold=True)
btn_ack = F(18, 292, 150, 30, "btn_ack", "#c43425", radius=15, parent=hud2)
btn_snooze = F(182, 292, 120, 30, "btn_snooze", "#ffffff", radius=15, stroke="#c43425", parent=hud2)
T(btn_ack, 32, 8, "ACKNOWLEDGE", 11, "#ffffff", bold=True)
T(btn_snooze, 34, 8, "SNOOZE", 11, "#b3261e", bold=True)
R(screen2, 0, 780, 390, 64, "#ffffff", {"stroke": "#dfe4ea", "strokeSides": [False, False, True, False]})

# ---- captions + save ----
T(None, 48, 964, "Screen 1 — Dashboard: 3D brooder view + comfort state HUD (baseline + trim, crowding rule)", 13, "#55606e")
T(None, 520, 964, "Screen 2 — Crowding alert: deterministic override, human acknowledgement", 13, "#55606e")
cmds.append({"command": "file.save", "params": {"path": FILE}})

with open("_build_final.json", "w") as f:
    json.dump(cmds, f)
r = subprocess.run([CLI, "run", "_build_final.json"], capture_output=True, text=True, timeout=600)
lines = [l for l in r.stdout.strip().splitlines() if l.strip()]
fails = []
for l in lines:
    try:
        x = json.loads(l)
        if not x.get("ok"): fails.append(x)
    except Exception: pass
print(f"steps: {len(lines)}, failures: {len(fails)}")
if fails:
    print(json.dumps(fails[:3], indent=1)[:500]); sys.exit(1)
print("BUILD COMPLETE")
