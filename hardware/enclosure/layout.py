# -*- coding: utf-8 -*-
"""The housing's coordinates and design rules, from board.json and the parameter table P.

  python hardware/enclosure/layout.py      writes layout.json; exit 1 on any rule violation

Coordinates are BOARD coordinates (see extract_board.py), with z = 0 at the inside floor.
Interior x/y figures are at the top of the base wall; 1 deg draft narrows the walls toward the floor.
Fusion (build_housing.py) only draws what this file decides.
Spec: docs/superpowers/specs/2026-11-22-main-board-housing-design.md
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "layout.json")


class LayoutError(Exception):
    pass


def _gland(name, refs, size):
    # Nylon IP68 glands. Hex/nut AF are typical catalogue values [TO CONFIRM] against the glands bought.
    if size == 12:
        return {"name": name, "refs": refs, "size": 12, "hole": 12.5, "hex_af": 15.0, "nut_af": 15.0, "nut_t": 6.0}
    return {"name": name, "refs": refs, "size": 16, "hole": 16.5, "hex_af": 19.0, "nut_af": 19.0, "nut_t": 6.0}


P = {
    # shell (spec 6.2, 6.3)
    "wall": 2.5, "draft": 1.0, "floor": 2.5,
    "side_gap": 3.0,      # board edge to side and antenna walls
    "cable_gap": 22.0,    # board cable edge to cable wall
    "standoff": 8.0,      # floor to board underside (>= 5)
    "lid_gap": 4.0,       # tallest part to lid underside (>= 3)
    "min_part_clear": 3.0,
    "min_wall_gap": 2.0,  # board edge to drafted wall, at board height
    "max_extra_h": 15.0,  # how far the interior may grow to fit the gland rows
    # board fixing (6.4)
    "boss_top_d": 6.0,     # face touching the board: the board's 6 mm clear circle
    "boss_neck_h": 2.0,    # the top 2 mm stays at boss_top_d, then flares
    "boss_base_d": 10.0,   # at the floor
    # Holes whose fixing must be metal-free (antenna zone): nylon M3 screw into a captive nylon nut.
    # H2's centre is 15.75 mm from the antenna span, so any metal there reaches inside 15 mm.
    "nylon_holes": ["H2"],
    "nylon_nut_af": 5.5, "nylon_nut_t": 2.4,
    "board_screw_len": 6.0,        # M3 x 6 into the inserts (H1, H3, H4)
    "nylon_board_screw_len": 8.0,  # M3 x 8 nylon at H2: passes through the nut, tip above the hole floor
    "nylon_nut_z": 3.5, "nylon_hole_floor_z": 0.5,
    "nylon_lid_screw_len": 12.0,   # lid screws in the antenna zone: nylon M3 x 12 into a captive nylon
                                   # nut in a pocket at the bottom of the insert boss (outside the seal)
    # lid joint (6.5)
    "lid_t": 3.0, "flange_t": 4.0,
    "groove_inset": 3.0,  # groove centre line, outward from the inner wall face
    "groove_w": 2.7, "groove_d": 1.5, "cord": 2.0,
    "screw_inset": 8.0,   # screw line, outward from the inner wall face
    "flange_inset": 12.5, # flange outer edge, outward from the inner wall face
    "screw_d": 3.0, "screw_clear_d": 3.4,
    "insert_od": 4.6, "insert_hole": 4.0, "insert_len": 5.7,
    "insert_boss_d": 8.0, "insert_boss_depth": 8.5,  # below the flange top, outside the wall
    "max_pitch": 60.0,
    "skirt_t": 1.5, "skirt_h": 3.0, "skirt_clear": 0.3,
    "rib_t": 2.0, "rib_h": 6.0,
    # metal radius per kind, for the antenna check: M3 pan head 5.5 dia; M5 washer 10 dia
    "metal_r": {"screws": 2.75, "ears": 5.0},
    # glands (6.6), left to right
    "glands": [
        _gland("feedA", ["J1"], 12), _gland("front", ["J3"], 12), _gland("rear", ["J4", "J5"], 12),
        _gland("CAN", ["J8"], 12), _gland("podL", ["J10"], 16), _gland("feedB", ["J9"], 16),
        _gland("podR", ["J11"], 16),
    ],
    "gland_edge": 1.5,    # hex corner to the flange underside
    "tool_gap": 5.0,      # spanner/socket room: hex corner to hex corner, to the floor and to the drafted wall
    # vent (6.7)
    "vent_hole": 12.5, "vent_body_d": 18.0, "vent_from_cable_wall": 52.0,  # clear of the +x ear's gussets  # vent z is derived: its inside nut clears the board top by 1.5 mm
    # ears (6.8)
    "ear_t": 3.0, "ear_from_flange": 9.0, "ear_pad": 9.0, "grommet_hole": 9.5, "ear_y_in": 20.0,
    "gusset_h": 15.0, "gusset_t": 3.0,  # two triangular gussets per ear, up the wall (review I6)
}


def _ac(af):
    """Across-corners radius of a hex with across-flats af."""
    return af / math.sqrt(3)


def _tallest(board):
    return max(p["height"] for p in board["parts"])


def _place_glands(board, p, i, flange_under):
    tails = {t["ref"]: t for t in board["tails"]}
    gl = []
    for k, g in enumerate(p["glands"]):
        xs = [x for r in g["refs"] for x, _, _ in tails[r]["pads"]]
        R = _ac(g["hex_af"])
        z = R + p["tool_gap"] + 0.01 if k % 2 == 0 else flange_under - R - p["gland_edge"]
        gl.append(dict(g, x=sum(xs) / len(xs), z=z, row="low" if k % 2 == 0 else "high"))
    if any(g["z"] - _ac(g["hex_af"]) < p["tool_gap"] - 1e-9 for g in gl):
        raise LayoutError("gland rows do not fit the wall height")

    def need(a, b):
        d = _ac(a["hex_af"]) + _ac(b["hex_af"]) + p["tool_gap"] + 0.01  # margin over 3-decimal rounding
        dz = abs(a["z"] - b["z"])
        return math.sqrt(d * d - dz * dz) if d > dz else 0.0

    # sweep left to right: each gland at least `need` from every earlier one
    for k in range(1, len(gl)):
        gl[k]["x"] = max(gl[k]["x"], max(gl[j]["x"] + need(gl[j], gl[k]) for j in range(k)))
    inset = flange_under * math.tan(math.radians(p["draft"]))  # drafted wall at the floor (worst case)
    lo = i["x0"] + inset + p["tool_gap"] + 0.01 + _ac(gl[0]["hex_af"])
    hi = i["x1"] - inset - p["tool_gap"] - 0.01 - _ac(gl[-1]["hex_af"])
    if gl[-1]["x"] > hi:
        shift = gl[-1]["x"] - hi
        for g in gl:
            g["x"] -= shift
    if gl[0]["x"] < lo:
        # left end hit the wall: re-sweep from the left wall
        gl[0]["x"] = lo
        for k in range(1, len(gl)):
            gl[k]["x"] = max(gl[k]["x"], max(gl[j]["x"] + need(gl[j], gl[k]) for j in range(k)))
        if gl[-1]["x"] > hi:
            raise LayoutError(f"glands do not fit the cable wall: need {gl[-1]['x'] - hi:.1f} mm more")
    for g in gl:
        g["x"] = round(g["x"], 3)
        g["z"] = round(g["z"], 3)
    return gl


def _fill(a, b, max_pitch):
    n = max(1, math.ceil(abs(b - a) / max_pitch - 1e-9))
    return [a + (b - a) * k / n for k in range(n + 1)]


def _boss_hits_gland(x, p, gl, h):
    """Insert boss under the cable-wall flange (x +/- r, z from h - depth up) vs high-row gland hexes."""
    r = p["insert_boss_d"] / 2
    zb = h - p["insert_boss_depth"]
    for g in gl:
        R = _ac(g["hex_af"])
        dx = max(abs(g["x"] - x) - r, 0)
        dz = max(zb - g["z"], 0)
        if math.hypot(dx, dz) < R + 1:
            return True
    return False


def build(board, p=P):
    o = board["outline"]
    i = {"x0": -p["side_gap"], "y0": -p["side_gap"], "x1": o["w"] + p["side_gap"], "y1": o["h"] + p["cable_gap"]}
    h0 = p["standoff"] + o["t"] + _tallest(board) + p["lid_gap"]
    err = None
    for extra in range(0, int(p["max_extra_h"]) + 1):
        h = h0 + extra
        try:
            gl = _place_glands(board, p, i, h - p["flange_t"])
            break
        except LayoutError as e:
            err = e
    else:
        raise LayoutError(f"gland: {err} (even with {p['max_extra_h']} mm extra height)")
    i["h"] = round(h, 3)

    def inflate(d):
        return [i["x0"] - d, i["y0"] - d, i["x1"] + d, i["y1"] + d]

    sx0, sy0, sx1, sy1 = inflate(p["screw_inset"])
    zx0, zy0, zx1, zy1 = board["antenna"]["zone"]
    mr = p["metal_r"]["screws"]

    # Antenna (top, y = sy0) side: filled like the others; screws inside the zone are nylon (no metal).
    top = _fill(sx0, sx1, p["max_pitch"])
    right = _fill(sy0, sy1, p["max_pitch"])
    # Cable side (y = sy1), right to left, moved off any high-row gland's hex where needed.
    def dodge(x):
        if not _boss_hits_gland(x, p, gl, h):
            return x
        for step in range(1, 61):
            for c in (x + 0.5 * step, x - 0.5 * step):
                if sx0 <= c <= sx1 and not _boss_hits_gland(c, p, gl, h):
                    return c
        raise LayoutError(f"gland: no clear place for a cable-side lid screw near x={x}")

    bottom = [dodge(x) for x in _fill(sx1, sx0, p["max_pitch"])]
    for _ in range(10):  # a dodged screw can open a gap: add a screw midway and dodge again
        gaps = [k for k in range(len(bottom) - 1) if abs(bottom[k] - bottom[k + 1]) > p["max_pitch"]]
        if not gaps:
            break
        k = gaps[0]
        bottom.insert(k + 1, dodge((bottom[k] + bottom[k + 1]) / 2))
        bottom = sorted(bottom, reverse=True)
    left = _fill(sy1, sy0, p["max_pitch"])
    loop = ([{"x": x, "y": sy0} for x in top]
            + [{"x": sx1, "y": y} for y in right[1:]]
            + [{"x": x, "y": sy1} for x in bottom[1:]]
            + [{"x": sx0, "y": y} for y in left[1:-1]])
    def material(s):
        inside = s["x"] + mr > zx0 and s["x"] - mr < zx1 and s["y"] + mr > zy0 and s["y"] - mr < zy1
        return "nylon" if inside else "steel"
    loop = [{"x": round(s["x"], 3), "y": round(s["y"], 3), "material": material(s)} for s in loop]

    gx0, gy0, gx1, gy1 = inflate(p["groove_inset"])
    fx0, fy0, fx1, fy1 = inflate(p["flange_inset"])
    ex_l, ex_r = fx0 - p["ear_from_flange"], fx1 + p["ear_from_flange"]
    ears = [{"x": x, "y": y} for x in (ex_l, ex_r) for y in (i["y0"] + p["ear_y_in"], i["y1"] - p["ear_y_in"])]

    bosses = []
    for hole in board["holes"]:
        top_d = p["boss_top_d"]
        base_d = p["boss_base_d"]
        nylon = hole["ref"] in p["nylon_holes"]
        bb = {"ref": hole["ref"], "x": hole["x"], "y": hole["y"], "top_d": top_d, "base_d": round(base_d, 3),
              "h": p["standoff"], "neck_h": p["boss_neck_h"], "fixing": "nylon_nut" if nylon else "insert",
              "screw_len": p["nylon_board_screw_len"] if nylon else p["board_screw_len"]}
        if nylon:
            bb.update(nut_z=p["nylon_nut_z"], hole_floor_z=p["nylon_hole_floor_z"])
        bosses.append(bb)

    w = o["w"]
    ribs = [
        # along the antenna wall, then one across at the antenna's right end, both hanging from the lid
        {"x0": i["x0"], "y0": 4.0 - p["rib_t"] / 2, "x1": i["x1"], "y1": 4.0 + p["rib_t"] / 2, "h": p["rib_h"]},
        {"x0": 95.0 - p["rib_t"] / 2, "y0": i["y0"], "x1": 95.0 + p["rib_t"] / 2, "y1": i["y1"], "h": p["rib_h"]},
    ]
    return {
        "params": p,
        "board_origin": [0.0, 0.0, p["standoff"]],
        "interior": i,
        "floor": p["floor"],
        "wall": p["wall"],
        "flange": {"x0": fx0, "y0": fy0, "x1": fx1, "y1": fy1, "t": p["flange_t"]},
        "groove": {"x0": gx0, "y0": gy0, "x1": gx1, "y1": gy1, "w": p["groove_w"], "d": p["groove_d"],
                   "r": p["groove_inset"] + 1.0},
        "screw_rect": [sx0, sy0, sx1, sy1],
        "screw_loop": loop,
        "screws": loop,
        "bosses": bosses,
        "glands": gl,
        "vent": {"wall": "+x", "y": i["y1"] - p["vent_from_cable_wall"],
                 "z": round(p["standoff"] + o["t"] + p["vent_body_d"] / 2 + 1.5, 3), "hole": p["vent_hole"],
                 "body_d": p["vent_body_d"]},
        "ears": ears,
        "lid": {"z_underside": i["h"], "t": p["lid_t"], "ribs": ribs},
        "antenna_zone": board["antenna"]["zone"],
        "board_w": w,
    }


def _overlap(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def check(board, lay, p=P):
    v = []
    o = board["outline"]
    i = lay["interior"]
    zone = board["antenna"]["zone"]

    # antenna: no metal body overlaps the zone
    for kind in ("screws", "ears"):
        r = p["metal_r"][kind]
        for s in lay[kind]:
            if s.get("material", "steel") == "nylon":
                continue
            if _overlap([s["x"] - r, s["y"] - r, s["x"] + r, s["y"] + r], zone):
                v.append(f"antenna: {kind} at ({s['x']}, {s['y']}) inside the no-metal zone")
    for b in lay["bosses"]:
        r = p["insert_od"] / 2
        if b["fixing"] == "insert" and _overlap([b["x"] - r, b["y"] - r, b["x"] + r, b["y"] + r], zone):
            v.append(f"antenna: insert at {b['ref']} inside the no-metal zone")

    # lid and rib clearance over every part
    zb = p["standoff"] + o["t"]
    for part in board["parts"]:
        if part["ref"] == "U5":  # its courtyard includes the antenna clearance; body height still checked
            box = [part["x"] - 9, part["y"] - 12.75, part["x"] + 9, part["y"] + 12.75]
        else:
            box = part["bbox"]
        top = zb + part["height"]
        if lay["lid"]["z_underside"] - top < p["min_part_clear"] - 1e-9:
            v.append(f"lid: {part['ref']} top {top:.2f} within {p['min_part_clear']} of the lid")
        for rib in lay["lid"]["ribs"]:
            if _overlap(box, [rib["x0"], rib["y0"], rib["x1"], rib["y1"]]):
                if lay["lid"]["z_underside"] - rib["h"] - top < p["min_part_clear"] - 1e-9:
                    v.append(f"lid: rib over {part['ref']} closer than {p['min_part_clear']}")

    # board to drafted wall at board height
    inset = (i["h"] - p["standoff"]) * math.tan(math.radians(p["draft"]))
    gaps = [-i["x0"] - inset, i["x1"] - o["w"] - inset, -i["y0"] - inset, i["y1"] - o["h"] - inset]
    if min(gaps) < p["min_wall_gap"]:
        v.append(f"wall: board to wall gap {min(gaps):.2f} < {p['min_wall_gap']}")

    # glands
    gl = lay["glands"]
    flange_under = i["h"] - p["flange_t"]
    for a, ga in enumerate(gl):
        ra = _ac(ga["hex_af"])
        if ga["z"] - ra < 1:
            v.append(f"gland {ga['name']} too close to the floor")
        if ga["z"] + ra > flange_under - 1:
            v.append(f"gland {ga['name']} hits the flange")
        inset = (i["h"] - ga["z"]) * math.tan(math.radians(p["draft"]))
        if ga["x"] - ra < i["x0"] + inset + p["tool_gap"] - 1e-6 or ga["x"] + ra > i["x1"] - inset - p["tool_gap"] + 1e-6:
            v.append(f"gland {ga['name']} without tool room at the side wall")
        if ga["z"] - ra < p["tool_gap"] - 1e-6:
            v.append(f"gland {ga['name']} without tool room above the floor")
        if i["y1"] - ga["nut_t"] < o["h"] + 2:
            v.append(f"gland {ga['name']} nut within 2 mm of the board edge")
        for gb in gl[a + 1:]:
            d = math.hypot(ga["x"] - gb["x"], ga["z"] - gb["z"])
            if d < ra + _ac(gb["hex_af"]) + p["tool_gap"] - 1e-6:
                v.append(f"gland {ga['name']}/{gb['name']} overlap ({d:.1f} mm)")
    for s in lay["screws"]:
        if abs(s["y"] - lay["screw_rect"][3]) < 1e-6 and _boss_hits_gland(s["x"], p, gl, i["h"]):
            v.append(f"gland: screw boss at x={s['x']} hits a gland")

    # screws: pitch (except across the antenna span), and outside the groove
    loop = lay["screw_loop"]
    for a, b in zip(loop, loop[1:] + loop[:1]):
        d = math.hypot(a["x"] - b["x"], a["y"] - b["y"])
        if d > p["max_pitch"] + 1e-6:
            v.append(f"pitch: {d:.1f} mm between screws at ({a['x']},{a['y']}) and ({b['x']},{b['y']})")
    g = lay["groove"]
    for s in lay["screws"]:
        dx = max(g["x0"] - s["x"], s["x"] - g["x1"], 0)
        dy = max(g["y0"] - s["y"], s["y"] - g["y1"], 0)
        if math.hypot(dx, dy) < p["groove_w"] / 2 + p["insert_od"] / 2 + 1 - 1e-6:
            v.append(f"groove: screw at ({s['x']},{s['y']}) too close to the seal")

    # bosses
    for b in lay["bosses"]:
        if b["fixing"] != "insert":
            tip = p["standoff"] + o["t"] - b["screw_len"]
            if tip > b["nut_z"] - p["nylon_nut_t"] / 2 - 0.5:
                v.append(f"boss {b['ref']}: nylon screw does not pass through its nut (tip z {tip:.1f})")
            if tip < b["hole_floor_z"] + 0.3:
                v.append(f"boss {b['ref']}: nylon screw bottoms in its hole (tip z {tip:.1f})")
        if b["top_d"] > 6.0 + 1e-9:
            v.append(f"boss {b['ref']}: top face wider than the board's 6 mm clear circle")
        for t in board["tails"]:
            for x, y, _ in t["pads"]:
                if math.hypot(x - b["x"], y - b["y"]) < b["base_d"] / 2 + 1:
                    v.append(f"boss {b['ref']}: within 1 mm of {t['ref']} pad")

    # vent: its inside nut sits beside the board edge, so it must be above the board and below the flange
    ve = lay["vent"]
    board_top = p["standoff"] + o["t"]
    if ve["z"] - ve["body_d"] / 2 < board_top + 1:
        v.append(f"vent: inside nut within 1 mm of the board (z {ve['z']})")
    if ve["z"] + ve["body_d"] / 2 > i["h"] - p["flange_t"] - 1:
        v.append("vent: hits the flange")
    rs = ve["body_d"] / 2 + 2
    for e in lay["ears"]:
        if e["x"] < 0:
            continue
        for gy in (e["y"] - p["ear_pad"] + p["gusset_t"] / 2, e["y"] + p["ear_pad"] - p["gusset_t"] / 2):
            dy = abs(gy - ve["y"]) - p["gusset_t"] / 2
            dz = (ve["z"] - rs) - (p["ear_t"] - p["floor"] + p["gusset_h"])
            if dy < rs + 1 and dz < 1:
                v.append(f"vent: spot face hits the ear gusset at y {gy}")
    x_in = i["x1"] - (i["h"] - ve["z"]) * math.tan(math.radians(p["draft"]))
    nut = [x_in - 5.0, ve["y"] - ve["body_d"] / 2, x_in, ve["y"] + ve["body_d"] / 2]
    for part in board["parts"]:
        if part["ref"] != "U5" and _overlap(part["bbox"], nut):
            if zb + part["height"] > ve["z"] - ve["body_d"] / 2 - 1:
                v.append(f"vent: inside nut within 1 mm of {part['ref']}")
    for e in lay["ears"]:
        if abs(e["y"] - ve["y"]) < (ve["body_d"] / 2 + p["ear_pad"]) and ve["z"] - ve["body_d"] / 2 < p["ear_t"] - p["floor"] + 1:
            v.append("vent: hits an ear")
    return v


if __name__ == "__main__":
    sys.path.insert(0, HERE)
    with open(os.path.join(HERE, "board.json"), encoding="utf8") as fh:
        board = json.load(fh)
    lay = build(board, P)
    viol = check(board, lay, P)
    with open(OUT, "w", encoding="utf8") as fh:
        json.dump(lay, fh, indent=1)
    i = lay["interior"]
    fl = lay["flange"]
    print(f"interior {i['x1'] - i['x0']:.1f} x {i['y1'] - i['y0']:.1f} x {i['h']:.1f} mm; "
          f"flange {fl['x1'] - fl['x0']:.1f} x {fl['y1'] - fl['y0']:.1f}; {len(lay['screws'])} lid screws; "
          "glands " + ", ".join(f"{g['name']}@({g['x']:.1f},{g['z']:.1f})" for g in lay["glands"]))
    for s in viol:
        print("VIOLATION", s)
    sys.exit(1 if viol else 0)
