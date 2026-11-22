# -*- coding: utf-8 -*-
"""Tests for layout.py: the housing's coordinates and its design rules.

  python hardware/enclosure/test_layout.py      exit 1 on any failure
"""
import copy
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import extract_board as E  # noqa: E402
import layout as L  # noqa: E402

BOARD = E.load(E.PCB)
FAILS = []


def check(name, cond, detail=""):
    if not cond:
        FAILS.append(f"{name}: {detail}")


def near(a, b, tol=0.01):
    return abs(a - b) <= tol


def fresh(**over):
    p = copy.deepcopy(L.P)
    p.update(over)
    return p, L.build(BOARD, p)


def test_default_passes():
    p, lay = fresh()
    v = L.check(BOARD, lay, p)
    check("default passes", v == [], v)


def test_interior():
    _, lay = fresh()
    i = lay["interior"]
    check("interior", (near(i["x0"], -3), near(i["y0"], -3), near(i["x1"], 143), near(i["y1"], 122)) == (True,) * 4, i)
    check("interior size", near(i["x1"] - i["x0"], 146) and near(i["y1"] - i["y0"], 125), i)


def test_lid_clearance_tracks_standoff():
    _, lay = fresh()
    z8 = lay["lid"]["z_underside"]
    check("lid clear of L2", z8 - (8 + 1.6 + 24.0) >= 3, z8)
    # The lid always clears L2 by lid_gap; the gland rows may set the height instead, so use a
    # standoff tall enough that L2 governs.
    _, lay20 = fresh(standoff=20)
    z20 = lay20["lid"]["z_underside"]
    check("lid clears L2 at standoff 20", z20 >= 20 + 1.6 + 24.0 + L.P["lid_gap"] - 1e-9, z20)
    check("lid moves with standoff", z20 > z8, (z8, z20))


def test_antenna_zone_rejects_screw():
    p, lay = fresh()
    lay["screws"].append({"x": 90.0, "y": -8.0, "material": "steel"})
    v = L.check(BOARD, lay, p)
    check("antenna screw rejected", any("antenna" in s for s in v), v)


def test_no_default_metal_in_zone():
    _, lay = fresh()
    zx0, zy0, zx1, zy1 = BOARD["antenna"]["zone"]
    for kind in ("screws", "ears"):
        for s in lay[kind]:
            if s.get("material") == "nylon":
                continue  # nylon lid screw + nylon nut: no metal (review I4)
            r = L.P["metal_r"][kind]
            inside = (s["x"] + r > zx0 and s["x"] - r < zx1 and s["y"] + r > zy0 and s["y"] - r < zy1)
            check("metal outside zone " + kind, not inside, s)
    for b in lay["bosses"]:
        if b["fixing"] != "insert":
            continue  # nylon screw + nylon nut: no metal
        r = L.P["insert_od"] / 2
        inside = (b["x"] + r > zx0 and b["x"] - r < zx1 and b["y"] + r > zy0 and b["y"] - r < zy1)
        check("insert outside zone", not inside, b)


def test_screw_pitch():
    p, lay = fresh()
    loop = lay["screw_loop"]  # screws in order round the flange, closed
    zx0, _, zx1, _ = BOARD["antenna"]["zone"]
    for a, b in zip(loop, loop[1:] + loop[:1]):
        d = math.hypot(a["x"] - b["x"], a["y"] - b["y"])
        spans_antenna = (a["y"] == b["y"] == lay["screw_rect"][1] and min(a["x"], b["x"]) < zx1 and max(a["x"], b["x"]) > zx0)
        if not spans_antenna:
            check("screw pitch", d <= p["max_pitch"] + 1e-6, (a, b, round(d, 2)))


def test_screws_outside_groove():
    p, lay = fresh()
    g = lay["groove"]
    for s in lay["screws"]:
        # distance from screw centre to the groove centre-line rectangle, measured outward
        dx = max(g["x0"] - s["x"], s["x"] - g["x1"], 0)
        dy = max(g["y0"] - s["y"], s["y"] - g["y1"], 0)
        d = math.hypot(dx, dy)
        check("screw outside groove", d >= p["groove_w"] / 2 + p["insert_od"] / 2 + 1 - 1e-6, (s, round(d, 2)))


def test_h2_is_nylon():
    _, lay = fresh()
    fix = {b["ref"]: b["fixing"] for b in lay["bosses"]}
    check("H2 nylon", fix == {"H1": "insert", "H2": "nylon_nut", "H3": "insert", "H4": "insert"}, fix)


def test_gland_overlap_detected():
    p = copy.deepcopy(L.P)
    for g in p["glands"]:
        g["hex_af"] = 30.0
        g["nut_af"] = 30.0
    try:
        lay = L.build(BOARD, p)
        v = L.check(BOARD, lay, p)
    except L.LayoutError as e:
        v = [str(e)]
    check("gland overlap detected", any("gland" in s for s in v), v)


def test_default_glands():
    p, lay = fresh()
    gl = lay["glands"]
    check("seven glands", [g["name"] for g in gl] == ["feedA", "front", "rear", "CAN", "podL", "feedB", "podR"], gl)
    i = lay["interior"]
    flange_under = lay["lid"]["z_underside"] - p["flange_t"]
    for a in range(len(gl)):
        ga = gl[a]
        ra = ga["hex_af"] / math.sqrt(3)  # across-corners radius
        check("gland above floor " + ga["name"], ga["z"] - ra >= 1, ga)
        check("gland below flange " + ga["name"], ga["z"] + ra <= flange_under - 1, ga)
        check("gland inside x " + ga["name"], ga["x"] - ra >= i["x0"] + 1 and ga["x"] + ra <= i["x1"] - 1, ga)
        for b in range(a + 1, len(gl)):
            gb = gl[b]
            rb = gb["hex_af"] / math.sqrt(3)
            d = math.hypot(ga["x"] - gb["x"], ga["z"] - gb["z"])
            check("gland spacing", d >= ra + rb + 2, (ga["name"], gb["name"], round(d, 2)))


def test_vent_clear_of_board():
    p, lay = fresh()
    v = lay["vent"]
    board_top = p["standoff"] + BOARD["outline"]["t"]
    check("vent nut above board", v["z"] - v["body_d"] / 2 >= board_top + 1, v)
    check("vent below flange", v["z"] + v["body_d"] / 2 <= lay["lid"]["z_underside"] - p["flange_t"] - 1, v)


def test_vent_rule_catches_low_vent():
    p, lay = fresh()
    lay["vent"]["z"] = 12.0  # above the ears, inside the board height
    viol = L.check(BOARD, lay, p)
    check("low vent rejected", any("vent" in s and "board" in s for s in viol), viol)


def test_h2_screw_reaches_through_nut():
    # I1: the nylon screw must pass fully through the nylon nut, and stop above the hole floor.
    p, lay = fresh()
    b = next(b for b in lay["bosses"] if b["ref"] == "H2")
    tip = p["standoff"] + BOARD["outline"]["t"] - b["screw_len"]
    nut_bottom = b["nut_z"] - p["nylon_nut_t"] / 2
    check("H2 screw through nut", tip <= nut_bottom - 0.5, (tip, nut_bottom))
    check("H2 screw above hole floor", tip >= b["hole_floor_z"] + 0.3, (tip, b["hole_floor_z"]))


def test_vent_nut_clear_of_parts():
    # I2: the vent's inside nut overhangs the board edge; every part under it must clear by 1 mm.
    p, lay = fresh()
    lay["vent"]["z"] = p["standoff"] + BOARD["outline"]["t"] + lay["vent"]["body_d"] / 2 + 0.5
    BOARD["parts"].append({"ref": "TALL", "x": 139, "y": lay["vent"]["y"], "rot": 0,
                           "bbox": [138.5, lay["vent"]["y"] - 1, 139.5, lay["vent"]["y"] + 1], "height": 5.0, "height_src": "table"})
    try:
        viol = L.check(BOARD, lay, p)
    finally:
        BOARD["parts"].pop()
    check("vent nut over a tall part rejected", any("vent" in s and "TALL" in s for s in viol), viol)


def test_antenna_span_clamped_with_nylon():
    # I4: no unclamped seal span; screws inside the antenna zone must be nylon.
    p, lay = fresh()
    loop = lay["screw_loop"]
    worst = max(math.hypot(a["x"] - b["x"], a["y"] - b["y"]) for a, b in zip(loop, loop[1:] + loop[:1]))
    check("max lid screw pitch everywhere", worst <= p["max_pitch"] + 1e-6, round(worst, 2))
    zx0, zy0, zx1, zy1 = BOARD["antenna"]["zone"]
    r = p["metal_r"]["screws"]
    for s in lay["screws"]:
        inside = s["x"] + r > zx0 and s["x"] - r < zx1 and s["y"] + r > zy0 and s["y"] - r < zy1
        if inside:
            check("zone screw is nylon", s.get("material") == "nylon", s)
    check("some nylon screws", any(s.get("material") == "nylon" for s in lay["screws"]), lay["screws"])


def test_glands_have_tool_room():
    # I5: socket/spanner room round every hex, and clear of the DRAFTED inner wall.
    p, lay = fresh()
    gl = lay["glands"]
    i = lay["interior"]
    tan = math.tan(math.radians(p["draft"]))
    for a, ga in enumerate(gl):
        ra = ga["hex_af"] / math.sqrt(3)
        x0 = i["x0"] + (i["h"] - ga["z"]) * tan
        x1 = i["x1"] - (i["h"] - ga["z"]) * tan
        check("nut off drafted wall " + ga["name"], ga["x"] - ra >= x0 + p["tool_gap"] - 1e-6 and ga["x"] + ra <= x1 - p["tool_gap"] + 1e-6, ga)
        check("nut off floor " + ga["name"], ga["z"] - ra >= p["tool_gap"] - 1e-6, ga)
        for gb in gl[a + 1:]:
            rb = gb["hex_af"] / math.sqrt(3)
            d = math.hypot(ga["x"] - gb["x"], ga["z"] - gb["z"])
            check("hex tool gap", d >= ra + rb + p["tool_gap"] - 1e-6, (ga["name"], gb["name"], round(d, 2)))
    check("tool gap is real", p["tool_gap"] >= 5.0, p.get("tool_gap"))


def test_vent_clear_of_gussets():
    p, lay = fresh()
    v = lay["vent"]
    rs = v["body_d"] / 2 + 2
    for e in lay["ears"]:
        if e["x"] < 0:
            continue
        for gy in (e["y"] - p["ear_pad"] + p["gusset_t"] / 2, e["y"] + p["ear_pad"] - p["gusset_t"] / 2):
            dy = abs(gy - v["y"]) - p["gusset_t"] / 2
            dz = (v["z"] - rs) - (p["ear_t"] - p["floor"] + p["gusset_h"])
            check("vent clear of gusset", dy >= rs + 1 or dz >= 1, (gy, v["y"], round(dy, 2), round(dz, 2)))


def test_bosses():
    p, lay = fresh()
    check("four bosses", len(lay["bosses"]) == 4, lay["bosses"])
    for b in lay["bosses"]:
        check("boss top 6", near(b["top_d"], 6.0), b)
        r = b["base_d"] / 2
        for t in BOARD["tails"]:
            for x, y, d in t["pads"]:
                check("tail clear of boss", math.hypot(x - b["x"], y - b["y"]) >= r + 1, (t["ref"], b))


if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_") and callable(f):
            f()
    for f in FAILS:
        print("FAIL", f)
    print(f"{'FAILED' if FAILS else 'OK'}: {len(FAILS)} failure(s)")
    sys.exit(1 if FAILS else 0)
