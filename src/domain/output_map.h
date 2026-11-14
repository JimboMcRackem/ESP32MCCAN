#pragma once
#include "domain/outputs.h"
#include "hal/ioutputs.h"
#include "hal/iaux_pwm.h"

// Writes the whole intent out, every output every call. Unconditional writes
// keep the driver stateless and make a missed update impossible. The pods'
// duty goes first, so a pod switched on in this call never starts at the
// previous, possibly brighter, duty.
void applyIntent(IOutputs& out, IAuxPwm& pwm, const OutputIntent& o);
