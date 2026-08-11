#pragma once
#include "domain/output_intent.h"
#include "hal/ipwm.h"

enum ChannelIndex : uint8_t {
  CH_FRONTL_R = 0, CH_FRONTL_G, CH_FRONTL_B,
  CH_FRONTR_R,     CH_FRONTR_G, CH_FRONTR_B,
  CH_REARL_R,      CH_REARL_G,  CH_REARL_B,
  CH_REARR_R,      CH_REARR_G,  CH_REARR_B,
  CH_DENALI_A,     CH_DENALI_B,
  CH_COUNT   // = 14
};

void applyIntent(IPwm& pwm, const OutputIntent& o);
