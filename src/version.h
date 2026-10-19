#pragma once
#include <stdint.h>

// Bumped for every release; tools/sign_update.py reads both values from here.
constexpr uint32_t kBuildNumber = 1;
constexpr const char* kVersionString = "1.0.0";
