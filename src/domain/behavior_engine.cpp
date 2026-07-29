#include "domain/behavior_engine.h"

static const Rgb OFF{0, 0, 0};

static bool flashIsOn(const Config& cfg, uint32_t nowMs) {
  uint32_t period = cfg.blinkPeriodMs ? cfg.blinkPeriodMs : 340;
  return (nowMs % (2 * period)) < period;
}

OutputIntent computeOutputs(const LogicalState& s, const Config& cfg,
                            uint32_t nowMs, EngineState& est) {
  OutputIntent o;
  const bool on = flashIsOn(cfg, nowMs);
  const Rgb orange = cfg.indicatorOrange;
  const Rgb white  = s.night ? cfg.drlWhiteNight : cfg.drlWhiteDay;
  const Rgb dimRed = s.night ? cfg.drlDimRedNight : cfg.drlDimRedDay;
  const Rgb flashCol = on ? orange : OFF;

  if (!s.run) {
    // DRL & brake off; indicators/hazards still function.
    o.frontL = s.leftInd  ? flashCol : OFF;
    o.frontR = s.rightInd ? flashCol : OFF;
    o.rearL  = s.leftInd  ? flashCol : OFF;
    o.rearR  = s.rightInd ? flashCol : OFF;
  } else {
    const bool brakeOn = s.brake();
    o.frontL = s.leftInd  ? flashCol : white;
    o.frontR = s.rightInd ? flashCol : white;
    o.rearL  = s.leftInd  ? flashCol : (brakeOn ? cfg.brakeRed : dimRed);
    o.rearR  = s.rightInd ? flashCol : (brakeOn ? cfg.brakeRed : dimRed);
  }

  // --- Spot latch state machine (flash long-press) ---
  if (s.lowBeam) {
    est.spotLatched = false;                 // auto-drop on low beam
  }
  if (s.flash && !est.flashPrev) {
    est.flashRisingMs = nowMs;               // rising edge: start hold timer
  }
  if (s.flash && (nowMs - est.flashRisingMs) >= cfg.spotHoldMs) {
    est.spotLatched = true;
  }
  est.flashPrev = s.flash;

  // --- Denali level selection ---
  if (!s.run) {
    o.denali = 0;
  } else if (est.spotLatched) {
    o.denali = cfg.denaliSpot;
  } else if (s.highBeam) {
    o.denali = cfg.denaliHigh;
  } else if (s.lowBeam || s.night) {
    o.denali = cfg.denaliLow;
  } else {
    o.denali = cfg.denaliDay;
  }
  return o;
}
