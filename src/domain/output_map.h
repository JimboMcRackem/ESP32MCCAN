#pragma once
#include "domain/outputs.h"
#include "hal/ioutputs.h"
#include "hal/iaux_pwm.h"

// Writes the whole intent out, every output every call. Unconditional writes
// keep the driver stateless and make a missed update impossible. The pods'
// duties go first, so a pod switched on in this call never starts at the
// previous, possibly brighter, duty.
void applyIntent(IOutputs& out, IAuxPwm& pwm, const OutputIntent& o);

// Before a planned restart: every output off, both duties 0, then the PWM
// pins parked low, so GPIO 12 (MTDI strap) is not mid-pulse at the reset.
void quietForRestart(IOutputs& out, IAuxPwm& pwm);
