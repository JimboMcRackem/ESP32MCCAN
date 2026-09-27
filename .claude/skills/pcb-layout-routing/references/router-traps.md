# Autorouter traps

This file is about the general shape of the traps a modern rip-up/reroute autorouter sets for
you, illustrated with one specific tool (KiCadRoutingTools) on one specific board. **Do not
reconstruct the specific flag rationale from memory or from this file's summary** — the
written authority for this project's exact flags is `hardware/docs/routing-tool.md`, and the
comments beside each flag in `hardware/scripts/route_external.py` say why that flag is passed,
kept current as the reasons changed across the project's history. Read those before touching
an equivalent flag on a different tool; generalise the *shape* of each trap from here, not the
specific numbers.

## The general rule underneath all of these

**A tool's own graders passing tells you nothing about whether it honoured your rules.** A
router with an internal "no violations found" check is checking against *its own*
understanding of the rules it was configured with — which is not necessarily the rules you
meant to give it, and is never a substitute for grading the output against the board's own
declared floors with a checker the router had no part in writing. Every trap below is a
version of this: a flag that looks like a floor, isn't; a flag that looks like protection,
composes with something else that removes it; a detector that looks specific, fires on the
wrong things.

## "Escalation" vs. "fab tier" — the floor isn't where it looks

A router facing a net it cannot close at the requested size will often be willing to retry it
at a smaller size to get it to close — and the flag that looks like it sets the floor for that
retry (something like "fab tier" or "quoted process") is frequently *not* the flag that holds
it. There is often a second, separately-named setting (an "escalation" level) whose default
lets a failing net retry all the way down to the fab's absolute minimum geometry, **below**
what the board itself declares as its floor. On the worked-example board this cost a full run:
the fab-tier flag was set to the correct tier, exited 0, and quietly handed back thousands of
tracks at roughly a third of the requested width — a size the tool's own DRC pass considered
perfectly legal, because it was checking against the wrong floor
(`hardware/docs/routing-tool.md` §6, first bullet). The fix is to find and set the escalation
control explicitly to "the board's own declared rules, no further," and then to grade the
result yourself against those same rules — never trust the tier setting alone.

## The fine-pitch-grid detector that thinks it found a BGA

A "BGA escape" feature in a router is often really "any fine-pitch grid of pads," not
specifically ball-grid-array detection. It can fire on a TSSOP or QFN with regular pin spacing,
classify it as a ball grid, and then run an aggressive under-pad rescue geometry (far finer
track/via/clearance than the board's normal rules) to force an escape that was never necessary
— the part had ordinary gull-wing or J-lead pins with normal clearance around them. If a board
has no BGA, LGA or CSP part on it at all, turn this feature off outright rather than trusting
it to correctly decide it isn't needed; a detector's false positive is a direct path to
sub-floor copper that a size-escalation check might not catch because it fires through a
different code path.

## "Keep existing copper" is narrower than it sounds, and composes with rip authority

A flag meaning "the input board's copper is read-only" is often really "disable this specific
late cleanup/orphan-stripping pass," which is a real and useful protection but not the same
guarantee as its name suggests. Two consequences to check for on any router: (1) a separate
late-stage cleanup pass may still sweep input copper it independently judges dead unless this
flag (or its real scope) is understood; and (2) a "protect this copper" flag does **not**
generally override a *separate* "you are allowed to rip up existing nets" authorization — a
net named on both lists is still rippable, because the two settings answer different
questions ("may this copper be cleaned up as dead" vs. "may this copper be torn out to make
room for something else"). If you need a piece of hand-routed copper to be truly untouchable,
find the tool's actual protection/lock mechanism (a per-net, exact-name, no-glob list is the
common shape) rather than trusting the first flag whose name sounds right. On the
worked-example project this was tested for real — a rip-authority run against 61 pre-existing
nets excluded from *routing* still needed the separate protection list to keep them from being
*ripped*, and net exclusion from routing alone was not sufficient
(`hardware/docs/routing-tool.md` §5.3, §6 "the two compose").

## Exclusion lists usually mean "don't route," not "don't touch"

A `--nets` (or equivalent) exclusion that keeps a net out of the routing queue is very often
scoped to exactly that — the routing queue — and says nothing about a router's own later
salvage or rip-up stages, which frequently build their *own* rip-eligibility list straight from
the board and are not automatically aware of what was excluded upstream. If a net must never
be touched by any stage of a run, find the mechanism that actually says that (again, usually a
named protection map, not a routing exclusion) and apply it directly, rather than assuming an
exclusion from routing implies exclusion from everything. The worked-example project lost an
entire hand-routed net this way on one run before the protection map was applied — the
exclusion kept the net out of the routing queue exactly as documented, and a later salvage
stage ripped it anyway (`hardware/docs/routing-tool.md` §6, "`--nets` exclusions say what may
not be ROUTED, not what may not be RIPPED").

## "No rippable blockers" means a pad, not a net, is in the way

When a router reports that it cannot close a net because there are no rippable blockers, the
obstruction is very often a **fixed pad**, not another net's movable copper — and no amount of
rip-up authority changes that, because there is nothing to rip. This message is a placement
diagnosis wearing a routing error's clothes: go look at why the geometry around that pad is
tight (see `placement.md`'s escape-channel arithmetic) rather than reaching for a routing flag.

## Room on the *input* board vs. room on the *routed* board mean different things

A stranded pad can show "no room" on a fully-routed board while a sweep of the bare,
pre-routed board finds plenty of legal via sites nearby. Both can be true at once, and they
point at opposite fixes. If room exists on the unrouted board but not on the routed one, the
problem is **congestion and ordering** — some other net got there first and used up the one
channel — and the fix is to make the starved net go earlier (a short hand-placed stub is often
enough to take it out of the routing competition entirely; it does not need to be routed all
the way home, just far enough to leave the contested area). If room is absent on *both* boards,
the problem is geometry, and only then does it call for a placement change. Diagnosing which
case you are in before acting matters, because a placement change aimed at a congestion problem
tends to close some nets while opening different ones elsewhere — a lateral move, not a fix.

## Don't reach for "rip everything" as a way out of a congested run

Granting a router broad authority to rip up and re-route already-placed nets in the hope that
a fresh ordering does better is rarely a net win on a board that is already tight in places:
freeing room for the nets that were stuck usually costs room somewhere else, and the run
becomes a reshuffle of which nets fail rather than a reduction in how many do. Prefer fixing
the actual channel or ordering problem (see the two points above) over expanding rip authority.

## A router's own connectivity/size checks are not this board's checks

Even a router with a bundled DRC/connectivity checker is checking against *its* model of your
rules, populated however its config import worked. Always re-grade the output with your own
checker, built directly from the same board file the design's real minimums live in (track
width, via size, annular ring, layer legality, minimum segment length). This is not
redundant with the router's own pass — see `gates.md`.

## Freezing a router's output makes it reproducible; re-running the router does not reproduce it

Once a routing run has produced an acceptable result, capture what it *added* as data your
generator can replay deterministically, rather than treating the router as a step that runs
fresh every time the board regenerates. A router with any randomised or history-dependent
heuristics (net ordering, rip-up history, timing-sensitive tie-breaks) is not guaranteed to
reproduce the same result on a re-run with identical inputs, and a "better" fresh run is not
even guaranteed to be strictly better — it can simply fail a *different* set of nets. On the
worked-example board, a full-board re-route under otherwise-identical settings failed a
different-sized and differently-composed set of nets than the run that had been frozen and
kept, and neither set was a subset of the other (`hardware/docs/routing-tool.md` §5.3 records
the same shape of result — re-running with more authority traded some newly-closed nets for
others newly opened, net movement "+10 against the number that gates" the board's own
acceptance test). Treat a good run as a result to freeze and diff against future regenerations,
not as a recipe to re-execute.

## Environment-specific: Git Bash mangles a leading `/`

If the shell driving any of this is Git Bash (MSYS) on Windows, any command-line argument that
*starts with `/`* is silently rewritten as a Windows path by MSYS's argument conversion before
the target program ever sees it — a net name like `/CANH` can arrive as something like
`C:/Program Files/Git/CANH`, matching nothing, with no error printed anywhere. If net names in
your design are `/`-prefixed (hierarchical KiCad net names commonly are), export
`MSYS_NO_PATHCONV=1` (or the MSYS2 equivalent `MSYS2_ARG_CONV_EXCL='*'`, depending on which
shell layer is doing the conversion) before running anything that takes such a name on the
command line, and verify the argument actually arrived intact — do not assume it did just
because the command didn't error. The same conversion affects plain output-path arguments too,
not just net names, if they start with `/`.
