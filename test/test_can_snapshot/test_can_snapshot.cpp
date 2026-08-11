#include <unity.h>
#include "domain/can_state.h"

void setUp(void) {}
void tearDown(void) {}

static void frame(uint8_t b0, uint8_t b1, uint8_t data[8]) {
  for (int i = 0; i < 8; ++i) data[i] = 0;
  data[0] = b0; data[1] = b1;
}

void test_empty_snapshot_is_zero(void) {
  CanState s;
  CanFrameSnapshot out[16];
  TEST_ASSERT_EQUAL_INT(0, s.snapshot(out, 16));
}

void test_snapshot_returns_seen_frames(void) {
  CanState s;
  uint8_t d[8];
  frame(0xAA, 0x01, d); s.update(0x102, d);
  frame(0xBB, 0x02, d); s.update(0x400, d);

  CanFrameSnapshot out[16];
  int n = s.snapshot(out, 16);
  TEST_ASSERT_EQUAL_INT(2, n);

  // Find 0x102 in the result and check its bytes.
  bool found = false;
  for (int i = 0; i < n; ++i) {
    if (out[i].id == 0x102) {
      found = true;
      TEST_ASSERT_EQUAL_UINT8(0xAA, out[i].data[0]);
      TEST_ASSERT_EQUAL_UINT8(0x01, out[i].data[1]);
    }
  }
  TEST_ASSERT_TRUE(found);
}

void test_snapshot_respects_maxOut(void) {
  CanState s;
  uint8_t d[8] = {0};
  s.update(0x100, d);
  s.update(0x200, d);
  s.update(0x300, d);
  CanFrameSnapshot out[2];
  TEST_ASSERT_EQUAL_INT(2, s.snapshot(out, 2));   // clamped to maxOut
}

void test_update_refreshes_existing_frame(void) {
  CanState s;
  uint8_t d[8] = {0};
  d[0] = 0x11; s.update(0x102, d);
  d[0] = 0x22; s.update(0x102, d);                // same id updated
  CanFrameSnapshot out[16];
  int n = s.snapshot(out, 16);
  TEST_ASSERT_EQUAL_INT(1, n);
  TEST_ASSERT_EQUAL_UINT8(0x22, out[0].data[0]);
}

int main(int, char**) {
  UNITY_BEGIN();
  RUN_TEST(test_empty_snapshot_is_zero);
  RUN_TEST(test_snapshot_returns_seen_frames);
  RUN_TEST(test_snapshot_respects_maxOut);
  RUN_TEST(test_update_refreshes_existing_frame);
  return UNITY_END();
}
