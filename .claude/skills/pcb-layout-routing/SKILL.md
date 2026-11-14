---
name: pcb-layout-routing
description: Use when laying out, placing or routing a printed circuit board in KiCad - especially when the board is generated from scripts rather than drawn by hand, when an autorouter is involved, or when a board is congested, hard to read, or failing DRC in ways that keep coming back.
---

# PCB layout and routing

## The workflow

1. **Generate, never hand-edit.** The board file is an output. Every change goes into the
   scripts that produce it. A hand edit in pcbnew is lost on the next run, and worse, it is
   lost silently.
2. **Place, and measure the placement.** Courtyard fill per region, checked by a script.
   Density is the root cause behind most routing failure, most silkscreen failure, and most
   "the autorouter is bad" complaints.
3. **Hand-route what carries an electrical requirement**, before the router runs: current
   paths that must be poured, differential pairs, switching loops, Kelvin taps.
4. **Let the router do the rest**, then **grade its output against the board's own rules**
   before admitting a single segment.
5. **Gate everything**, on every build. A gate that runs sometimes is a comment.

## Start here

- Congested board, unroutable nets, silk with nowhere to go → `references/placement.md`
- Choosing or changing a layer stack → `references/stackup.md`
- Deciding what to route by hand → `references/routing.md`
- Using an autorouter → `references/router-traps.md`
- What to check and why DRC is not enough → `references/gates.md`

## The five things most worth knowing

- **A pour never shorts to a foreign net**, so DRC will never catch a ground-split error.
  If two nets must meet at exactly N places, a script has to count them.
- **An autorouter will go below the sizes you give it and exit 0.** Grade its output
  yourself, against the board's own minimums.
- **Loop area and Kelvin taps are placement problems**, not routing problems. There is no
  good route for a 35 mm compensation trace.
- **Measure, do not derive.** A plane's current capacity, a region's fill, a pair's length:
  compute them from the board. Arithmetic in a comment was true once.
- **Silkscreen that cannot be printed is a placement failure.** Shrinking it or moving it to
  the fab layer hides the failure and leaves a board nobody can work on.

## Provenance

Extracted from an 8-layer, 200x140 mm ESP32 controller board re-laid out in this repo
(`hardware/`). That board is the worked example throughout `references/`, cited by file and
line so the claims can be checked, not taken on faith. It is not a template to copy: the
board's own regions, nets and part numbers stay in `hardware/docs/`, and it was **not
fabricable** when this skill was written — 11 pads were still unconnected. Everything here is
about the method that got it that far, including the parts of the method that had not
finished the job yet.
