# -*- coding: utf-8 -*-
"""Tests for check_plane_mincut.py on synthetic boards with known answers.

  python scripts/test_check_plane_mincut.py      exit 1 on any failure

Models use check_power_paths.load()'s shapes:
  pads   (key, net, layers, rect)          tracks (net, layer, x0, y0, x1, y1, w)
  vias   (net, x, y, size, drill)          zones  (net, layers, poly, rule, nopour, ...)
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import check_plane_mincut as M  # noqa: E402

# The tool reads a cut at 0.92-1.0 x its true width (the 8-neighbour metric, normalised so it
# never reads wide), plus about one grid step of quantisation.
LO, HI = 0.90, 1.03


def rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def strip(layers=("F.Cu",), w=10.0, length=30.0, extra_vias=(), extra_zones=(), tracks=()):
    """A w x length pour of net P, terminal pads S (left end) and T (right end)."""
    return dict(
        pads=[("S.1", "P", list(layers), (0.0, 0.0, 1.0, w)),
              ("T.1", "P", list(layers), (length - 1.0, 0.0, length, w))],
        tracks=list(tracks),
        vias=list(extra_vias),
        zones=[("P", list(layers), rect(0.0, 0.0, length, w), False, False)] + list(extra_zones))


def close(got, want, step=M.STEP):
    return LO * want - step <= got <= HI * want + step


def test_straight_strip_reads_its_width():
    got, _ = M.min_cut(strip(), "P", ["S.1"], ["T.1"])
    assert close(got, 10.0), got


def test_two_layers_in_parallel_add():
    got, _ = M.min_cut(strip(layers=("F.Cu", "B.Cu")), "P", ["S.1"], ["T.1"])
    assert close(got, 20.0), got


def test_diagonal_via_wall_leaves_only_its_gap():
    # Foreign vias (size 0.6, clearance 0.3 -> 1.2 mm knock-outs) every 0.7 mm on a 45-degree
    # line from the bottom edge, stopping short of the top: the gap above the wall is the neck.
    # The straight-cut check reads this strip as 10 mm wide.
    vias = [("Q", 10.0 + 0.7 * k, 0.0 + 0.7 * k, 0.6, 0.3) for k in range(10)]
    # last via centre at (16.3, 6.3): knock-out to y = 6.9; gap to the edge ~ 3.1 mm along the
    # wall's direction, measured square to it (45 deg): (10 - 6.9) ... take the true neck as the
    # shortest segment from the last knock-out to the top edge: 10 - 6.9 = 3.1 mm.
    got, _ = M.min_cut(strip(extra_vias=vias), "P", ["S.1"], ["T.1"])
    assert close(got, 3.1), got


def test_full_wall_cuts_to_zero():
    vias = [("Q", 15.0, 0.4 + 0.7 * k, 0.6, 0.3) for k in range(15)]
    got, _ = M.min_cut(strip(extra_vias=vias), "P", ["S.1"], ["T.1"])
    assert got < 0.05, got


def test_same_net_via_joins_layers():
    # F.Cu carries S's half, B.Cu T's half; one same-net via in the overlap joins them.
    m = dict(pads=[("S.1", "P", ["F.Cu"], (0.0, 0.0, 1.0, 10.0)),
                   ("T.1", "P", ["B.Cu"], (29.0, 0.0, 30.0, 10.0))],
             tracks=[], vias=[("P", 15.0, 5.0, 0.6, 0.3)],
             zones=[("P", ["F.Cu"], rect(0.0, 0.0, 16.0, 10.0), False, False),
                    ("P", ["B.Cu"], rect(14.0, 0.0, 30.0, 10.0), False, False)])
    got, _ = M.min_cut(m, "P", ["S.1"], ["T.1"])
    # All the current crowds into the one via, so the neck is the copper ring round its 0.6 mm
    # pad: pi x 0.6 = 1.9 mm (the barrel itself is not cut; check_power_paths grades vias).
    assert 1.6 <= got <= 2.6, got
    m["vias"] = []
    got, _ = M.min_cut(m, "P", ["S.1"], ["T.1"])
    assert got < 0.05, got


def test_same_net_track_is_copper():
    # Pour stops short; a 1 mm track of the same net bridges to T.
    m = strip(w=10.0, length=30.0)
    m["zones"] = [("P", ["F.Cu"], rect(0.0, 0.0, 20.0, 10.0), False, False)]
    m["tracks"] = [("P", "F.Cu", 19.0, 5.0, 30.0, 5.0, 1.0)]
    got, _ = M.min_cut(m, "P", ["S.1"], ["T.1"])
    assert close(got, 1.0), got


def test_check_reports_a_necked_path():
    vias = [("Q", 10.0 + 0.7 * k, 0.0 + 0.7 * k, 0.6, 0.3) for k in range(10)]
    m = strip(extra_vias=vias)
    f, _log = M.check_model(m, [("strip", "P", ["S.1"], ["T.1"], 6.4)])
    assert f and "strip" in f[0], f
    f, _log = M.check_model(strip(), [("strip", "P", ["S.1"], ["T.1"], 6.4)])
    assert not f, f


def main():
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print("PASS", name)
            except Exception as e:   # noqa: BLE001 -- report every test
                fails += 1
                print("FAIL", name, repr(e))
    print("test_check_plane_mincut: %s" % ("PASS" if not fails else "FAIL (%d)" % fails))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
