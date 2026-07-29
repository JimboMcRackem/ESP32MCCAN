#include <unity.h>
#include "domain/color.h"

void test_rgb_equality() {
  Rgb a{255, 80, 0};
  Rgb b{255, 80, 0};
  Rgb c{0, 0, 0};
  TEST_ASSERT_TRUE(a == b);
  TEST_ASSERT_TRUE(a != c);
}

void setUp(void) {}
void tearDown(void) {}

int main(int, char**) {
  UNITY_BEGIN();
  RUN_TEST(test_rgb_equality);
  return UNITY_END();
}
