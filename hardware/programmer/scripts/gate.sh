#!/usr/bin/env bash
# Every gate for the programmer board, in run order (plan Task 5).
#
#   bash hardware/programmer/scripts/gate.sh
#
# One PASS/FAIL row per gate; exit 0 only if every gate passes.  Reports from ERC and DRC
# go to a temp directory, so running the gate does not touch tracked files.
cd "$(dirname "$0")/.." || exit 2
export PYTHONIOENCODING=utf-8
KICAD="${KICAD_CLI:-C:/Program Files/KiCad/10.0/bin/kicad-cli.exe}"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
ok=1

row() {  # row NAME command...   run quietly, print PASS/FAIL, keep the log on failure
    local name="$1"; shift
    if "$@" >"$TMP/$name.log" 2>&1; then
        printf 'PASS  %s\n' "$name"
    else
        printf 'FAIL  %s  (log follows)\n' "$name"; tail -15 "$TMP/$name.log" | sed 's/^/      /'
        ok=0
    fi
}

erc() {
    "$KICAD" sch export netlist --format kicadsexpr -o "$TMP/netlist.net" prog.kicad_sch &&
    # the committed netlist is what gen_pcb.py reads: it must be the schematic's, bar the stamp
    diff <(grep -v -E '^\s*\((source|date|tool) ' output/netlist.net | tr -d '\r') \
         <(grep -v -E '^\s*\((source|date|tool) ' "$TMP/netlist.net" | tr -d '\r') >/dev/null &&
    "$KICAD" sch erc --severity-all -o "$TMP/erc.rpt" prog.kicad_sch >/dev/null &&
    grep -q 'ERC messages: 0 ' "$TMP/erc.rpt"
}

drc() {
    "$KICAD" pcb drc --severity-all --schematic-parity --refill-zones \
        -o "$TMP/drc.rpt" prog.kicad_pcb >/dev/null
    grep -q '\*\* Found 0 DRC violations \*\*' "$TMP/drc.rpt" &&
    grep -q '\*\* Found 0 unconnected pads \*\*' "$TMP/drc.rpt" &&
    grep -q '\*\* Found 0 Footprint errors \*\*' "$TMP/drc.rpt"   # schematic parity
}

row test_parts          python scripts/test_parts.py
row test_netlist_prog   python scripts/test_netlist_prog.py
row test_board          python scripts/test_board.py
row test_fab_prog       python scripts/test_fab_prog.py
row erc                 erc
row check_netlist_prog  python scripts/check_netlist_prog.py
row drc                 drc
row check_board         python scripts/check_board.py
row fab_check           python scripts/gen_fab_prog.py --check
row stock               python scripts/check_stock_prog.py --boards 5

[ $ok = 1 ]
