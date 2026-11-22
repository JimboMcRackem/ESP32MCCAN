#!/bin/sh
# Export the populated board as STEP for the housing's interference check (read-only on the board).
# Run from the repo root:  sh hardware/enclosure/ref/make_ref.sh
# Parts whose 3D model does not resolve are stood in by envelope blocks in build_housing.py.
KICAD_CLI="${KICAD_CLI:-/c/Program Files/KiCad/10.0/bin/kicad-cli.exe}"
"$KICAD_CLI" pcb export step --subst-models --force \
  -o hardware/enclosure/ref/mccan-board.step hardware/mccan.kicad_pcb
