#include <unity.h>
#include "domain/logical_state.h"
#include "domain/outputs.h"

void test_hazards_requires_both_indicators() {
  LogicalState s;
  s.leftInd = true;
  TEST_ASSERT_FALSE(s.hazards());
  s.rightInd = true;
  TEST_ASSERT_TRUE(s.hazards());
}

void test_brake_is_front_or_rear() {
  LogicalState s;
  TEST_ASSERT_FALSE(s.brake());
  s.rearBrake = true;
  TEST_ASSERT_TRUE(s.brake());
  s.rearBrake = false;
  s.frontBrake = true;
  TEST_ASSERT_TRUE(s.brake());
}

void test_output_intent_defaults_dark() {
  TEST_ASSERT_EQUAL_UINT16(0, OutputIntent{}.on);
}

void setUp(void) {}
void tearDown(void) {}

int main(int, char**) {
  UNITY_BEGIN();
  RUN_TEST(test_hazards_requires_both_indicators);
  RUN_TEST(test_brake_is_front_or_rear);
  RUN_TEST(test_output_intent_defaults_dark);
  return UNITY_END();
}
