#include "hal/pwm_pca9685.h"

Pca9685Pwm::Pca9685Pwm(uint8_t i2cAddr) : drv_(i2cAddr) {}

bool Pca9685Pwm::begin(uint32_t pwmFreqHz) {
  if (!drv_.begin()) return false;    // PCA9685 not responding on I2C
  drv_.setPWMFreq(pwmFreqHz);         // ~1000 Hz for LEDs (PCA9685 max ~1526 Hz)
  for (uint8_t ch = 0; ch < CH_COUNT; ++ch) drv_.setPin(ch, 0);
  return true;
}

void Pca9685Pwm::setDuty(uint8_t channel, uint8_t duty) {
  if (channel >= CH_COUNT) return;
  // Scale 8-bit duty (0-255) to the PCA9685's 12-bit range (0-4095).
  uint16_t val = (uint16_t)((uint32_t)duty * 4095u / 255u);
  drv_.setPin(channel, val);          // setPin handles full-off (0) and full-on (4095)
}
