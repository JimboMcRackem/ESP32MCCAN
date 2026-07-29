#pragma once
#include "hal/ipwm.h"
#include "domain/channel_map.h"
#include <Adafruit_PWMServoDriver.h>

// Drives 14 outputs via an external PCA9685 (16-channel, 12-bit, I2C).
class Pca9685Pwm : public IPwm {
public:
  explicit Pca9685Pwm(uint8_t i2cAddr = 0x40);
  bool begin(uint32_t pwmFreqHz);                 // call Wire.begin(sda,scl) first
  void setDuty(uint8_t channel, uint8_t duty) override;
private:
  Adafruit_PWMServoDriver drv_;
};
