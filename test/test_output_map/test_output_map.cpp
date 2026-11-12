#include <unity.h>
#include "domain/output_map.h"
#include "domain/aux_pwm.h"
#include <string>

void tearDown(void) {}

// Both fakes append to one log, so a test can see the order of writes.
static std::string g_log;

void setUp(void) { g_log.clear(); }

class FakeOutputs : public IOutputs {
public:
  bool state[OUT_COUNT] = {false};
  int  writes = 0;
  void setOutput(uint8_t i, bool on) override {
    if (i < OUT_COUNT) state[i] = on;
    ++writes;
    g_log += 'o';
  }
};

class FakePwm : public IAuxPwm {
public:
  int last = -1;
  int writes = 0;
  void setDuty(uint8_t percent) override { last = percent; ++writes; g_log += 'd'; }
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
  FakeOutputs fake; FakePwm pwm;
  OutputIntent o;
  applyIntent(fake, pwm, o);
  TEST_ASSERT_EQUAL_INT(OUT_COUNT, fake.writes);
}

void test_apply_drives_only_the_set_bits() {
  FakeOutputs fake; FakePwm pwm;
  OutputIntent o;
  o.on = outMask(OUT_FR_IND, OUT_AUX_L);
  applyIntent(fake, pwm, o);
  for (uint8_t i = 0; i < OUT_COUNT; ++i) {
    bool expect = (i == OUT_FR_IND || i == OUT_AUX_L);
    TEST_ASSERT_EQUAL_INT((int)expect, (int)fake.state[i]);
  }
}

void test_intents_differing_only_in_duty_are_unequal() {
  OutputIntent a, b;
  b.auxDuty = 15;
  TEST_ASSERT_TRUE(a != b);
}

// The pod must never light at a higher duty than its level asks for, even
// for one tick, so the duty goes out before any switch.
void test_apply_writes_duty_before_any_output() {
  FakeOutputs fake; FakePwm pwm;
  OutputIntent o;
  o.on = outMask(OUT_AUX_L, OUT_AUX_R);
  o.auxDuty = 15;
  applyIntent(fake, pwm, o);
  TEST_ASSERT_EQUAL_INT(15, pwm.last);
  TEST_ASSERT_EQUAL_STRING("doooooooooooo", g_log.c_str());
}

void test_apply_writes_duty_every_call() {
  FakeOutputs fake; FakePwm pwm;
  OutputIntent o;
  applyIntent(fake, pwm, o);
  applyIntent(fake, pwm, o);
  TEST_ASSERT_EQUAL_INT(2, pwm.writes);
}

void test_ledc_duty_mapping() {
  TEST_ASSERT_EQUAL_UINT32(0,    ledcDutyFor(0, 10));
  TEST_ASSERT_EQUAL_UINT32(153,  ledcDutyFor(15, 10));
  TEST_ASSERT_EQUAL_UINT32(1024, ledcDutyFor(100, 10));
  TEST_ASSERT_EQUAL_UINT32(1024, ledcDutyFor(250, 10));
}

int main(int, char**) {
  UNITY_BEGIN();
  RUN_TEST(test_out_count_is_twelve);
  RUN_TEST(test_set_and_ison_round_trip);
  RUN_TEST(test_outmask_builds_the_same_word_as_set);
  RUN_TEST(test_apply_writes_every_output_exactly_once);
  RUN_TEST(test_apply_drives_only_the_set_bits);
  RUN_TEST(test_intents_differing_only_in_duty_are_unequal);
  RUN_TEST(test_apply_writes_duty_before_any_output);
  RUN_TEST(test_apply_writes_duty_every_call);
  RUN_TEST(test_ledc_duty_mapping);
  return UNITY_END();
}
