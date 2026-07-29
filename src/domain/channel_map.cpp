#include "domain/channel_map.h"

static void applyRgb(IPwm& pwm, uint8_t baseCh, const Rgb& c) {
  pwm.setDuty(baseCh + 0, c.r);
  pwm.setDuty(baseCh + 1, c.g);
  pwm.setDuty(baseCh + 2, c.b);
}

void applyIntent(IPwm& pwm, const OutputIntent& o) {
  applyRgb(pwm, CH_FRONTL_R, o.frontL);
  applyRgb(pwm, CH_FRONTR_R, o.frontR);
  applyRgb(pwm, CH_REARL_R,  o.rearL);
  applyRgb(pwm, CH_REARR_R,  o.rearR);
  pwm.setDuty(CH_DENALI_A, o.denali);
  pwm.setDuty(CH_DENALI_B, o.denali);
}
