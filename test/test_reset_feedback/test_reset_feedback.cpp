#include <unity.h>
#include "domain/reset_feedback.h"

void setUp(void) {}
void tearDown(void) {}

static const uint16_t kAllInd = outMask(OUT_FL_IND, OUT_FR_IND, OUT_RL_IND, OUT_RR_IND);

void test_idle_leaves_intent_unchanged() {
  OutputIntent o; o.on = outMask(OUT_FL_DRL, OUT_RL_BRK); o.auxDuty = 15;
  TEST_ASSERT_TRUE(withResetFeedback(o, ResetPhase::Idle, 0) == o);
  TEST_ASSERT_TRUE(withResetFeedback(o, ResetPhase::Cancelled, 0) == o);
}

void test_armed_blinks_all_indicators_at_10hz() {
  OutputIntent o; o.on = outMask(OUT_FL_DRL);
  TEST_ASSERT_EQUAL_UINT16(outMask(OUT_FL_DRL) | kAllInd,
                           withResetFeedback(o, ResetPhase::Armed, 0).on);
  TEST_ASSERT_EQUAL_UINT16(outMask(OUT_FL_DRL),
                           withResetFeedback(o, ResetPhase::Armed, 50).on);
}

// The dark half forces indicators off even if the engine had one lit.
void test_armed_dark_half_clears_a_lit_indicator() {
  OutputIntent o; o.on = outMask(OUT_FL_IND, OUT_RL_IND);
  TEST_ASSERT_EQUAL_UINT16(0, withResetFeedback(o, ResetPhase::Armed, 50).on);
}

void test_confirmed_holds_all_indicators_on() {
  OutputIntent o;
  TEST_ASSERT_EQUAL_UINT16(kAllInd, withResetFeedback(o, ResetPhase::Confirmed, 50).on);
}

void test_feedback_never_touches_aux() {
  OutputIntent o; o.on = outMask(OUT_AUX_L, OUT_AUX_R);
  o.auxL = o.auxR = AuxLevel::Low; o.auxDuty = 15;
  OutputIntent got = withResetFeedback(o, ResetPhase::Armed, 0);
  TEST_ASSERT_EQUAL_UINT16(outMask(OUT_AUX_L, OUT_AUX_R) | kAllInd, got.on);
  TEST_ASSERT_EQUAL_UINT8(15, got.auxDuty);
  TEST_ASSERT_EQUAL_INT((int)AuxLevel::Low, (int)got.auxL);
}

int main(int, char**) {
  UNITY_BEGIN();
  RUN_TEST(test_idle_leaves_intent_unchanged);
  RUN_TEST(test_armed_blinks_all_indicators_at_10hz);
  RUN_TEST(test_armed_dark_half_clears_a_lit_indicator);
  RUN_TEST(test_confirmed_holds_all_indicators_on);
  RUN_TEST(test_feedback_never_touches_aux);
  return UNITY_END();
}
