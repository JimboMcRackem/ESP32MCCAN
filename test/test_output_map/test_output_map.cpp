#include <unity.h>
#include "domain/output_map.h"

void setUp(void) {}
void tearDown(void) {}

class FakeOutputs : public IOutputs {
public:
  bool state[OUT_COUNT] = {false};
  int  writes = 0;
  void setOutput(uint8_t i, bool on) override {
    if (i < OUT_COUNT) state[i] = on;
    ++writes;
  }
};

void test_out_count_is_twelve() {
  TEST_ASSERT_EQUAL_INT(12, (int)OUT_COUNT);
}

void test_set_and_ison_round_trip() {
  OutputIntent o;
  TEST_ASSERT_FALSE(o.isOn(OUT_RL_BRK));
  o.set(OUT_RL_BRK, true);
  TEST_ASSERT_TRUE(o.isOn(OUT_RL_BRK));
  TEST_ASSERT_FALSE(o.isOn(OUT_RR_BRK));   // neighbours untouched
  o.set(OUT_RL_BRK, false);
  TEST_ASSERT_EQUAL_UINT16(0, o.on);
}

void test_outmask_builds_the_same_word_as_set() {
  OutputIntent o;
  o.set(OUT_FL_DRL, true);
  o.set(OUT_AUX_R, true);
  TEST_ASSERT_EQUAL_UINT16(outMask(OUT_FL_DRL, OUT_AUX_R), o.on);
}

void test_apply_writes_every_output_exactly_once() {
  FakeOutputs fake;
  OutputIntent o;
  applyIntent(fake, o);
  TEST_ASSERT_EQUAL_INT(OUT_COUNT, fake.writes);
}

void test_apply_drives_only_the_set_bits() {
  FakeOutputs fake;
  OutputIntent o;
  o.on = outMask(OUT_FR_IND, OUT_AUX_L);
  applyIntent(fake, o);
  for (uint8_t i = 0; i < OUT_COUNT; ++i) {
    bool expect = (i == OUT_FR_IND || i == OUT_AUX_L);
    TEST_ASSERT_EQUAL_INT((int)expect, (int)fake.state[i]);
  }
}

int main(int, char**) {
  UNITY_BEGIN();
  RUN_TEST(test_out_count_is_twelve);
  RUN_TEST(test_set_and_ison_round_trip);
  RUN_TEST(test_outmask_builds_the_same_word_as_set);
  RUN_TEST(test_apply_writes_every_output_exactly_once);
  RUN_TEST(test_apply_drives_only_the_set_bits);
  return UNITY_END();
}
