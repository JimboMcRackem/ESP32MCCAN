#include "domain/output_map.h"

void applyIntent(IOutputs& out, IAuxPwm& pwm, const OutputIntent& o) {
  pwm.setDuty(o.auxDuty);
  for (uint8_t i = 0; i < (uint8_t)OUT_COUNT; ++i)
    out.setOutput(i, o.isOn((OutputIndex)i));
}
