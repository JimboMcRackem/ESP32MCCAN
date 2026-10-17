#pragma once
#include "domain/outputs.h"
#include "hal/ioutputs.h"

// Writes the whole intent out, every output every call. Unconditional writes
// keep the driver stateless and make a missed update impossible.
void applyIntent(IOutputs& out, const OutputIntent& o);
