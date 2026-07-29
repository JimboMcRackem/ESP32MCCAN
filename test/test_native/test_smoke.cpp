#include <unity.h>
#include "domain/color.h"
#include "domain/logical_state.h"
#include "domain/output_intent.h"

void test_rgb_equality() {
  Rgb a{255, 80, 0};
  Rgb b{255, 80, 0};
  Rgb c{0, 0, 0};
  TEST_ASSERT_TRUE(a == b);
  TEST_ASSERT_TRUE(a != c);
}

// Forward declarations for tests defined in test_types.cpp
void test_hazards_requires_both_indicators();
void test_brake_is_front_or_rear();
void test_output_intent_defaults_dark();

void setUp(void) {}
void tearDown(void) {}

int main(int, char**) {
  UNITY_BEGIN();
  RUN_TEST(test_rgb_equality);
  RUN_TEST(test_hazards_requires_both_indicators);
  RUN_TEST(test_brake_is_front_or_rear);
  RUN_TEST(test_output_intent_defaults_dark);
  return UNITY_END();
}
