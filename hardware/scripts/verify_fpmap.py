"""Check every footprint the project assigns.

Two failure modes this catches, both of which survive ERC and would reach fabrication:

1. **A footprint string that does not resolve.**  KiCad silently carries an unresolved
   footprint in the schematic; it only fails when the netlist is imported into the board,
   by which time the placement work is done.
2. **A pad-count / pin-count mismatch.**  The classic version is a symbol with an exposed
   pad as pin N against a footprint whose thermal pad is numbered differently, or a
   3-pin part given a 2-pin package.  The board imports, the part looks placed, and one
   connection does not exist.

Run:  python scripts/verify_fpmap.py
Exit: 0 if every assigned footprint resolves and matches, 1 otherwise.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
HW = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
import fpmap  # noqa: E402

STOCK = r"C:\Program Files\KiCad\10.0\share\kicad\footprints"
NETLIST = os.path.join(HW, "output", "netlist.net")


def fp_path(spec):
    lib, _, name = spec.partition(":")
    if lib == "mccan":
        return os.path.join(HW, "footprints", "mccan.pretty", name + ".kicad_mod")
    return os.path.join(STOCK, lib + ".pretty", name + ".kicad_mod")


def pad_numbers(path):
    """Distinct *numbered* pads.  Mechanical pads ("") and NC pads are excluded, the way
    KiCad's own netlist/board comparison treats them."""
    t = open(path, encoding="utf-8").read()
    # KiCad 6+ quotes the pad number; the legacy (module ...) format does not, and vendor
    # libraries such as SamacSys still ship legacy files.  Accept both.
    nums = set(re.findall(r'\(pad\s+"([^"]+)"', t))
    nums |= set(re.findall(r"\(pad\s+([^\s\"()]+)\s", t))
    return {n for n in nums if n and n.lower() not in ("nc", "")}


def main():
    t = open(NETLIST, encoding="utf-8").read()
    comps = re.findall(
        r'\(comp\s*\n\s*\(ref "([^"]+)"\)\s*\n\s*\(value "([^"]+)"\)(.*?)\n\t\t\)', t, re.S)
    pins = {}
    for blk in re.split(r"\n\t\t\(net\n", t)[1:]:
        for m in re.finditer(r'\(ref "([^"]+)"\)\s*\n\s*\(pin "([^"]+)"\)', blk):
            pins.setdefault(m.group(1), set()).add(m.group(2))

    bad, blocked, ok = [], [], 0
    for ref, val, body in comps:
        m = re.search(r'\(footprint "([^"]+)"\)', body)
        spec = m.group(1) if m else ""
        if not spec:
            blocked.append((ref, val, fpmap.BLOCKED.get(ref, "NO REASON RECORDED")))
            continue
        path = fp_path(spec)
        if not os.path.isfile(path):
            bad.append((ref, val, spec, "footprint does not exist"))
            continue
        pads, used = pad_numbers(path), pins.get(ref, set())
        missing = used - pads
        if missing:
            bad.append((ref, val, spec,
                        "symbol uses pin(s) %s with no matching pad (footprint has %s)"
                        % (",".join(sorted(missing)), ",".join(sorted(pads)))))
            continue
        ok += 1

    print("assigned and verified : %d" % ok)
    print("blocked (no footprint): %d" % len(blocked))
    print("FAILURES              : %d" % len(bad))
    if blocked:
        print("\n-- blocked, with the reason recorded in fpmap.BLOCKED --")
        for ref, val, why in sorted(blocked):
            print("   %-4s %-32s %s" % (ref, val, why))
    if bad:
        print("\n-- FAILURES --")
        for ref, val, spec, why in sorted(bad):
            print("   %-4s %-20s %s\n        %s" % (ref, val, spec, why))
        return 1
    # a blocked part with no recorded reason is itself a failure
    silent = [b for b in blocked if b[2] == "NO REASON RECORDED"]
    if silent:
        print("\n-- FAILURE: unassigned with no reason in fpmap.BLOCKED --")
        for ref, val, _ in silent:
            print("   %-4s %s" % (ref, val))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
