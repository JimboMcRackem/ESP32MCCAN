#include <unity.h>
#include "domain/channel_map.h"

class FakePwm : public IPwm {
public:
  uint8_t duty[14] = {0};
  void setDuty(uint8_t ch, uint8_t d) override { if (ch < 14) duty[ch] = d; }
};

void test_applies_all_corners_and_both_denali() {
  OutputIntent o;
  o.frontL = {1, 2, 3};
  o.frontR = {4, 5, 6};
  o.rearL  = {7, 8, 9};
  o.rearR  = {10, 11, 12};
  o.denali = 200;
  FakePwm pwm;
  applyIntent(pwm, o);
  TEST_ASSERT_EQUAL_UINT8(1, pwm.duty[0]);   // frontL R
  TEST_ASSERT_EQUAL_UINT8(3, pwm.duty[2]);   // frontL B
  TEST_ASSERT_EQUAL_UINT8(4, pwm.duty[3]);   // frontR R
  TEST_ASSERT_EQUAL_UINT8(9, pwm.duty[8]);   // rearL B
  TEST_ASSERT_EQUAL_UINT8(12, pwm.duty[11]); // rearR B
  TEST_ASSERT_EQUAL_UINT8(200, pwm.duty[12]); // Denali A
  TEST_ASSERT_EQUAL_UINT8(200, pwm.duty[13]); // Denali B
}

void setUp(void) {}
void tearDown(void) {}

int main(int, char**) {
  UNITY_BEGIN();
  RUN_TEST(test_applies_all_corners_and_both_denali);
  return UNITY_END();
}
