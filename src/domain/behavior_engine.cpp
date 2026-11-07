#include "domain/behavior_engine.h"

static bool flashIsOn(const Config& cfg, uint32_t nowMs) {
  const uint32_t period = cfg.blinkPeriodMs ? cfg.blinkPeriodMs : 340;
  return (nowMs % (2 * period)) < period;
}

// The on/off phase for one indicator side. Elapsed time is computed with
// unsigned subtraction, so it is correct across millis() rollover.
// Generated phase measured from the anchor, so the first on-phase is full
// whenever the request starts. Unsigned subtraction keeps it rollover-safe.
static bool anchoredFlashIsOn(const Config& cfg, uint32_t nowMs, uint32_t anchorMs) {
  const uint32_t period = cfg.blinkPeriodMs ? cfg.blinkPeriodMs : 340;
  return ((uint32_t)(nowMs - anchorMs) % (2 * period)) < period;
}

static bool indicatorPhase(bool bit, const Config& cfg, uint32_t nowMs,
                           IndTimer& t, uint32_t anchorMs) {
  if (bit && !t.prev) t.sinceMs = nowMs;   // rising edge restarts the window
  t.prev = bit;
  if (!bit) return false;

  switch (cfg.flashSource) {
    case FlashSource::Follow:
      return true;
    case FlashSource::Generate:
      return anchoredFlashIsOn(cfg, nowMs, anchorMs);
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

  // A request starting from nothing anchors the generated phase. A side that
  // starts while the other is already flashing joins it, so hazards stay in
  // step even when the two bits arrive a tick apart.
  const bool stillFlashing = (est.leftTimer.prev && li) || (est.rightTimer.prev && ri);
  const bool starting = (li && !est.leftTimer.prev) || (ri && !est.rightTimer.prev);
  if (starting && !stillFlashing) est.flashAnchorMs = nowMs;

  const bool lp = indicatorPhase(li, cfg, nowMs, est.leftTimer, est.flashAnchorMs);
  const bool rp = indicatorPhase(ri, cfg, nowMs, est.rightTimer, est.flashAnchorMs);

  // Indicator/hazard beats brake beats DRL. An indicating corner shows ONLY
  // its indicator: the same-side DRL is off per ECE R48, and on the rear the
  // brake is off too. The rear rule predates the EL360's separate red and amber
  // LEDs and is under review (spec 9.2 item 3d).
  //
  // Both the DRL drop and the brake drop key off the REQUEST (li / ri), never
  // off the phase. Keying them off the phase would blink them back on in the
  // indicator's dark half, which is exactly what R48 forbids.
  o.set(OUT_FL_IND, lp);
  o.set(OUT_RL_IND, lp);
  o.set(OUT_FR_IND, rp);
  o.set(OUT_RR_IND, rp);

  // --- Night mode: flash long press, used only while DayNight is unassigned ---
  // NOTE: on the Energica Experia, flash / high beam / low beam are mutually
  // exclusive positions of ONE switch. HighBeam is bit 6 AND bit 16 and
  // HighBeamFlash is bit 16, so s.flash also reads true on steady high beam:
  // high beam at any point in a press spends it, or holding high beam would
  // toggle night mode. These bit states are unconfirmed on the bike.
  const bool dayNightMapped = mapFor(cfg, Function::DayNight).count != 0;
  const uint32_t hold = cfg.nightHoldMs >= kMinNightHoldMs ? cfg.nightHoldMs : 800;
  if (s.flash && !est.flashPrev) { est.flashRisingMs = nowMs; est.pressUsed = false; }
  if (s.highBeam) est.pressUsed = true;
  if (s.flash && !est.pressUsed && s.run && !dayNightMapped &&
      (uint32_t)(nowMs - est.flashRisingMs) >= hold) {
    est.nightToggled = !est.nightToggled;
    est.pressUsed = true;
  }
  est.flashPrev = s.flash;
  const bool night = dayNightMapped ? s.night : est.nightToggled;

  if (s.run) {
    const bool brakeOn = s.brake();
    // Front white is the day running light; at night the pods take over.
    o.set(OUT_FL_DRL, !li && !night);
    o.set(OUT_RL_DRL, !li);
    o.set(OUT_FR_DRL, !ri && !night);
    o.set(OUT_RR_DRL, !ri);
    o.set(OUT_RL_BRK, brakeOn && !li);
    o.set(OUT_RR_BRK, brakeOn && !ri);
  }

  // Aux pods are aux lights, not DRLs: full on high beam, low at night. The
  // optional darkening keys off the request like the DRL drop, skips hazards
  // (both pods would go out) and never touches full.
  const AuxLevel base = !s.run      ? AuxLevel::Off
                      : s.highBeam  ? AuxLevel::Full
                      : night       ? AuxLevel::Low
                                    : AuxLevel::Off;
  const bool darken = cfg.auxDarkenOnIndicate && base == AuxLevel::Low && li != ri;
  o.auxL = (darken && li) ? AuxLevel::Off : base;
  o.auxR = (darken && ri) ? AuxLevel::Off : base;
  o.set(OUT_AUX_L, o.auxL == AuxLevel::Full);
  o.set(OUT_AUX_R, o.auxR == AuxLevel::Full);
  return o;
}
