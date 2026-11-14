# Schematic generators

These author the KiCad sheets as text. They exist because this project was built without an
interactive KiCad session, and because regenerating from a script is reviewable in a way that
hand-edited s-expressions are not.

| Script | Produces |
|---|---|
| `symlib.py` | `../symbols/mccan_parts.kicad_sym` — LM51571-Q1 pin types, plus the DML3017LDC, ADG706, NX5020UNBKS (2-unit) and BTS7008_2EPA symbols |
| `gen_power_input.py` + `layout_power_input.py` + `notes_power_input.py` + `power_input_libsyms.txt` | `../sheets/power_input.kicad_sch` |
| `gen_rails.py` + `notes.py` | `../sheets/rails.kicad_sch` |
| `gen_mcu_can.py` | `../sheets/mcu_can.kicad_sch` |
| `gen_outputs.py` | `../sheets/outputs.kicad_sch` |
| `gen_root.py` | `../mccan.kicad_sch` — sheet boxes, their pins, and the root-level labels that join them |
| `kicanon.py` | shared: canonicalises every generator's output into the form KiCad's GUI writes |

Run from this directory, `symlib.py` first. **All six are idempotent** — running any of them
twice in a row leaves the file byte-identical.

## You CAN open these in KiCad. That is the whole point of `kicanon.py`.

Editing a sheet in the GUI and saving it rewrites the file in KiCad's canonical form. Before
2026-09-15 the generators did not produce that form, so the moment a sheet was saved from the
GUI its generator could never reproduce it again. `power_input` had already drifted this way:
its committed sheet differed from its generator's output by **258 lines**, every one cosmetic.

```
(show_name no)         x110    = 5 properties x 22 symbols
(do_not_autoplace no)  x110
(body_style 1)         x22
(in_pos_files yes)     x22
minus a sheet_instances / embedded_fonts block a CHILD sheet does not carry
```

…plus two orderings the GUI imposes: top-level elements grouped by type, and each group sorted
by UUID. Sorting by UUID looks arbitrary and is — but the UUIDs here are content-derived and
stable, so the order is deterministic.

Every generator now pipes its output through `kicanon.canonicalise()`, so **the generator and
the GUI agree**. A GUI save is no longer destructive to the generator relationship.

The remaining rule still stands: **if you change a sheet in the GUI, port the change back into
its generator**, or the next run will overwrite you. The generators are the source of truth.

## Two rules the generators enforce for you

**Every coordinate must be an exact multiple of 1.27 mm.** Off-grid endpoints are an ERC error,
and worse, a pin that misses its wire by 0.6 mm looks connected on screen but is not.
`ongrid()` asserts on every placement, wire, junction, label and no-connect.

**Put a label at a wire's END, not in the middle of it.** A mid-wire label still joins the net,
so the netlist looks correct, but the far endpoint dangles.

## Verify by reading the netlist, not by trusting ERC

ERC passes plenty of circuits that are wired wrong. Export the netlist and read every net:

```
kicad-cli sch export netlist --format kicadsexpr -o output/netlist.net mccan.kicad_sch
```

Allow **180 s** — these runs can exceed a 2-minute timeout.

**Netlist equivalence is the real regression test.** When changing a generator, capture the
netlist before and after and diff the net-to-pin mapping. Byte-identity of the `.kicad_sch` is a
useful check when you expect no change at all, but netlist equivalence is what actually matters
and is the only sane test once layout starts moving symbols around.
