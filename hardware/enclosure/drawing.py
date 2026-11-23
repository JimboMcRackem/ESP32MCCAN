# -*- coding: utf-8 -*-
"""Dimensioned A3 drawing of the housing, 1:1, from layout.json and board.json (stdlib only).

  python hardware/enclosure/drawing.py      writes hardware/enclosure/export/housing-drawing.svg

Print at 100 % on A3 for a 1:1 template. Views: top (lid off), cable wall from outside, +x side.
"""
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "export", "housing-drawing.svg")

INK, THIN, ZONE, BOARD = "#111", "#666", "#c0392b", "#1f6f3f"


class Svg:
    def __init__(self):
        self.el = []

    def add(self, s):
        self.el.append(s)

    def rect(self, x0, y0, x1, y1, stroke=INK, w=0.35, fill="none", dash=None, rx=0):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        self.add(f'<rect x="{min(x0, x1):.2f}" y="{min(y0, y1):.2f}" width="{abs(x1 - x0):.2f}" height="{abs(y1 - y0):.2f}" '
                 f'rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="{w}"{d}/>')

    def circle(self, x, y, r, stroke=INK, w=0.35, fill="none"):
        self.add(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{r:.2f}" fill="{fill}" stroke="{stroke}" stroke-width="{w}"/>')

    def line(self, x0, y0, x1, y1, stroke=INK, w=0.25, dash=None):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        self.add(f'<line x1="{x0:.2f}" y1="{y0:.2f}" x2="{x1:.2f}" y2="{y1:.2f}" stroke="{stroke}" stroke-width="{w}"{d}/>')

    def text(self, x, y, s, size=3.0, anchor="start", fill=INK, rot=0, weight="normal"):
        t = f' transform="rotate({rot} {x:.2f} {y:.2f})"' if rot else ""
        s = s.replace("&", "&amp;").replace("<", "&lt;")
        self.add(f'<text x="{x:.2f}" y="{y:.2f}" font-family="Arial, sans-serif" font-size="{size}" '
                 f'text-anchor="{anchor}" fill="{fill}" font-weight="{weight}"{t}>{s}</text>')

    def hdim(self, x0, x1, y, label, ext_from=None):
        """Horizontal dimension at page y; extension lines from ext_from (page y) if given."""
        if ext_from is not None:
            for x in (x0, x1):
                self.line(x, ext_from, x, y + (1.5 if y > ext_from else -1.5), THIN, 0.18)
        self.line(x0, y, x1, y, INK, 0.2)
        for x, s in ((x0, 1), (x1, -1)):
            self.add(f'<path d="M{x:.2f},{y:.2f} l{2 * s:.2f},-0.7 l0,1.4 z" fill="{INK}"/>')
        self.text((x0 + x1) / 2, y - 1.0, label, 2.8, "middle")

    def vdim(self, x, y0, y1, label, ext_from=None):
        if ext_from is not None:
            for y in (y0, y1):
                self.line(ext_from, y, x + (1.5 if x > ext_from else -1.5), y, THIN, 0.18)
        self.line(x, y0, x, y1, INK, 0.2)
        for y, s in ((y0, 1), (y1, -1)):
            self.add(f'<path d="M{x:.2f},{y:.2f} l-0.7,{2 * s:.2f} l1.4,0 z" fill="{INK}"/>')
        self.text(x - 1.0, (y0 + y1) / 2, label, 2.8, "middle", rot=-90)

    def render(self, w=420, h=297):
        hatch = ('<defs><pattern id="hatch" width="3" height="3" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">'
                 f'<line x1="0" y1="0" x2="0" y2="3" stroke="{ZONE}" stroke-width="0.4"/></pattern></defs>')
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}mm" height="{h}mm" viewBox="0 0 {w} {h}">'
                f'<rect width="{w}" height="{h}" fill="#fff"/>{hatch}' + "".join(self.el) + "</svg>")


def bom(L):
    p = L["params"]
    n_screw = sum(1 for s in L["screws"] if s.get("material") != "nylon")
    n_nyl = len(L["screws"]) - n_screw
    nb = next(b for b in L["bosses"] if b["fixing"] != "insert")
    n_ins = sum(1 for b in L["bosses"] if b["fixing"] == "insert")
    g = L["groove"]
    perim = 2 * ((g["x1"] - g["x0"]) + (g["y1"] - g["y0"])) - (8 - 2 * math.pi) * g["r"]
    m12 = sum(1 for x in L["glands"] if x["size"] == 12)
    m16 = sum(1 for x in L["glands"] if x["size"] == 16)
    return [
        ("Base", "1", "ASA, printed (moulded later)"),
        ("Lid", "1", "ASA, printed"),
        ("Lid screw, M3 x 8 pan head, A2 stainless", str(n_screw), ""),
        ("M3 brass heat-set insert, 5.7 long", str(n_screw + n_ins), "[TO CONFIRM] part; hole 4.0"),
        ("Board screw, M3 x 6 pan head + washer, A2", str(n_ins), "H1, H3, H4"),
        (f"Nylon M3 x {nb['screw_len']:.0f} screw + nylon M3 nut", "1 + 1", "H2 board fixing (antenna zone, no metal)"),
        (f"Nylon M3 x {p['nylon_lid_screw_len']:.0f} screw + nylon M3 nut", f"{n_nyl} + {n_nyl}", "lid screws over the antenna, nut in boss pocket"),
        ("Silicone O-ring cord, 2.0 mm", f"{perim + 20:.0f} mm", "joined into a loop"),
        ("Cable gland M12 x 1.5, nylon IP68 + locknut", str(m12), "[TO CONFIRM] clamp range"),
        ("Cable gland M16 x 1.5, nylon IP68 + locknut", str(m16), "[TO CONFIRM] clamp range"),
        ("Membrane vent, M12, plastic, IP67/68", "1", "[TO CONFIRM] part"),
        ("Rubber grommet + steel sleeve, M5 bolt", "4", f"[TO CONFIRM]; hole {p['grommet_hole']}, panel {p['ear_t']}"),
    ]


def main():
    with open(os.path.join(HERE, "layout.json"), encoding="utf8") as fh:
        L = json.load(fh)
    with open(os.path.join(HERE, "board.json"), encoding="utf8") as fh:
        B = json.load(fh)
    p = L["params"]
    i, f = L["interior"], L["flange"]
    h, wall, fl, lt = i["h"], p["wall"], p["floor"], p["lid_t"]
    S = Svg()
    ears = L["ears"]
    ex0 = min(e["x"] for e in ears) - p["ear_pad"]
    ex1 = max(e["x"] for e in ears) + p["ear_pad"]

    # ---- top view (lid off) ----
    ox, oy = 25 - ex0, 32 - f["y0"]

    def T(x, y):
        return ox + x, oy + y

    S.text(T(ex0, 0)[0], 18, "ESP32MCCAN main board housing  —  1:1 on A3", 5, weight="bold")
    S.text(T(ex0, 0)[0], 24, "Top view, lid off (antenna edge at top). Board coordinates: origin = board top-left.", 3, fill=THIN)
    zx0, zy0, zx1, zy1 = L["antenna_zone"]
    S.rect(*T(zx0, max(zy0, f["y0"])), *T(zx1, zy1), stroke=ZONE, w=0.3, fill="url(#hatch)")
    S.text(T((zx0 + zx1) / 2, 0)[0], T(0, zy1)[1] + 4, "ANTENNA ZONE — NO METAL (incl. bracket)", 2.8, "middle", ZONE, weight="bold")
    for e in ears:
        side = -1 if e["x"] < 0 else 1
        wx = (i["x0"] - wall) if side < 0 else (i["x1"] + wall)
        S.rect(*T(min(wx, e["x"] + side * p["ear_pad"]), e["y"] - p["ear_pad"]), *T(max(wx, e["x"] + side * p["ear_pad"]), e["y"] + p["ear_pad"]), rx=3)
        S.circle(*T(e["x"], e["y"]), p["grommet_hole"] / 2)
    S.rect(*T(f["x0"], f["y0"]), *T(f["x1"], f["y1"]), w=0.45, rx=3)
    S.rect(*T(i["x0"] - wall, i["y0"] - wall), *T(i["x1"] + wall, i["y1"] + wall), w=0.3)
    S.rect(*T(i["x0"], i["y0"]), *T(i["x1"], i["y1"]), w=0.45)
    g = L["groove"]
    S.rect(*T(g["x0"], g["y0"]), *T(g["x1"], g["y1"]), stroke=THIN, w=0.25, dash="2,1", rx=g["r"])
    o = B["outline"]
    S.rect(*T(0, 0), *T(o["w"], o["h"]), stroke=BOARD, w=0.3, dash="3,1.5", rx=1)
    S.text(*T(o["w"] / 2, o["h"] / 2 - 18), "board 140 x 100 (dashed)", 3, "middle", BOARD)
    l2 = next(pp for pp in B["parts"] if pp["ref"] == "L2")
    S.rect(*T(l2["bbox"][0], l2["bbox"][1]), *T(l2["bbox"][2], l2["bbox"][3]), stroke=BOARD, w=0.2)
    S.text(*T((l2["bbox"][0] + l2["bbox"][2]) / 2, (l2["bbox"][1] + l2["bbox"][3]) / 2), f"L2 {l2['height']:.0f} mm", 2.6, "middle", BOARD)
    for b in L["bosses"]:
        S.circle(*T(b["x"], b["y"]), b["base_d"] / 2, w=0.25)
        S.circle(*T(b["x"], b["y"]), b["top_d"] / 2, w=0.25)
        S.text(T(b["x"], 0)[0] + (6 if b["x"] < 70 else -6), T(0, b["y"])[1] + 1, b["ref"] + (" nylon" if b["fixing"] != "insert" else ""), 2.4, "start" if b["x"] < 70 else "end")
    for s in L["screws"]:
        S.circle(*T(s["x"], s["y"]), p["insert_hole"] / 2, w=0.3)
    for gl in L["glands"]:
        S.line(*T(gl["x"], i["y1"] - 6), *T(gl["x"], f["y1"] + 3), THIN, 0.2, "1,1")
    S.text(*T(i["x1"] + wall + 1, L["vent"]["y"] + 1), "vent", 2.4)
    # dims
    S.hdim(*[T(x, 0)[0] for x in (f["x0"], f["x1"])], T(0, f["y0"])[1] - 4, f"{f['x1'] - f['x0']:.1f} flange", T(0, f["y0"])[1])
    S.hdim(*[T(x, 0)[0] for x in (ex0, ex1)], T(0, f["y1"])[1] + 9, f"{ex1 - ex0:.1f} over ears", T(0, f["y1"])[1])
    S.hdim(*[T(x, 0)[0] for x in (i["x0"], i["x1"])], T(0, i["y1"])[1] - 3, f"{i['x1'] - i['x0']:.1f} inside")
    S.vdim(T(ex0, 0)[0] - 4, *[T(0, y)[1] for y in (f["y0"], f["y1"])], f"{f['y1'] - f['y0']:.1f} flange", T(f["x0"], 0)[0])
    S.vdim(T(i["x0"], 0)[0] + 6, *[T(0, y)[1] for y in (i["y0"], i["y1"])], f"{i['y1'] - i['y0']:.1f} inside")
    S.vdim(T(ex1, 0)[0] + 4, *[T(0, ears[2]["y"])[1], T(0, ears[3]["y"])[1]], f"{ears[3]['y'] - ears[2]['y']:.0f} ears", T(ex1, 0)[0])

    # ---- cable wall, seen from outside ----
    fy0 = 255.0  # page y of z = 0

    def F(x, z):
        return ox + x, fy0 - z

    S.text(F(ex0, 0)[0], F(0, h + lt)[1] - 4, "Cable wall from outside (glands: low/high rows)", 3, weight="bold")
    S.rect(*F(i["x0"] - wall, -fl), *F(i["x1"] + wall, h - p["flange_t"]), w=0.4)
    S.rect(*F(f["x0"], h - p["flange_t"]), *F(f["x1"], h), w=0.4)
    S.rect(*F(f["x0"], h), *F(f["x1"], h + lt), w=0.4)
    for e in ears:
        side = -1 if e["x"] < 0 else 1
        wx = (i["x0"] - wall) if side < 0 else (i["x1"] + wall)
        S.rect(*F(min(wx, e["x"] + side * p["ear_pad"]), -fl), *F(max(wx, e["x"] + side * p["ear_pad"]), -fl + p["ear_t"]), w=0.3)
    S.line(*F(0, p["standoff"]), *F(o["w"], p["standoff"]), BOARD, 0.25, "3,1.5")
    S.line(*F(0, p["standoff"] + o["t"]), *F(o["w"], p["standoff"] + o["t"]), BOARD, 0.25, "3,1.5")
    for gl in L["glands"]:
        x, z = F(gl["x"], gl["z"])
        S.circle(x, z, gl["hole"] / 2, w=0.35)
        S.circle(x, z, gl["hex_af"] / 2 + 2, THIN, 0.2)
        S.text(x, z + 1, f"M{gl['size']}", 2.4, "middle")
        S.text(x, F(0, -fl)[1] + 5 + (3.5 if gl["row"] == "high" else 0), f"{gl['name']} x{gl['x']:.1f} z{gl['z']:.1f}", 2.3, "middle")
    S.vdim(F(f["x1"], 0)[0] + 6, F(0, -fl)[1], F(0, h + lt)[1], f"{h + lt + fl:.1f} overall", F(f["x1"], 0)[0])
    S.vdim(F(i["x0"], 0)[0] - 10, F(0, 0)[1], F(0, h)[1], f"{h:.1f} inside", F(i["x0"] - wall, 0)[0])

    # ---- +x side view ----
    sx = T(ex1, 0)[0] + 32

    def Sd(y, z):
        return sx + (y - f["y0"]), fy0 - z

    S.text(Sd(f["y0"], 0)[0], F(0, h + lt)[1] - 4, "+x side (vent), cable wall to the right", 3, weight="bold")
    S.rect(*Sd(i["y0"] - wall, -fl), *Sd(i["y1"] + wall, h - p["flange_t"]), w=0.4)
    S.rect(*Sd(f["y0"], h - p["flange_t"]), *Sd(f["y1"], h), w=0.4)
    S.rect(*Sd(f["y0"], h), *Sd(f["y1"], h + lt), w=0.4)
    v = L["vent"]
    S.circle(*Sd(v["y"], v["z"]), v["hole"] / 2)
    S.text(Sd(v["y"], 0)[0], Sd(0, v["z"] + v["hole"] / 2 + 2)[1], f"vent y{v['y']:.0f} z{v['z']:.1f}", 2.4, "middle")
    for e in ears:
        if e["x"] > 0:
            S.rect(*Sd(e["y"] - p["ear_pad"], -fl), *Sd(e["y"] + p["ear_pad"], -fl + p["ear_t"]), w=0.3)

    # ---- BOM + notes ----
    bx, by = sx - 4, 30.0
    S.text(bx, by, "Bill of materials", 3.6, weight="bold")
    for k, (item, qty, note) in enumerate(bom(L)):
        y = by + 6 + k * 5.2
        S.text(bx, y, qty, 2.7, "end" if False else "start")
        S.text(bx + 14, y, item, 2.7)
        if note:
            S.text(bx + 14, y + 2.4, note, 2.0, fill=THIN)
    ny = by + 6 + len(bom(L)) * 5.2 + 6
    notes = [
        f"Wall {wall}, floor {fl}, draft {p['draft']} deg, standoffs {p['standoff']} (top face 6.0 dia).",
        f"Lid to L2 >= {h - (p['standoff'] + o['t'] + l2['height']):.1f} mm; groove {p['groove_w']} x {p['groove_d']} for {p['cord']} cord.",
        f"{len(L['screws'])} lid screws outside the seal; nylon ones over the antenna zone.",
        "Fit the board before the vent: the vent's inside nut overhangs the board edge.",
        "Print: ASA, >= 5 perimeters, >= 6 top/bottom, base open-side up.",
        "Source: layout.json (layout.py) from board.json (mccan.kicad_pcb).",
    ]
    for k, n in enumerate(notes):
        S.text(bx, ny + k * 4.2, n, 2.5)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf8") as fh:
        fh.write(S.render())
    print("wrote", OUT)


if __name__ == "__main__":
    main()
