# -*- coding: utf-8 -*-
"""Canonicalise a generated KiCad sheet into the form the GUI writes.

Why this exists
---------------
`power_input.kicad_sch` had been opened and saved in KiCad, and the committed sheet
therefore differed from its generator's output by 258 lines.  Every one of those lines
turned out to be cosmetic:

    (show_name no)         x110    = 5 properties x 22 symbols
    (do_not_autoplace no)  x110
    (body_style 1)         x22
    (in_pos_files yes)     x22
    minus a sheet_instances / embedded_fonts block a CHILD sheet does not carry

plus two orderings the GUI imposes and a hand-written generator has no reason to guess:

    * top-level elements grouped by TYPE, in the order below
    * each group sorted by UUID

Sorting by UUID looks arbitrary and is: the UUIDs are content-derived and stable, so the
order is deterministic, just not meaningful to a human.  It matters only because without
it a generator can never reproduce a GUI-saved sheet, which makes byte-comparison useless
as a fidelity check.

Run a generator's output through `canonicalise()` and the generator and the GUI agree.
"""
import re

# Observed in a KiCad 10.0.2-saved sheet.  `no_connect` and `bus` are placed by the
# format schema rather than by observation -- no GUI-saved sheet on this project has
# had one yet, so if a future sheet disagrees, trust the sheet and fix this list.
TYPE_ORDER = [
    "text_box", "text", "no_connect", "junction", "bus_entry", "wire", "bus",
    "label", "global_label", "hierarchical_label", "netclass_flag", "symbol", "sheet",
    # root-sheet trailers, always last
    "sheet_instances", "embedded_fonts",
]


def _split_top_level(body):
    """Yield (type, text) for each top-level `\\t(kind ...)` block in `body`."""
    out, i, n = [], 0, len(body)
    while i < n:
        j = body.find("\n\t(", i)
        if j < 0:
            break
        start = j + 1
        m = re.match(r"\t\((\w+)", body[start:])
        if not m:
            i = start + 1
            continue
        kind = m.group(1)
        depth, k = 0, body.index("(", start)
        while True:
            c = body[k]
            if c == '"':
                k += 1
                while body[k] != '"' or body[k - 1] == "\\":
                    k += 1
            elif c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
                if depth == 0:
                    break
            k += 1
        out.append((kind, body[start:k + 1]))
        i = k + 1
    return out


def canonicalise(text):
    """Reorder a sheet's top-level elements the way KiCad's GUI writes them."""
    anchor = "\t(lib_symbols"
    a = text.index(anchor)
    depth, j = 0, text.index("(", a)
    while True:
        c = text[j]
        if c == '"':
            j += 1
            while text[j] != '"' or text[j - 1] == "\\":
                j += 1
        elif c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                break
        j += 1
    head, body = text[:j + 1], text[j + 1:]

    tail = ")\n" if body.rstrip().endswith(")") else ""
    blocks = _split_top_level(body)

    groups = {}
    for kind, blk in blocks:
        groups.setdefault(kind, []).append(blk)

    unknown = [k for k in groups if k not in TYPE_ORDER]
    assert not unknown, "unknown top-level element(s), extend TYPE_ORDER: %s" % unknown

    def uuid_of(blk):
        m = re.search(r'\(uuid "([0-9a-f-]+)"\)', blk)
        return m.group(1) if m else ""

    out = [head]
    for kind in TYPE_ORDER:
        for blk in sorted(groups.get(kind, []), key=uuid_of):
            out.append("\n" + blk)
    return "".join(out) + "\n" + tail
