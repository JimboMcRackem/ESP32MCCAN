#include "domain/behavior_engine.h"
#include <cmath>

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
  // brake is off too. The Oxford units could run both at once; amber alone is
  // the user's choice because it reads more clearly (spec 5.3).
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

  // Aux pods: full on high beam, low at night. Each pod's DRL LEDs light
  // whenever it is powered, and a DRL must be off beside an indicating corner,
  // so an indicating side's pod goes Off (hazards: both). At Full this is the
  // user's setting, trading forward light against the rule. It keys off the
  // request like the DRL drop, so the pod does not pulse with the flash.
  const AuxLevel base = !s.run      ? AuxLevel::Off
                      : s.highBeam  ? AuxLevel::Full
                      : night       ? AuxLevel::Low
                                    : AuxLevel::Off;
  const bool darken = base == AuxLevel::Low ||
                      (base == AuxLevel::Full && cfg.auxOffOnIndicateHighBeam);
  o.auxL = (darken && li) ? AuxLevel::Off : base;
  o.auxR = (darken && ri) ? AuxLevel::Off : base;
  // A pod that is not Off is powered; its brightness is its yellow duty.
  o.set(OUT_AUX_L, o.auxL != AuxLevel::Off);
  o.set(OUT_AUX_R, o.auxR != AuxLevel::Off);

  // Brightness per pod. Leaning right (+) puts the right pod on the inside.
  const float k = leanFactor(s, cfg);
  const bool rightIn = k > 0.0f && s.leanDeg > 0.0f;
  const bool leftIn  = k > 0.0f && s.leanDeg < 0.0f;
  const float tL = auxTargetDuty(o.auxL, leftIn, rightIn, k, s, cfg);
  const float tR = auxTargetDuty(o.auxR, rightIn, leftIn, k, s, cfg);

  // Smoothing. Elapsed time by unsigned subtraction, so a millis() wrap
  // between two ticks still gives the real gap.
  const float maxStep = est.dutyInit
      ? kAuxSlewPctPerS * (float)(uint32_t)(nowMs - est.dutyMs) / 1000.0f : 0.0f;
  // Only speed and lean move a pod within its level, so only they glide.
  auto glide = [&](AuxLevel lvl, float target, float& cur, AuxLevel& prev) {
    if (lvl == AuxLevel::Off)                cur = 0.0f;     // off is immediate
    else if (!est.dutyInit || lvl != prev)   cur = target;   // level change: instant
    else if (target > cur)                   cur = (target - cur > maxStep) ? cur + maxStep : target;
    else                                     cur = (cur - target > maxStep) ? cur - maxStep : target;
    prev = lvl;
    return (uint8_t)lroundf(cur);
  };
  o.auxDutyL = glide(o.auxL, tL, est.dutyL, est.prevL);
  o.auxDutyR = glide(o.auxR, tR, est.dutyR, est.prevR);
  est.dutyMs = nowMs;
  est.dutyInit = true;
  return o;
}

float leanFactor(const LogicalState& s, const Config& cfg) {
  if (!cfg.leanEnable || !s.leanValid) return 0.0f;
  if (cfg.leanMinKmh > 0 && (!s.speedValid || s.speedKmh < cfg.leanMinKmh)) return 0.0f;
  const float a = std::fabs(s.leanDeg);
  const float lo = cfg.leanStartDeg, hi = cfg.leanFullDeg;
  if (hi <= lo) return a > lo ? 1.0f : 0.0f;
  if (a <= lo) return 0.0f;
  if (a >= hi) return 1.0f;
  return (a - lo) / (hi - lo);
}

// High beam's duty: the speed curve when it is on and speed is valid,
// otherwise auxFullDuty (today's behaviour).
static float fullBase(const LogicalState& s, const Config& cfg) {
  const float full = cfg.auxFullDuty;
  if (!cfg.speedScaleEnable || !s.speedValid) return full;
  const float slow = cfg.hbSlowDuty < cfg.auxFullDuty ? cfg.hbSlowDuty : full;
  const float lo = cfg.hbSlowKmh, hi = cfg.hbFullKmh;
  const float v = s.speedKmh;
  if (hi <= lo) return v > lo ? full : slow;
  if (v <= lo) return slow;
  if (v >= hi) return full;
  return slow + (full - slow) * (v - lo) / (hi - lo);
}

float auxTargetDuty(AuxLevel level, bool insideOfLean, bool outsideOfLean,
                    float k, const LogicalState& s, const Config& cfg) {
  if (level == AuxLevel::Off) return 0.0f;
  const float base = level == AuxLevel::Low ? (float)auxDutyFor(AuxLevel::Low, cfg)
                                            : fullBase(s, cfg);
  float t = base;
  if (insideOfLean) {
    const float boost = level == AuxLevel::Low ? cfg.leanBoostDuty : cfg.auxFullDuty;
    t = base + k * (boost - base);
    if (t < base) t = base;
  } else if (outsideOfLean) {
    t = base + k * ((float)cfg.leanDimDuty - base);
    if (t > base) t = base;
  }
  const float cap = cfg.auxFullDuty;
  return t > cap ? cap : t;
}

uint8_t auxDutyFor(AuxLevel level, const Config& cfg) {
  switch (level) {
    case AuxLevel::Full: return cfg.auxFullDuty;
    // Low is never brighter than Full, whatever the two settings say.
    case AuxLevel::Low:  return cfg.auxLowDuty < cfg.auxFullDuty ? cfg.auxLowDuty
                                                                  : cfg.auxFullDuty;
    case AuxLevel::Off:
    default:             return 0;
  }
}
