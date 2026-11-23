# -*- coding: utf-8 -*-
"""Build the ESP32MCCAN housing in Autodesk Fusion from layout.json.

Runs inside Fusion (Fusion's embedded Python), either as a Fusion script (run(context)) or via the
Fusion MCP with a wrapper that exec()s this file and calls main(layout_path, ...).

Fusion only draws: every dimension comes from layout.json, which layout.py writes and checks.
Housing coordinates (mm): board top-left (0, 0), +x right, +y toward the cable edge, z = 0 at the
inside floor. Fusion coordinates (cm): X = x/10, Y = -y/10, Z = z/10, so the antenna edge is +Y.
The model is built as direct-modelling bodies from temporary B-Rep solids. Edit dimensions in
layout.py and re-run; do not hand-edit the bodies if the change must survive a regeneration.
"""
import json
import math
import os

import adsk.core
import adsk.fusion

TBM = None
BOOL = adsk.fusion.BooleanTypes
BIG = 1000.0  # mm, half-space cutter size


# ---------- primitives (housing mm in, temporary bodies out) ----------
def P3(x, y, z):
    return adsk.core.Point3D.create(x / 10.0, -y / 10.0, z / 10.0)


def V3(x, y, z):
    return adsk.core.Vector3D.create(x, -y, z)


def obox(cx, cy, cz, ldir, wdir, length, width, height):
    b = adsk.core.OrientedBoundingBox3D.create(P3(cx, cy, cz), V3(*ldir), V3(*wdir), length / 10.0, width / 10.0, height / 10.0)
    return TBM.createBox(b)


def box(x0, y0, z0, x1, y1, z1):
    return obox((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2, (1, 0, 0), (0, 1, 0), x1 - x0, y1 - y0, z1 - z0)


def cyl(a, b, r, r2=None):
    return TBM.createCylinderOrCone(P3(*a), r / 10.0, P3(*b), (r if r2 is None else r2) / 10.0)


def union(*bodies):
    t = bodies[0]
    for b in bodies[1:]:
        assert TBM.booleanOperation(t, b, BOOL.UnionBooleanType), "union failed"
    return t


def cut(t, *tools):
    for b in tools:
        assert TBM.booleanOperation(t, b, BOOL.DifferenceBooleanType), "cut failed"
    return t


def intersect(t, b):
    assert TBM.booleanOperation(t, b, BOOL.IntersectionBooleanType), "intersect failed"
    return t


def rrect(x0, y0, x1, y1, r, z0, z1):
    """Rounded-rectangle prism."""
    r = min(r, (x1 - x0) / 2 - 0.01, (y1 - y0) / 2 - 0.01)
    b = union(box(x0 + r, y0, z0, x1 - r, y1, z1), box(x0, y0 + r, z0, x1, y1 - r, z1))
    for cx in (x0 + r, x1 - r):
        for cy in (y0 + r, y1 - r):
            b = union(b, cyl((cx, cy, z0), (cx, cy, z1), r))
    return b


def frustum(x0, y0, x1, y1, z0, z1, draft_deg):
    """Box whose sides lean in by draft_deg going down from z1 (top) to z0."""
    a = math.radians(draft_deg)
    b = box(x0, y0, z0, x1, y1, z1)
    for (ux, uy), (px, py) in (((-1, 0), (x0, 0)), ((1, 0), (x1, 0)), ((0, -1), (0, y0)), ((0, 1), (0, y1))):
        n = (ux * math.cos(a), uy * math.cos(a), -math.sin(a))           # outward normal of the drafted face
        w = (-uy, ux, 0)
        pt = (px if ux else (x0 + x1) / 2, py if uy else (y0 + y1) / 2, z1)
        c = (pt[0] + n[0] * BIG / 2, pt[1] + n[1] * BIG / 2, pt[2] + n[2] * BIG / 2)
        cut(b, obox(c[0], c[1], c[2], n, w, BIG, BIG, BIG))
    return b


def hexprism(cx, cy, cz, axis, af, length):
    """Hex prism, across-flats af, centred at c, along axis 'x', 'y' or 'z'."""
    ax = {"x": (1, 0, 0), "y": (0, 1, 0), "z": (0, 0, 1)}[axis]
    # two unit vectors perpendicular to the axis
    e1 = {"x": (0, 1, 0), "y": (1, 0, 0), "z": (1, 0, 0)}[axis]
    e2 = tuple(ax[(i + 1) % 3] * e1[(i + 2) % 3] - ax[(i + 2) % 3] * e1[(i + 1) % 3] for i in range(3))
    body = None
    for k in range(3):
        t = math.radians(60 * k)
        ld = tuple(math.cos(t) * e1[i] + math.sin(t) * e2[i] for i in range(3))
        wd = tuple(-math.sin(t) * e1[i] + math.cos(t) * e2[i] for i in range(3))
        # height direction = ld x wd = the axis (up to sign; the box is symmetric)
        b = obox(cx, cy, cz, ld, wd, af, af * 2, length)
        body = b if body is None else intersect(body, b)
    return body


# ---------- housing ----------
def build_base(L):
    p = L["params"]
    i = L["interior"]
    h, wall, fl = i["h"], p["wall"], p["floor"]
    tan = math.tan(math.radians(p["draft"]))
    # shell: drafted outer block minus drafted cavity
    base = frustum(i["x0"] - wall, i["y0"] - wall, i["x1"] + wall, i["y1"] + wall, -fl, h, p["draft"])
    cut(base, frustum(i["x0"], i["y0"], i["x1"], i["y1"], 0, h + 0.001, p["draft"]))
    # flange ring at the top
    f = L["flange"]
    ring = rrect(f["x0"], f["y0"], f["x1"], f["y1"], 3.0, h - p["flange_t"], h)
    cut(ring, box(i["x0"], i["y0"], h - p["flange_t"] - 1, i["x1"], i["y1"], h + 1))
    union(base, ring)
    # insert bosses under the flange at every lid screw, then the insert holes
    for s in L["screws"]:
        union(base, cyl((s["x"], s["y"], h - p["insert_boss_depth"]), (s["x"], s["y"], h - p["flange_t"] + 0.01),
                        p["insert_boss_d"] / 2))
    # the insert bosses must not intrude into the cavity
    cut(base, frustum(i["x0"], i["y0"], i["x1"], i["y1"], 0, h + 0.001, p["draft"]))
    for s in L["screws"]:
        if s.get("material") == "nylon":
            zb = h - p["insert_boss_depth"]
            cut(base, cyl((s["x"], s["y"], zb - 0.1), (s["x"], s["y"], h + 0.1), p["screw_clear_d"] / 2))
            nt = p["nylon_nut_t"] + 0.3
            cut(base, hexprism(s["x"], s["y"], zb + nt / 2 - 0.05, "z", p["nylon_nut_af"] + 0.3, nt + 0.1))
        else:
            cut(base, cyl((s["x"], s["y"], h - p["insert_len"] - 0.5), (s["x"], s["y"], h + 0.1), p["insert_hole"] / 2))
    # gasket groove: rounded ring on the top face
    g = L["groove"]
    gw = g["w"] / 2
    groove = rrect(g["x0"] - gw, g["y0"] - gw, g["x1"] + gw, g["y1"] + gw, g["r"] + gw, h - g["d"], h + 0.1)
    cut(groove, rrect(g["x0"] + gw, g["y0"] + gw, g["x1"] - gw, g["y1"] - gw, g["r"] - gw, h - g["d"] - 1, h + 1))
    cut(base, groove)
    # board bosses: Ø6 neck on a drafted cone
    for b in L["bosses"]:
        x, y, sh = b["x"], b["y"], b["h"]
        boss = union(cyl((x, y, -0.5), (x, y, sh - b["neck_h"]), b["base_d"] / 2, b["top_d"] / 2),
                     cyl((x, y, sh - b["neck_h"]), (x, y, sh), b["top_d"] / 2))
        union(base, boss)
        if b["fixing"] == "insert":
            cut(base, cyl((x, y, sh - p["insert_len"] - 0.5), (x, y, sh + 0.1), p["insert_hole"] / 2))
        else:
            # nylon screw into a captive nylon nut, slid in from the cavity side (-x)
            cut(base, cyl((x, y, b["hole_floor_z"]), (x, y, sh + 0.1), p["screw_clear_d"] / 2))
            nz = b["nut_z"]
            cut(base, box(x - b["base_d"], y - (p["nylon_nut_af"] + 0.3) / 2, nz - (p["nylon_nut_t"] + 0.3) / 2,
                          x + (p["nylon_nut_af"] + 0.3) * 0.58, y + (p["nylon_nut_af"] + 0.3) / 2, nz + (p["nylon_nut_t"] + 0.3) / 2))
    # glands: spot face outside, then the hole
    for gl in L["glands"]:
        x, z = gl["x"], gl["z"]
        rs = gl["hex_af"] / 2 + 2
        y_sf = i["y1"] + wall - (h - (z - rs)) * tan - 0.2
        cut(base, cyl((x, y_sf, z), (x, i["y1"] + wall + 20, z), rs))
        cut(base, cyl((x, i["y1"] - 5, z), (x, i["y1"] + wall + 20, z), gl["hole"] / 2))
    # vent on the +x wall
    v = L["vent"]
    rs = v["body_d"] / 2 + 2
    x_sf = i["x1"] + wall - (h - (v["z"] - rs)) * tan - 0.2
    cut(base, cyl((x_sf, v["y"], v["z"]), (i["x1"] + wall + 20, v["y"], v["z"]), rs))
    cut(base, cyl((i["x1"] - 5, v["y"], v["z"]), (i["x1"] + wall + 5, v["y"], v["z"]), v["hole"] / 2))
    # ears: plates flush with the base's back face, grommet holes
    for e in L["ears"]:
        side = -1 if e["x"] < 0 else 1
        wall_x = (i["x0"] - wall + 2.0) if side < 0 else (i["x1"] + wall - 2.0)
        x0, x1 = sorted((wall_x, e["x"] + side * p["ear_pad"]))
        ear = rrect(x0, e["y"] - p["ear_pad"], x1, e["y"] + p["ear_pad"], 3.0, -fl, -fl + p["ear_t"])
        union(base, ear)
        # gussets: triangles from the ear's top face up the wall, stopping short of the grommet
        x_out = (i["x0"] - wall) if side < 0 else (i["x1"] + wall)
        x_end = e["x"] - side * (p["grommet_hole"] / 2 + 5.0)
        ze, gh, gt = -fl + p["ear_t"], p["gusset_h"], p["gusset_t"]
        for gy in (e["y"] - p["ear_pad"] + gt / 2, e["y"] + p["ear_pad"] - gt / 2):
            gx0, gx1 = sorted((wall_x, x_end))
            gus = box(gx0, gy - gt / 2, ze - 0.01, gx1, gy + gt / 2, ze + gh)
            ax, az, bx, bz = x_out, ze + gh, x_end, ze
            dx, dz = bx - ax, bz - az
            n = (dz, -dx) if (dz * (x_out - ax) + (-dx) * (ze - az)) < 0 else (-dz, dx)
            ln = math.hypot(*n)
            n = (n[0] / ln, 0.0, n[1] / ln)
            c = (ax + n[0] * BIG / 2, gy, az + n[2] * BIG / 2)
            cut(gus, obox(c[0], c[1], c[2], n, (0, 1, 0), BIG, BIG, BIG))
            union(base, gus)
        cut(base, cyl((e["x"], e["y"], -fl - 1), (e["x"], e["y"], -fl + p["ear_t"] + 1), p["grommet_hole"] / 2))
    return base


def build_lid(L):
    p = L["params"]
    i = L["interior"]
    h = i["h"]
    f = L["flange"]
    lid = rrect(f["x0"], f["y0"], f["x1"], f["y1"], 3.0, h, h + p["lid_t"])
    tan = math.tan(math.radians(p["draft"]))
    c = p["skirt_clear"] + p["skirt_h"] * tan
    sx0, sy0, sx1, sy1 = i["x0"] + c, i["y0"] + c, i["x1"] - c, i["y1"] - c
    t = p["skirt_t"]
    skirt = box(sx0, sy0, h - p["skirt_h"], sx1, sy1, h + 0.01)
    cut(skirt, box(sx0 + t, sy0 + t, h - p["skirt_h"] - 1, sx1 - t, sy1 - t, h + 1))
    union(lid, skirt)
    for r in L["lid"]["ribs"]:
        union(lid, box(max(r["x0"], sx0 + t - 0.01), max(r["y0"], sy0 + t - 0.01), h - r["h"],
                       min(r["x1"], sx1 - t + 0.01), min(r["y1"], sy1 - t + 0.01), h + 0.01))
    for s in L["screws"]:
        cut(lid, cyl((s["x"], s["y"], h - 1), (s["x"], s["y"], h + p["lid_t"] + 1), p["screw_clear_d"] / 2))
    return lid


def build_gasket(L):
    p = L["params"]
    h = L["interior"]["h"]
    g = L["groove"]
    cw = p["cord"] / 2
    ring = rrect(g["x0"] - cw, g["y0"] - cw, g["x1"] + cw, g["y1"] + cw, g["r"] + cw, h - g["d"], h)  # compressed
    cut(ring, rrect(g["x0"] + cw, g["y0"] + cw, g["x1"] - cw, g["y1"] - cw, g["r"] - cw, h - g["d"] - 1, h + 1))
    return ring


def build_hardware(L):
    """Metal parts (and the nylon H2 screw/nut), as plain solids: name -> body."""
    p = L["params"]
    i = L["interior"]
    h = i["h"]
    out = {}
    top = h + p["lid_t"]
    for k, s in enumerate(L["screws"]):
        x, y = s["x"], s["y"]
        if s.get("material") == "nylon":
            ln = p["nylon_lid_screw_len"]
            out[f"NYLON_lid_screw_{k + 1}"] = union(cyl((x, y, top - ln), (x, y, top), p["screw_d"] / 2),
                                                    cyl((x, y, top), (x, y, top + 2.0), 5.5 / 2))
            zb = h - p["insert_boss_depth"]
            out[f"NYLON_lid_nut_{k + 1}"] = hexprism(x, y, zb + p["nylon_nut_t"] / 2 + 0.1, "z", p["nylon_nut_af"], p["nylon_nut_t"])
        else:
            out[f"lid_screw_{k + 1}"] = union(cyl((x, y, top - 8), (x, y, top), p["screw_d"] / 2),
                                              cyl((x, y, top), (x, y, top + 2.0), 5.5 / 2))
            out[f"lid_insert_{k + 1}"] = cyl((x, y, h - p["insert_len"]), (x, y, h), p["insert_od"] / 2)
    sb = p["standoff"] + 1.6
    for b in L["bosses"]:
        x, y = b["x"], b["y"]
        screw = union(cyl((x, y, sb - b["screw_len"]), (x, y, sb), p["screw_d"] / 2), cyl((x, y, sb), (x, y, sb + 2.0), 5.5 / 2))
        if b["fixing"] == "insert":
            out[f"board_screw_{b['ref']}"] = screw
            out[f"board_insert_{b['ref']}"] = cyl((x, y, p["standoff"] - p["insert_len"]), (x, y, p["standoff"]), p["insert_od"] / 2)
        else:
            out[f"NYLON_board_screw_{b['ref']}"] = screw
            out[f"NYLON_nut_{b['ref']}"] = hexprism(x, y, b["nut_z"], "z", p["nylon_nut_af"], p["nylon_nut_t"])
    for k, e in enumerate(L["ears"]):
        out[f"ear_sleeve_{k + 1}"] = cyl((e["x"], e["y"], -p["floor"] - 1), (e["x"], e["y"], -p["floor"] + p["ear_t"] + 1), 3.5)
    return out


def build_glands(L):
    """Nylon glands and the vent as envelopes: name -> body."""
    p = L["params"]
    i = L["interior"]
    h, wall = i["h"], p["wall"]
    tan = math.tan(math.radians(p["draft"]))
    out = {}
    for g in L["glands"]:
        x, z = g["x"], g["z"]
        y_in = i["y1"] - (h - z) * tan
        y_sf = i["y1"] + wall - (h - (z - g["hex_af"] / 2 - 2)) * tan - 0.2
        body = union(cyl((x, y_in - g["nut_t"] - 2, z), (x, y_sf + 20, z), g["size"] / 2 - 0.01),
                     hexprism(x, y_in - g["nut_t"] / 2, z, "y", g["nut_af"], g["nut_t"]),
                     hexprism(x, y_sf + 4, z, "y", g["hex_af"], 8),
                     cyl((x, y_sf + 8, z), (x, y_sf + 20, z), g["hex_af"] * 0.95 / 2))
        out[f"gland_{g['name']}_M{g['size']}"] = body
    v = L["vent"]
    x_in = i["x1"] - (h - v["z"]) * tan  # inner wall face at the vent's height
    out["vent"] = union(cyl((x_in - 6, v["y"], v["z"]), (i["x1"] + wall + 10, v["y"], v["z"]), v["hole"] / 2 - 0.01),
                        cyl((x_in - 5, v["y"], v["z"]), (x_in, v["y"], v["z"]), v["body_d"] / 2),  # inside nut
                        cyl((i["x1"] + wall, v["y"], v["z"]), (i["x1"] + wall + 10, v["y"], v["z"]), v["body_d"] / 2))
    return out


# ---------- Fusion document ----------
def new_component(root, name):
    occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
    occ.component.name = name
    return occ


def add_bodies(occ, bodies, appearance=None):
    for name, b in bodies.items():
        rb = occ.component.bRepBodies.add(b)
        rb.name = name
    return occ


DOC_NAME = "ESP32MCCAN Housing"


def main(layout_path):
    global TBM
    app = adsk.core.Application.get()
    TBM = adsk.fusion.TemporaryBRepManager.get()
    with open(layout_path, encoding="utf8") as fh:
        L = json.load(fh)
    doc = app.activeDocument
    if doc is None or not doc.name.startswith(DOC_NAME):
        doc = app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
        doc.name = DOC_NAME
    design = adsk.fusion.Design.cast(app.activeProduct)
    for o in list(design.rootComponent.occurrences):  # regenerate: clear the previous build
        o.deleteMe()
    design.designType = adsk.fusion.DesignTypes.DirectDesignType
    root = design.rootComponent

    occs = {
        "Base": add_bodies(new_component(root, "Base"), {"base": build_base(L)}),
        "Lid": add_bodies(new_component(root, "Lid"), {"lid": build_lid(L)}),
        "Gasket": add_bodies(new_component(root, "Gasket"), {"gasket_cord_2mm": build_gasket(L)}),
        "Hardware": add_bodies(new_component(root, "Hardware"), build_hardware(L)),
        "Glands": add_bodies(new_component(root, "Glands"), build_glands(L)),
    }
    lines = []
    for n, o in occs.items():
        vols = [b.volume for b in o.component.bRepBodies]  # cm^3
        lines.append(f"{n}: {len(vols)} bodies, {sum(vols):.1f} cm3")
    print("built: " + "; ".join(lines))
    return design, occs, L


# ---------- interference and clearance check ----------
HOUSING = ("Base", "Lid", "Gasket", "Hardware", "Glands")


def place_board(design, step_path, L):
    """Import the board STEP as component 'Board', moved so its top-left corner sits at (0, 0, standoff)."""
    app = adsk.core.Application.get()
    root = design.rootComponent
    occ = new_component(root, "Board")
    opts = app.importManager.createSTEPImportOptions(step_path)
    app.importManager.importToTarget(opts, occ.component)
    bodies = all_bodies(occ)
    pcb = max(bodies, key=lambda b: (b.boundingBox.maxPoint.x - b.boundingBox.minPoint.x) *
              (b.boundingBox.maxPoint.y - b.boundingBox.minPoint.y))
    bb = pcb.boundingBox
    m = adsk.core.Matrix3D.create()
    m.translation = adsk.core.Vector3D.create(-bb.minPoint.x, -bb.maxPoint.y, L["params"]["standoff"] / 10.0 - bb.minPoint.z)
    occ.transform = m
    w = (bb.maxPoint.x - bb.minPoint.x) * 10
    hh = (bb.maxPoint.y - bb.minPoint.y) * 10
    return occ, (round(w, 2), round(hh, 2))


def place_envelopes(design, board, L):
    """A block (courtyard x height) for every part whose height came from the fallback table."""
    occ = new_component(design.rootComponent, "Envelopes")
    zb = L["params"]["standoff"] + 1.6
    for p in board["parts"]:
        if p["height_src"] == "model" or p["ref"].startswith("TP") or p["ref"] == "NT1":
            continue
        x0, y0, x1, y1 = p["bbox"]
        occ.component.bRepBodies.add(box(x0, y0, zb, x1, y1, zb + p["height"])).name = "env_" + p["ref"]
    return occ


def all_bodies(occ):
    out = list(occ.bRepBodies)
    for child in occ.childOccurrences:
        out += all_bodies(child)
    return out


def check_interference(design, occs, L, board, step_path):
    app = adsk.core.Application.get()
    bocc, size = place_board(design, step_path, L)
    eocc = place_envelopes(design, board, L)
    others = all_bodies(bocc) + all_bodies(eocc)
    housing = []
    for n in HOUSING:
        housing += all_bodies(occs[n])
    report = [f"board STEP placed: {size[0]} x {size[1]} mm, {len(all_bodies(bocc))} bodies; "
              f"{len(all_bodies(eocc))} envelope blocks"]

    coll = adsk.core.ObjectCollection.create()
    for b in housing + others:
        coll.add(b)
    inp = design.createInterferenceInput(coll)
    inp.areCoincidentFacesIncluded = False
    res = design.analyzeInterference(inp)
    # Result entities carry different entity tokens from the inputs, so classify by owning component.
    def is_housing(body):
        return body.parentComponent.name in HOUSING

    hits = []
    for r in res:
        one, two = r.entityOne, r.entityTwo
        if is_housing(one) != is_housing(two):
            hits.append(f"{one.parentComponent.name}/{one.name} x {two.parentComponent.name}/{two.name} "
                        f"({r.interferenceBody.volume * 1000:.2f} mm3)")
    report.append(f"interference: {len(hits)}")
    report += ["  " + h for h in hits]

    mm = app.measureManager

    def min_dist(group_a, group_b):
        best = (1e9, None, None)
        for a in group_a:
            for b in group_b:
                d = mm.measureMinimumDistance(a, b).value * 10
                if d < best[0]:
                    best = (d, a.name, b.name)
        return best

    d, a, b = min_dist(all_bodies(occs["Lid"]), others)
    report.append(f"lid to nearest part: {d:.2f} mm ({b})")
    d, a, b = min_dist(all_bodies(occs["Glands"]), others)
    report.append(f"glands/vent to nearest part: {d:.2f} mm ({a} / {b})")
    d, a, b = min_dist(all_bodies(occs["Base"]), others)
    report.append(f"base to nearest part: {d:.2f} mm ({b})")

    zx0, zy0, zx1, zy1 = L["antenna_zone"]
    inside = []
    for body in all_bodies(occs["Hardware"]):
        if body.name.startswith("NYLON"):
            continue
        bb = body.boundingBox
        x0, x1 = bb.minPoint.x * 10, bb.maxPoint.x * 10
        y0, y1 = -bb.maxPoint.y * 10, -bb.minPoint.y * 10
        if x0 < zx1 and zx0 < x1 and y0 < zy1 and zy0 < y1:
            inside.append(body.name)
    report.append(f"metal in antenna zone: {len(inside)} bodies {inside}")
    print("\n".join(report))
    return hits, inside


def export_all(design, occs, out_dir):
    """STEP + STL per printed part, the assembly STEP (with the board) and the Fusion archive."""
    em = design.exportManager
    os.makedirs(out_dir, exist_ok=True)
    written = []
    for name, stem in (("Base", "housing-base"), ("Lid", "housing-lid")):
        comp = occs[name].component
        f = os.path.join(out_dir, stem + ".step")
        em.execute(em.createSTEPExportOptions(f, comp))
        written.append(f)
        f = os.path.join(out_dir, stem + ".stl")
        o = em.createSTLExportOptions(comp.bRepBodies.item(0), f)
        o.meshRefinement = adsk.fusion.MeshRefinementSettings.MeshRefinementHigh
        em.execute(o)
        written.append(f)
    f = os.path.join(out_dir, "housing-assembly.step")
    em.execute(em.createSTEPExportOptions(f, design.rootComponent))
    written.append(f)
    f = os.path.join(out_dir, "esp32mccan-housing.f3d")
    em.execute(em.createFusionArchiveExportOptions(f, design.rootComponent))
    written.append(f)
    print("exported: " + ", ".join(f"{os.path.basename(w)} {os.path.getsize(w) // 1024} kB" for w in written))
    return written


def build_and_check(here):
    """Build from layout.json, then check against the board STEP. Returns (hits, metal_in_zone)."""
    design, occs, L = main(os.path.join(here, "layout.json"))
    with open(os.path.join(here, "board.json"), encoding="utf8") as fh:
        board = json.load(fh)
    hits, inside = check_interference(design, occs, L, board, os.path.join(here, "ref", "mccan-board.step"))
    if hits or inside:
        raise RuntimeError(f"housing check failed: {len(hits)} interference(s), {len(inside)} metal body(ies) in the antenna zone")
    export_all(design, occs, os.path.join(here, "export"))
    return hits, inside


def run(_context):
    build_and_check(os.path.dirname(os.path.abspath(__file__)))
