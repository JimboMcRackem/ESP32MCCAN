#include "hal/can_bus.h"
#include "driver/twai.h"
#include "driver/gpio.h"

bool CanBus::begin(int rxPin, int txPin, uint32_t bitrateBps) {
  twai_general_config_t g = TWAI_GENERAL_CONFIG_DEFAULT(
      (gpio_num_t)txPin, (gpio_num_t)rxPin, TWAI_MODE_LISTEN_ONLY);
  // Experia bus speed assumed 500 kbps (verify during bring-up).
  twai_timing_config_t t = TWAI_TIMING_CONFIG_500KBITS();
  (void)bitrateBps;  // hook for future configurable bitrate
  twai_filter_config_t f = TWAI_FILTER_CONFIG_ACCEPT_ALL();
  if (twai_driver_install(&g, &t, &f) != ESP_OK) return false;
  if (twai_start() != ESP_OK) return false;
  // The driver insists on a real TX GPIO and drives it recessive (HIGH) for as long as it
  // runs. On this board TX is GPIO12, the MTDI strap (HIGH at reset = 1.8 V flash, which
  // does not boot), and nothing else is wired to it. Listen-only never drives TX, so hand the
  // pin back: input, pulled down, alongside the board's R36. Reception is unaffected.
  gpio_set_direction((gpio_num_t)txPin, GPIO_MODE_INPUT);
  gpio_pulldown_en((gpio_num_t)txPin);
  return true;
}

bool CanBus::receive(uint32_t& id, uint8_t data[8]) {
  twai_message_t msg;
  if (twai_receive(&msg, 0) != ESP_OK) return false;   // 0 ticks = non-blocking
  id = msg.identifier;
  for (int i = 0; i < 8; ++i) data[i] = (i < msg.data_length_code) ? msg.data[i] : 0;
  return true;
}
