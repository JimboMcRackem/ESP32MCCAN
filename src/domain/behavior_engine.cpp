#include "domain/behavior_engine.h"

static bool flashIsOn(const Config& cfg, uint32_t nowMs) {
  const uint32_t period = cfg.blinkPeriodMs ? cfg.blinkPeriodMs : 340;
  return (nowMs % (2 * period)) < period;
}

// The on/off phase for one indicator side. Elapsed time is computed with
// unsigned subtraction, so it is correct across millis() rollover.
static bool indicatorPhase(bool bit, const Config& cfg, uint32_t nowMs,
                           IndTimer& t) {
  if (bit && !t.prev) t.sinceMs = nowMs;   // rising edge restarts the window
  t.prev = bit;
  if (!bit) return false;

  switch (cfg.flashSource) {
    case FlashSource::Follow:
      return true;
    case FlashSource::Generate:
      return flashIsOn(cfg, nowMs);
    case FlashSource::Auto:
    default:
      if ((uint32_t)(nowMs - t.sinceMs) >= kFlashFollowTimeoutMs)
        return flashIsOn(cfg, nowMs);
      return true;
  }
}

OutputIntent computeOutputs(const LogicalState& s, const Config& cfg,
                            uint32_t nowMs, EngineState& est) {
  OutputIntent o;
  const bool li = s.leftInd, ri = s.rightInd;
  const bool lp = indicatorPhase(li, cfg, nowMs, est.leftTimer);
  const bool rp = indicatorPhase(ri, cfg, nowMs, est.rightTimer);

  // Indicator/hazard beats brake beats DRL. An indicating corner shows ONLY
  // its indicator: the same-side DRL is off per ECE R48, and on the rear the
  // brake is off too, because the module ORs DRL and brake onto one light
  // engine -- leaving either asserted would light the corner through the dark
  // phase and destroy the flash contrast.
  //
  // Both the DRL drop and the brake drop key off the REQUEST (li / ri), never
  // off the phase. Keying them off the phase would blink them back on in the
  // indicator's dark half, which is exactly what R48 forbids.
  o.set(OUT_FL_IND, lp);
  o.set(OUT_RL_IND, lp);
  o.set(OUT_FR_IND, rp);
  o.set(OUT_RR_IND, rp);

  if (s.run) {
    const bool brakeOn = s.brake();
    o.set(OUT_FL_DRL, !li);
    o.set(OUT_RL_DRL, !li);
    o.set(OUT_FR_DRL, !ri);
    o.set(OUT_RR_DRL, !ri);
    o.set(OUT_RL_BRK, brakeOn && !li);
    o.set(OUT_RR_BRK, brakeOn && !ri);
  }

  // --- Spot latch state machine (flash long-press) ---
  // NOTE: on the Energica Experia, flash / high beam / low beam are mutually
  // exclusive positions of ONE switch, so s.lowBeam and s.flash are never both
  // true. The sequential auto-drop-then-latch below is safe under that
  // assumption. Porting to a bike with independent flash and low-beam signals?
  // Gate the latch with `&& !s.lowBeam` (or use else-if).
  if (s.lowBeam) est.spotLatched = false;              // auto-drop on low beam
  if (s.flash && !est.flashPrev) est.flashRisingMs = nowMs;
  if (s.flash && (uint32_t)(nowMs - est.flashRisingMs) >= cfg.spotHoldMs)
    est.spotLatched = true;
  est.flashPrev = s.flash;

  // Aux pods: on/off only. Oxford's 5 brightness stages are a mechanical dial
  // on a switch this board replaces, so there is no level to select.
  const bool aux = s.run && (s.highBeam || est.spotLatched);
  o.set(OUT_AUX_L, aux);
  o.set(OUT_AUX_R, aux);
  return o;
}
