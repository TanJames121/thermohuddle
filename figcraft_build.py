#!/usr/bin/env python3
"""FigCraft two-phase build: create containers, capture IDs, nest children."""
import json, subprocess, sys

CLI = r"C:\Program Files\FigCraft\figcraft-cli.exe"
FILE = "ThermoHuddle_App_Design.figcraft"

def run(script, step):
    with open(step, "w") as f:
        json.dump(script, f)
    r = subprocess.run([CLI, "run", step], capture_output=True, text=True, timeout=240)
    lines = [l for l in r.stdout.strip().splitlines() if l.strip()]
    results = []
    for l in lines:
        try:
            results.append(json.loads(l))
        except Exception:
            pass
    fails = [x for x in results if not x.get("ok")]
    if fails:
        print("FAILURES:", json.dumps(fails)[:400]); sys.exit(1)
    return results

def ids_by_name(results, names):
    """Map layer name -> id from run results (result includes {id})."""
    out = {}
    for x in results:
        rid = (x.get("result") or {}).get("id") if isinstance(x.get("result"), dict) else None
        # node.create results: {"id": N}; we track by order
    return out

# ---------- PHASE A: containers ----------
phaseA = [
  {"command": "file.new", "params": {"name": "ThermoHuddle App Design"}},
  {"command": "page.rename", "params": {"name": "📱 App Screens"}},
  {"command": "node.create", "params": {"type": "rectangle", "x": 0, "y": 0, "width": 1440, "height": 760, "name": "bg", "props": {"fill": "#cdd0d4"}}},
  {"command": "node.create", "params": {"type": "text", "x": 48, "y": 28, "text": "ThermoHuddle — App UI Design", "props": {"fontSize": 28, "fontStyle": "bold", "fill": "#1c2430"}}},
  {"command": "node.create", "params": {"type": "text", "x": 48, "y": 62, "text": "Edge AI Smart Brooder · CpE 404 Capstone · Screens at 390×844 (iPhone 14)", "props": {"fontSize": 13, "fill": "#55606e"}}},
  # screen 1 containers
  {"command": "node.create", "params": {"type": "frame", "x": 48, "y": 100, "width": 390, "height": 844, "name": "screen1", "props": {"fill": "#f5f7fa", "cornerRadius": 40, "clip": True}}},
  {"command": "node.create", "params": {"type": "frame", "x": 0, "y": 44, "width": 390, "height": 44, "name": "statusbar1", "parent": "P_screen1", "props": {"fill": "#24457e"}}},
  {"command": "node.create", "params": {"type": "frame", "x": 0, "y": 88, "width": 390, "height": 380, "name": "viewport1", "parent": "P_screen1", "props": {"fill": "#d7dde8", "clip": True}}},
  {"command": "node.create", "params": {"type": "frame", "x": 16, "y": 484, "width": 358, "height": 330, "name": "hud1", "parent": "P_screen1", "props": {"fill": "#ffffff", "cornerRadius": 16, "stroke": "#dfe4ea", "strokeWeight": 1}}},
  # screen 2 containers
  {"command": "node.create", "params": {"type": "frame", "x": 520, "y": 100, "width": 390, "height": 844, "name": "screen2", "props": {"fill": "#f5f7fa", "cornerRadius": 40, "clip": True}}},
  {"command": "node.create", "params": {"type": "frame", "x": 0, "y": 44, "width": 390, "height": 44, "name": "statusbar2", "parent": "P_screen2", "props": {"fill": "#24457e"}}},
  {"command": "node.create", "params": {"type": "frame", "x": 0, "y": 88, "width": 390, "height": 380, "name": "viewport2", "parent": "P_screen2", "props": {"fill": "#d7dde8", "clip": True}}},
  {"command": "node.create", "params": {"type": "frame", "x": 16, "y": 484, "width": 358, "height": 330, "name": "hud2", "parent": "P_screen2", "props": {"fill": "#ffffff", "cornerRadius": 16, "stroke": "#dfe4ea", "strokeWeight": 1}}},
]

# PHASE A pass 1: create ONLY the top-level frames (screen1, screen2), with parents stripped
A1 = []
for c in phaseA:
    p = dict(c)
    if "parent" in p["params"]:
        continue  # children wait for pass 2
    A1.append(p)

res1 = run(A1, "_phaseA1.json")
# IDs are assigned in order of node creation; map by result order
node_ids = [x["result"].get("id") for x in res1 if isinstance(x.get("result"), dict) and "id" in x.get("result", {})]
# order of creation in A1: bg, title, subtitle, screen1, screen2
name_order = ["bg", "title", "subtitle", "screen1", "screen2"]
idmap = dict(zip(name_order, node_ids))
print("pass1 ids:", idmap)

# PHASE A pass 2: sub-frames with real parent ids
def P(frame_name):
    return idmap[frame_name]

A2 = []
subspecs = [
    ("statusbar1", P("screen1"), {"type": "frame", "x": 0, "y": 44, "width": 390, "height": 44, "name": "statusbar1", "props": {"fill": "#24457e"}}),
    ("viewport1",  P("screen1"), {"type": "frame", "x": 0, "y": 88, "width": 390, "height": 380, "name": "viewport1", "props": {"fill": "#d7dde8", "clip": True}}),
    ("hud1",       P("screen1"), {"type": "frame", "x": 16, "y": 484, "width": 358, "height": 330, "name": "hud1", "props": {"fill": "#ffffff", "cornerRadius": 16, "stroke": "#dfe4ea", "strokeWeight": 1}}),
    ("statusbar2", P("screen2"), {"type": "frame", "x": 0, "y": 44, "width": 390, "height": 44, "name": "statusbar2", "props": {"fill": "#24457e"}}),
    ("viewport2",  P("screen2"), {"type": "frame", "x": 0, "y": 88, "width": 390, "height": 380, "name": "viewport2", "props": {"fill": "#d7dde8", "clip": True}}),
    ("hud2",       P("screen2"), {"type": "frame", "x": 16, "y": 484, "width": 358, "height": 330, "name": "hud2", "props": {"fill": "#ffffff", "cornerRadius": 16, "stroke": "#dfe4ea", "strokeWeight": 1}}),
]
for name, parent, params in subspecs:
    params["parent"] = parent
    A2.append({"command": "node.create", "params": params})

res2 = run(A2, "_phaseA2.json")
sub_ids = [x["result"].get("id") for x in res2 if isinstance(x.get("result"), dict) and "id" in x.get("result", {})]
sub_names = [s[0] for s in subspecs]
for n, i in zip(sub_names, sub_ids):
    idmap[n] = i
print("all container ids:", idmap)

# ---------- PHASE B: children with real IDs ----------
def C(parent_key, **kw):
    params = {"parent": idmap[parent_key]}
    params.update(kw)
    return {"command": "node.create", "params": params}

B = [
  # ===== Screen 1 =====
  C("statusbar1", type="text", x=24, y=12, text="9:41", props={"fontSize": 14, "fill": "#ffffff", "fontStyle": "bold"}),
  C("viewport1", type="text", x=16, y=16, text="◉ LIVE · 47 chicks tracked", props={"fontSize": 13, "fontStyle": "bold", "fill": "#0d6e5c"}),
  # brooder floor (ellipse) + grid quadrants + warm glow + chick dots
  C("viewport1", type="ellipse", x=55, y=90, width=280, height=180, props={"fill": "#c8ab7a", "stroke": "#8a7450", "strokeWeight": 2}),
  C("viewport1", type="line", x=195, y=90, width=0, props={"stroke": "#a08a5e", "strokeWeight": 1}),
  C("viewport1", type="ellipse", x=140, y=140, width=110, height=80, props={"fill": "#ffb84d", "opacity": 0.30}),
  # chick dots (huddle cluster under lamp)
  *[C("viewport1", type="ellipse", x=160+dx*14, y=155+dy*10, width=6, height=6, props={"fill": "#f5f0e2", "stroke": "#c9a24a", "strokeWeight": 1})
    for dx in range(6) for dy in range(3)],
  C("viewport1", type="text", x=16, y=280, text="TOO COLD · flock huddling under lamp", props={"fontSize": 12, "fontStyle": "bold", "fill": "#2d7dd2"}),
  C("viewport1", type="text", x=16, y=300, text="NND 4.2 cm · entropy 0.46 · Clark–Evans R 0.41", props={"fontSize": 11, "fill": "#455062"}),
  # HUD 1
  C("hud1", type="text", x=18, y=14, text="COMFORT STATE", props={"fontSize": 11, "fill": "#8b95a5", "letterSpacing": 1}),
  C("hud1", type="text", x=18, y=30, text="TOO COLD", props={"fontSize": 24, "fontStyle": "bold", "fill": "#2d7dd2"}),
  C("hud1", type="text", x=18, y=64, text="Huddle pattern → trim +0.5°C (dwell 10 min)", props={"fontSize": 12, "fill": "#55606e"}),
  C("hud1", type="rectangle", x=18, y=90, width=322, height=1, props={"fill": "#eef1f5"}),
  *[C("hud1", type="text", x=18, y=102+i*22, text=lbl, props={"fontSize": 12, "fill": "#55606e"}) for i, lbl in enumerate([
      "Brooding day", "Baseline setpoint", "Behavioral trim", "Floor temp (PV)",
      "Lamp duty", "NH₃ (MQ-137)", "Crowding rule"])],
  *[C("hud1", type="text", x=250, y=102+i*22, text=val, props={"fontSize": 12, "fontStyle": "bold", "fill": col}) for i, (val, col) in enumerate([
      ("1", "#1c2430"), ("34.0°C", "#1c2430"), ("+0.5°C", "#2d7dd2"), ("31.2°C", "#1c2430"),
      ("72 %", "#1c2430"), ("8 ppm", "#1c2430"), ("clear", "#28a745")])],
  # nav bar
  C("screen1", type="rectangle", x=0, y=780, width=390, height=64, props={"fill": "#ffffff", "stroke": "#dfe4ea", "strokeSides": [False, False, True, False]}),

  # ===== Screen 2 =====
  C("statusbar2", type="text", x=24, y=12, text="9:41", props={"fontSize": 14, "fill": "#ffffff", "fontStyle": "bold"}),
  C("viewport2", type="text", x=16, y=16, text="⚠ CROWDING — max cell fraction 58%", props={"fontSize": 13, "fontStyle": "bold", "fill": "#d97706"}),
  C("viewport2", type="ellipse", x=55, y=90, width=280, height=180, props={"fill": "#c8ab7a", "stroke": "#8a7450", "strokeWeight": 2}),
  # dense pile (one big amber blob with red ring = crowding)
  C("viewport2", type="ellipse", x=150, y=140, width=100, height=90, props={"fill": "#e8b04b", "opacity": 0.9, "stroke": "#c43425", "strokeWeight": 3}),
  # scattered stragglers
  *[C("viewport2", type="ellipse", x=sx, y=sy, width=6, height=6, props={"fill": "#f5f0e2", "stroke": "#c9a24a", "strokeWeight": 1})
    for sx, sy in [(80,120),(95,230),(300,130),(310,220),(70,180),(280,100)]],
  C("viewport2", type="text", x=16, y=280, text="ALARM — vent burst + notification", props={"fontSize": 12, "fontStyle": "bold", "fill": "#b3261e"}),
  C("viewport2", type="text", x=16, y=300, text="Re-alerts every 5 min until acknowledged", props={"fontSize": 11, "fill": "#455062"}),
  # HUD 2
  C("hud2", type="text", x=18, y=14, text="CROWDING RULE", props={"fontSize": 11, "fill": "#8b95a5", "letterSpacing": 1}),
  C("hud2", type="text", x=18, y=30, text="ALARM ACTIVE", props={"fontSize": 22, "fontStyle": "bold", "fill": "#b3261e"}),
  C("hud2", type="text", x=18, y=60, text="Deterministic override — outside the classifier", props={"fontSize": 12, "fill": "#55606e"}),
  C("hud2", type="rectangle", x=18, y=86, width=322, height=1, props={"fill": "#eef1f5"}),
  # alarm box (as a red-bordered sub-frame)
  {"command": "node.create", "params": {"type": "frame", "x": 18, "y": 98, "width": 322, "height": 64, "parent": idmap["hud2"], "name": "alarmbox", "props": {"fill": "#fdeceb", "cornerRadius": 12, "stroke": "#c43425", "strokeWeight": 1}}},
]
res3 = run(B, "_phaseB.json")
b_ids = [x["result"].get("id") for x in res3 if isinstance(x.get("result"), dict) and "id" in x.get("result", {})]
alarm_id = b_ids[-1] if b_ids else None
print("alarmbox id:", alarm_id)

# alarm box children + stats rows + buttons
B2 = [
  {"command": "node.create", "params": {"type": "text", "x": 14, "y": 8, "text": "⚠ ALARM — acknowledge required", "parent": alarm_id, "props": {"fontSize": 13, "fontStyle": "bold", "fill": "#b3261e"}}},
  {"command": "node.create", "params": {"type": "text", "x": 14, "y": 30, "text": "Alarm + ventilation burst + notification sent. Re-alerts every 5 min until a human acknowledges.", "parent": alarm_id, "width": 296, "props": {"fontSize": 11, "fill": "#7a2a22"}}},
  *[{"command": "node.create", "params": {"type": "text", "x": 18, "y": 176+i*22, "text": lbl, "parent": idmap["hud2"], "props": {"fontSize": 12, "fill": "#55606e"}}}
    for i, lbl in enumerate(["Max cell fraction", "Consecutive windows", "Ventilation burst", "Floor temp (PV)", "Setpoint (baseline + trim)"])],
  *[{"command": "node.create", "params": {"type": "text", "x": 250, "y": 176+i*22, "text": val, "parent": idmap["hud2"], "props": {"fontSize": 12, "fontStyle": "bold", "fill": col}}}
    for i, (val, col) in enumerate([("58%", "#d97706"), ("3 / 3", "#b3261e"), ("running", "#d97706"), ("33.4°C", "#1c2430"), ("33.5°C", "#1c2430")])],
  # buttons
  {"command": "node.create", "params": {"type": "frame", "x": 18, "y": 292, "width": 150, "height": 30, "parent": idmap["hud2"], "name": "btn_ack", "props": {"fill": "#c43425", "cornerRadius": 15}}},
  {"command": "node.create", "params": {"type": "text", "x": 34, "y": 7, "text": "ACKNOWLEDGE", "parent": None, "props": {"fontSize": 11, "fontStyle": "bold", "fill": "#ffffff"}}},
  {"command": "node.create", "params": {"type": "frame", "x": 182, "y": 292, "width": 120, "height": 30, "parent": idmap["hud2"], "name": "btn_snooze", "props": {"fill": "#ffffff", "cornerRadius": 15, "stroke": "#c43425", "strokeWeight": 1}}},
  {"command": "node.create", "params": {"type": "text", "x": 212, "y": 7, "text": "SNOOZE", "parent": None, "props": {"fontSize": 11, "fontStyle": "bold", "fill": "#b3261e"}}},
]
# the two button labels need the button ids as parents — fix by running in two steps
res4a = run(B2[:7], "_phaseB2a.json")  # through stats rows
btn_ids = []
for x in res4a:
    if isinstance(x.get("result"), dict) and "id" in x["result"]:
        r = x["result"]
        # can't get names from run results; instead: create buttons separately
# create buttons, then labels with parent=button ids
B3 = [
  {"command": "node.create", "params": {"type": "frame", "x": 18, "y": 292, "width": 150, "height": 30, "parent": idmap["hud2"], "name": "btn_ack", "props": {"fill": "#c43425", "cornerRadius": 15}}},
  {"command": "node.create", "params": {"type": "frame", "x": 182, "y": 292, "width": 120, "height": 30, "parent": idmap["hud2"], "name": "btn_snooze", "props": {"fill": "#ffffff", "cornerRadius": 15, "stroke": "#c43425", "strokeWeight": 1}}},
]
res5 = run(B3, "_phaseB3.json")
new_ids = [x["result"].get("id") for x in res5 if isinstance(x.get("result"), dict) and "id" in x.get("result", {})]
ack_id, snooze_id = new_ids[0], new_ids[1]
B4 = [
  {"command": "node.create", "params": {"type": "text", "x": 32, "y": 8, "text": "ACKNOWLEDGE", "parent": ack_id, "props": {"fontSize": 11, "fontStyle": "bold", "fill": "#ffffff"}}},
  {"command": "node.create", "params": {"type": "text", "x": 34, "y": 8, "text": "SNOOZE", "parent": snooze_id, "props": {"fontSize": 11, "fontStyle": "bold", "fill": "#b3261e"}}},
]
run(B4, "_phaseB4.json")

# captions + nav bar 2 + save
B5 = [
  {"command": "node.create", "params": {"type": "text", "x": 48, "y": 964, "text": "Screen 1 — Dashboard: 3D brooder view + comfort state HUD (baseline + trim, crowding rule)", "props": {"fontSize": 13, "fill": "#55606e"}}},
  {"command": "node.create", "params": {"type": "text", "x": 520, "y": 964, "text": "Screen 2 — Crowding alert: deterministic override, human acknowledgement", "props": {"fontSize": 13, "fill": "#55606e"}}},
  {"command": "node.create", "params": {"type": "rectangle", "x": 0, "y": 780, "width": 390, "height": 64, "parent": idmap["screen2"], "props": {"fill": "#ffffff", "stroke": "#dfe4ea", "strokeSides": [False, False, True, False]}}},
  {"command": "file.save", "params": {"path": FILE}},
]
run(B5, "_phaseB5.json")
print("BUILD COMPLETE")
