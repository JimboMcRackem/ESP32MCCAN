# Gates: what to check, and why DRC alone is not enough

A gate exists because someone lost hours to the thing it checks. That is the only good reason
to write one, and it is also the test for whether a proposed gate is worth the maintenance
cost: has this actually bitten someone, or does it just sound like good practice?

## What DRC does not catch, and needs a purpose-built gate

- **Ground-split counting.** A pour never shorts to a foreign net by construction — DRC has
  nothing to flag, because nothing is electrically wrong. If a design requires two nets that
  are supposed to be separate (e.g. an input-side ground and a system ground) to meet at
  *exactly* N places (a filter component, a single star point), nothing in standard DRC counts
  those meeting points for you. A script that walks the two nets' pads against the poured
  polygon(s) and counts intersections is the only thing that catches "meets in the wrong place"
  or "meets one too many times." (Worked example: `hardware/scripts/check_grounds.py`.)
- **Copper below the board's own declared minimums.** See `router-traps.md` — an autorouter
  can hand back geometry finer than what it was asked for and finer than the board's own
  `min_track_width` / `min_via_diameter` / annular-ring rules, and still exit clean, because it
  is grading against a different, more permissive floor internally. A dedicated check reads the
  board's *own* stored rules and fails anything under them, regardless of what the tool that
  produced the copper thought was fine. (Worked example: `hardware/scripts/check_geometry.py`.)
- **Tracks on plane layers.** A layer meant to be a solid, unbroken reference plane can still
  legally accept a routed track from a tool that doesn't know that layer's role — nothing about
  a track on an inner copper layer is illegal in general. A check that reads which layers are
  declared signal layers (not hard-coded, but read from the same source of truth the router
  and the plane-pour code both use) and fails any track found elsewhere catches a slot cut
  through a reference plane before it ships.
- **Zero-length or sub-grid segments.** Harmless-looking junk — a stub a hair too short to draw
  or to register as a real connection — that a diff-based freeze step (see below) would
  otherwise bake into a generated board forever. Grade against a real, small threshold (a
  fraction of the router's own grid step is a reasonable one) and refuse to freeze anything
  that has one.
- **Courtyard overlap, checked before routing, not after.** DRC checks this too, but if DRC
  only runs *after* a lengthy autorouter pass, a placement mistake that DRC would catch in a
  fraction of a second instead costs the full routing run before it's discovered. Read the
  same courtyard geometry the placer uses and check pairwise overlap directly from the
  placement data, before generating a board at all — it costs about a second and answers the
  question the expensive run would have answered twenty minutes later. (Worked example:
  `hardware/scripts/check_courtyards.py`, whose own docstring records a real instance of losing
  a full routing run to a courtyard overlap DRC would have caught in a second if it had run
  first.)
- **Plane current-carrying capacity.** See `stackup.md`. Not a DRC concept at all — it needs a
  rasterised measurement against a real engineering standard, run *last* in any chain that
  includes an autorouter, because router-placed vias can only make a plane's cross-section
  narrower, never wider, than the pre-routed board.
- **Region density / fill.** See `placement.md`. Also not a DRC concept — DRC checks clearance
  and connectivity, not whether a region has enough headroom left for the escapes it will need.
- **A zone that filled as two (or more) disconnected islands.** This is the sharpest trap in
  this whole file. A pinched pour — one that got squeezed down to nothing at some point along
  its outline by tight neighbouring geometry — can fill as two electrically separate islands
  of copper that are each, individually, perfectly legal: right net, right clearances, right
  connections to whatever pads sit inside each island. Standard DRC treats a split fill as an
  **unconnected item** (the zone is "unconnected" to itself across the gap), not a rule
  **violation** — and an exit-code gate keyed to violations alone (see below) will report a
  clean board while an entire plane is quietly cut in half. The signature to look for in a DRC
  report is an unconnected-item block whose anchors are *the same zone, twice, at the same
  point* — KiCad reporting a zone as unconnected to itself. A check that greps the report for
  exactly that self-paired signature (not just "a zone appears in an unconnected item," which
  also fires on an ordinary pad-to-zone routing miss and is a different, less alarming fault)
  is a few dozen lines and catches a fault that passed every other check on the
  worked-example board (`hardware/scripts/check_zone_islands.py`: "the board shipped through
  every check this repo had" until this one specific signature was added).

## Two traps about the gates themselves

- **A DRC-style tool's exit code can conflate "found violations" with "found anything to
  report at all."** A DRC run that counts unconnected pads/items as part of its exit-status
  logic will return a non-zero exit on a board that has zero rule *violations* but some
  accepted, tracked, non-zero count of unconnected items (a board mid-way through routing, for
  instance). Treat the process exit code as informational at best; the actual gate has to be
  the violation/unconnected count parsed out of the **report body**, compared against whatever
  count is currently accepted, never `$?` on its own. (Worked example:
  `hardware/README.md`, "Neither run's exit code is the pass/fail signal on its own — `kicad-cli`
  exits 5 whenever any unconnected pad exists.")
- **`$?` read after a pipeline is the last command's exit status, not the one you meant to
  check.** If a gate command's output is piped through anything — `| head`, `| grep`, `| tail`
  — before the exit code is inspected, `$?` (in a POSIX shell without explicit `PIPESTATUS`
  handling) reflects the *pipe's last stage*, not the tool that actually did the check. A
  gate written as `some_check | head -20; if [ $? -ne 0 ]` can report success on a genuine
  failure purely because `head` exited 0 after reading enough lines. Capture the tool's own
  exit status directly (run it unpiped and redirect to a file, or use your shell's pipeline
  status array) before branching on it.
- **A rule can be silently downgraded from error to warning**, and a gate that filters by
  severity will then report a clean board while real findings sit invisible in the discarded
  half. **Run the same DRC at both the strict severity level and the permissive one.** A CAD
  tool's stock project defaults commonly leave a large fraction of its total rule set at
  "warning" or "ignore," which an error-only gate discards entirely and silently. Compare the
  two runs' counts explicitly rather than assuming they'd agree; do not assume a rule's default
  severity reflects whether it matters on *this* board. (Worked example:
  `hardware/scripts/gen_netclasses.py`: an error-only DRC gate reported zero violations while
  the same board, checked at the permissive severity, reported 28 findings across two rule
  types that had never been touched away from their tool defaults.)
- **A gate that parses a report has to run strictly after the tool that writes the report, not
  beside it or before it**, and should refuse to trust a report that is missing or older than
  the board it is supposed to describe. A parsing gate that races the tool it depends on is
  worse than useless — it will pass on stale or absent data and look exactly like a real check.

## The framing that makes gates worth writing

A gate exists because someone lost real time to the thing it checks — and that means a new
gate is a sign a mistake actually happened, not a sign of thoroughness for its own sake. Two
rules about *writing* gates follow from that framing:

- **A gate that admits or rejects a piece of work should not be written by whoever produced
  that work.** Not because of dishonesty — because the author's own mental model of what could
  go wrong is exactly the blind spot the gate exists to cover. If you routed the board, have
  someone or something else write (or at minimum review) the checker that grades the route.
- **Ablation over argument, when a fix appears to work.** When a change fixes a problem, do not
  reason your way to which part of the change did the work — take the parts back out, one at a
  time, and watch what breaks. A fix credited to the wrong cause teaches the wrong lesson for
  next time and leaves the real cause of the original bug live and undetected.

## The failure no automated gate here catches: stale facts

Every check above operates on the board file or a tool's report — none of them read prose. A
measurement or a decision that gets superseded lives on in every comment, docstring and
document that restated it, and those do not get re-checked automatically by anything. This
needs a deliberate sweep, and it is worth treating as seriously as any automated gate because
it is exactly as capable of shipping a wrong board.

- **A sweep needs two passes: words, and numbers.** Grepping for the words that name a
  superseded decision (a feature name, a former dimension's label, an old layer count spelled
  out) finds the prose that talks *about* the decision. It does not find a copy of the decision
  that travels as a bare number with no identifying word nearby — a coordinate range, a
  distance, a layer index — because nothing about a bare number is greppable for what it
  represents. Run both passes. On the worked-example project, the numeric-only pass is what
  found a fabrication document quoting an obsolete keep-out location by coordinates, and an
  order specification still naming an old, smaller layer count nowhere near the words that a
  words-only sweep had already checked.
- **A ruling recorded once is not a ruling delivered everywhere.** The moment a decision
  reverses something already written down, immediately grep for every restatement of the old
  claim across the whole tree — not just the section or file that happens to be open for the
  task that triggered the reversal. A single reversed number on the worked-example project had
  to be tracked into several specifications, several hand-maintained documents and several
  source comments independently; each occurrence was found the same way, by asking "which
  other file quotes the number I just changed," never by stumbling on it while doing something
  else.
- **Sweep the source of truth first, and start at the top of the file.** Every other sweep
  points *outward*, from the module that actually decides a fact toward the documents that
  quote it. That habit has a blind spot: the deciding module's own summary — a module
  docstring, a header comment, a design note at the top of the file — is exactly as capable of
  going stale as anything downstream, and it is the one place nobody re-checks, because it is
  the thing every other check is checked *against*. On the worked-example project, the
  generator module's own top-of-file docstring had carried an old board dimension, stated in
  the present tense as current fact, since the day it stopped being true — and no sweep found
  it, because every sweep was pointed at "everything that quotes this file," not at the file
  itself. Read the summary at the top of the file you trust most, last, as part of the sweep,
  not as an exemption from it.
- **A line-number citation is a claim with a shelf life, even when it was correct when
  written.** If a review, a task brief, or any handoff document cites specific line numbers in
  a file that is still being actively edited (by a concurrent task, or simply not yet
  finalized), every citation drifts silently as lines are inserted or removed above it — right
  when written, wrong by the time it's read, with no error anywhere to signal the drift. The
  reader finds *something* at the cited line and has to guess whether the finding is stale or
  the citation is broken, and the two convenient resolutions are both wrong: treating the
  finding as already resolved, or editing the source to make the citation true again after the
  fact. When citing into a file someone else (or some other task) is actively editing, quote
  the actual text being referenced — text doesn't drift — and offer the line number only as a
  convenience, not as the identifier.
- **When a handoff prescribes a command and then states what it returns, actually run the
  command** rather than trusting the stated count or list. A command run with slightly wrong
  flags (a case-sensitive grep where the real data has mixed case, for instance) silently
  under-returns — it hands back a shorter result that still *looks* complete, with nothing
  to distinguish "this is genuinely everything" from "this missed some entries." A drifted line
  citation at least announces itself, because the reader finds the wrong text and knows
  something is off; an under-returning command does not announce anything. If a document gives
  you both a command and a description of its output, get the description *from actually
  running the command*, not by reading the document's own prose paraphrase of it — the two can
  silently disagree the moment either one is edited without the other.
- **A stale number embedded in an otherwise-live piece of reasoning is not a dead comment.**
  The tempting response on finding a wrong figure inside a paragraph of rationale is to delete
  the whole paragraph. Usually that overcorrects: the policy the paragraph argues for is often
  still correct and still the right call, and only the specific number measured against it has
  moved. The right repair is to correct the figure in place and say what it was re-measured
  against, not to remove the reasoning around it — deleting the reasoning costs the next reader
  the answer to "why is this like this," which is the entire reason a comment like that exists.
- **Check that an instruction still has something to point at, not just that its numbers are
  current.** A stale-fact sweep asks "is this figure still true." It's a different question to
  ask "does this instruction still refer to anything real" — a sentence can be entirely
  factually current and still be an instruction pointing at nothing, if whatever it used to
  reference was removed rather than changed. On the worked-example project, a fabrication note
  told the vendor "no copper in the marked region — see the comment layer," and every word of
  that sentence was true right up until the thing it was telling them to look at had quietly
  stopped being marked on that layer. Read documents meant for someone else to act on **as the
  person who has to act on them**, and ask what they would actually do next — not just whether
  every value in the sentence checks out.

None of this replaces the automated gates above. It is the category of failure they cannot see
at all, because it lives in prose rather than in the board file, and it needs the same
seriousness as a missing DRC check: something that actually bit a real project, worth building
a habit (a sweep, run at the point of every reversal) around rather than trusting memory.
