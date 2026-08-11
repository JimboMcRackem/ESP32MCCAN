#pragma once
#include "domain/config.h"
#include <string>

std::string configToJson(const Config& c);
Config configFromJson(const std::string& json, bool& ok);
