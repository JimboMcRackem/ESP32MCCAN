# Schematic generators

These author the KiCad sheets as text. They exist because this project was built
without an interactive KiCad session, and because regenerating from a script is
reviewable in a way that hand-edited s-expressions are not.

| Script | Produces |
|---|---|
| `symlib.py` | `../symbols/mccan_parts.kicad_sym` — LM51571-Q1 pin types, DML3017LDC symbol |
| `gen_rails.py` + `notes.py` | `../sheets/rails.kicad_sch` |
| `gen_root.py` | patches `../mccan.kicad_sch` with the rails sheet pins and the inter-sheet wires |

Run from this directory, `symlib.py` first. All three are idempotent.

**Do not hand-edit the generated sheets.** KiCad's GUI rewrites them in its own
canonical form on save, which is fine and expected — but if you then re-run a
generator it will overwrite that work. Edit the generator, or retire it.
