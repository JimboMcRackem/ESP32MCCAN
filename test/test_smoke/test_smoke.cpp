#include <unity.h>
#include "domain/outputs.h"

void test_output_intent_defaults_dark() {
  TEST_ASSERT_EQUAL_UINT16(0, OutputIntent{}.on);
}

void setUp(void) {}
void tearDown(void) {}

int main(int, char**) {
  UNITY_BEGIN();
  RUN_TEST(test_output_intent_defaults_dark);
  return UNITY_END();
}
