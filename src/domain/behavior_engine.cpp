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

  o.denali = 0;  // finalized in Task 6
  return o;
}
