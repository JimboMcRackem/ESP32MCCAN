# Schematic generators

These author the KiCad sheets as text. They exist because this project was built
without an interactive KiCad session, and because regenerating from a script is
reviewable in a way that hand-edited s-expressions are not.

| Script | Produces |
|---|---|
| `symlib.py` | `../symbols/mccan_parts.kicad_sym` — LM51571-Q1 pin types, DML3017LDC symbol |
| `gen_rails.py` + `notes.py` | `../sheets/rails.kicad_sch` |
| `gen_mcu_can.py` | `../sheets/mcu_can.kicad_sch` |
| `gen_root.py` | `../mccan.kicad_sch` — sheet boxes, their pins, and the root-level labels that join them |

Run from this directory, `symlib.py` first. All three are idempotent.

**Do not hand-edit the generated sheets.** KiCad's GUI rewrites them in its own
canonical form on save, which is fine and expected — but if you then re-run a
generator it will overwrite that work. Edit the generator, or retire it.

## Two rules the generators now enforce for you

**Every coordinate must be an exact multiple of 1.27 mm.** Off-grid endpoints are an ERC error, and
worse, a pin that misses its wire by 0.6 mm looks connected on screen but is not. `ongrid()` asserts
on every placement, wire, junction, label and no-connect.

**Put a label at a wire's END, not in the middle of it.** A mid-wire label still joins the net, so
the netlist looks correct, but the far endpoint dangles.

## Verify by reading the netlist, not by trusting ERC

ERC passes plenty of circuits that are wired wrong. Export the netlist and read every net:

```
kicad-cli sch export netlist --format kicadsexpr -o output/netlist.net mccan.kicad_sch
```

Allow 180 s — these runs can exceed a 2-minute timeout.
