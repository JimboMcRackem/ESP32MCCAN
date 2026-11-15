# -*- coding: utf-8 -*-
"""Tests for the programmer's JLCPCB package (plan Task 4).

    python hardware/programmer/scripts/gen_fab_prog.py      (build the package first)
    python hardware/programmer/scripts/test_fab_prog.py

Each test grades the generated package with gen_fab_prog.check() and then grades a copy,
broken one way in a temp directory, to show check() catches that break.
"""
import csv
import io
import os
import re
import shutil
import sys
import tempfile
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gen_fab_prog as G  # noqa: E402
import parts  # noqa: E402


def broken(edit):
    """check() over a copy of the package (and board) with `edit(out_dir, pcb_path)` applied."""
    tmp = tempfile.mkdtemp(prefix="fabprog-")
    try:
        out = os.path.join(tmp, "jlcpcb")
        shutil.copytree(G.OUT, out)
        pcb = os.path.join(tmp, "prog.kicad_pcb")
        shutil.copy(G.PCB, pcb)
        edit(out, pcb)
        return G.check(out, pcb)
    finally:
        shutil.rmtree(tmp)


def rows(path):
    with io.open(path, encoding="utf-8", newline="") as f:
        return list(csv.reader(f))


def rewrite(path, rs):
    with io.open(path, "w", encoding="utf-8", newline="") as f:
        csv.writer(f, lineterminator="\n").writerows(rs)


def test_package_passes():
    assert G.check() == [], G.check()


def test_bom_covers_every_part():
    rs = rows(os.path.join(G.OUT, "bom.csv"))
    assert rs[0] == ["Comment", "Designator", "Footprint", "LCSC"]
    seen = {}
    for r in rs[1:]:
        for ref in r[1].split(","):
            seen[ref] = seen.get(ref, 0) + 1
            assert parts.PARTS[ref]["lcsc"] == r[3], (ref, r[3])
    assert seen == {ref: 1 for ref in parts.PARTS}, seen

    def drop_c9(out, _pcb):
        p = os.path.join(out, "bom.csv")
        rewrite(p, [[c, d.replace(",C9", ""), f, l] for c, d, f, l in rows(p)])
    assert any("C9" in f for f in broken(drop_c9))

    def wrong_lcsc(out, _pcb):
        p = os.path.join(out, "bom.csv")
        rewrite(p, [[c, d, f, "C1" if "U1" in d.split(",") else l] for c, d, f, l in rows(p)])
    assert any("U1" in f for f in broken(wrong_lcsc))


def test_cpl_matches_board():
    rs = rows(os.path.join(G.OUT, "cpl.csv"))
    assert rs[0] == ["Designator", "Mid X", "Mid Y", "Layer", "Rotation"]
    assert len(rs) - 1 == len(parts.PARTS)
    assert all(r[3].lower() == "top" for r in rs[1:])
    cpl = {r[0]: (float(r[1][:-2]), float(r[2][:-2])) for r in rs[1:]}
    for ref in ("J1", "J2"):
        cx, cy = G.pad_centre_board(ref, G.PCB)
        # the CPL is y-up: KiCad's position file negates board y
        assert abs(cpl[ref][0] - cx) < 1e-3 and abs(cpl[ref][1] + cy) < 1e-3, (ref, cpl[ref])

    def move_j2(out, _pcb):
        p = os.path.join(out, "cpl.csv")
        rewrite(p, [[d, ("%.4fmm" % (float(x[:-2]) + 1.27)) if d == "J2" else x, y, l, r]
                    for d, x, y, l, r in rows(p)])
    assert any("J2" in f for f in broken(move_j2))

    def bottom(out, _pcb):
        p = os.path.join(out, "cpl.csv")
        rewrite(p, [[d, x, y, "Bottom" if d == "R1" else l, r] for d, x, y, l, r in rows(p)])
    assert any("R1" in f for f in broken(bottom))


def test_rotation_review_lists_polarised():
    rev = io.open(os.path.join(G.OUT, "rotation-review.txt"), encoding="utf-8").read()
    assert "EVERY row" in rev and "preview" in rev
    body = rev.split("\n\n", 1)[1]
    for ref in ("U1", "U2", "U3", "U4", "U5", "D1", "D2", "D3", "J1", "J2"):
        m = re.search(r"^%s\s.*\s(\w+)\s*$" % ref, body, re.M)
        assert m and m.group(1) in ("recalled", "unverified"), (ref, m and m.group(0))

    def drop_d2(out, _pcb):
        p = os.path.join(out, "rotation-review.txt")
        t = io.open(p, encoding="utf-8").read()
        io.open(p, "w", encoding="utf-8", newline="\n").write(
            "\n".join(l for l in t.split("\n") if not l.startswith("D2 ")))
    assert any("D2" in f for f in broken(drop_d2))


def test_stamp_matches_board():
    stamp = io.open(os.path.join(G.OUT, "board.sha256"), encoding="utf-8").read().strip()
    assert stamp == G.board_hash(G.PCB)

    def touch(_out, pcb):
        with open(pcb, "ab") as f:
            f.write(b" ")
    assert any("board" in f for f in broken(touch))


def test_gerbers_complete():
    names = zipfile.ZipFile(os.path.join(G.OUT, "gerbers.zip")).namelist()
    for ext in (".gtl", ".gbl", ".gts", ".gbs", ".gtp", ".gbp", ".gto", ".gbo", ".gm1"):
        assert any(n.endswith(ext) for n in names), (ext, names)
    assert any(n.endswith("-PTH.drl") for n in names), names
    assert any(n.endswith("-NPTH.drl") for n in names), names

    def drop_npth(out, _pcb):
        p = os.path.join(out, "gerbers.zip")
        old = zipfile.ZipFile(p)
        keep = [(n, old.read(n)) for n in old.namelist() if not n.endswith("-NPTH.drl")]
        old.close()
        with zipfile.ZipFile(p, "w") as z:
            for n, b in keep:
                z.writestr(n, b)
    assert any("NPTH" in f for f in broken(drop_npth))


def main():
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print("PASS", name)
            except Exception as e:  # noqa: BLE001
                fails += 1
                print("FAIL", name, repr(e)[:400])
    print("test_fab_prog: %s" % ("PASS" if not fails else "FAIL (%d)" % fails))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
