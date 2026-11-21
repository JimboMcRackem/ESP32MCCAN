#include <unity.h>
#include "domain/can_signal.h"

static NumSignal sig(uint8_t start, uint8_t len, bool be = false, bool sgn = false) {
  NumSignal s;
  s.id = 0x200;
  s.startBit = start;
  s.length = len;
  s.bigEndian = be;
  s.isSigned = sgn;
  return s;
}

static int64_t raw(const uint8_t d[8], const NumSignal& s) {
  int64_t r = 0x7EADBEEF;
  TEST_ASSERT_TRUE(decodeRaw(d, s, r));
  return r;
}

void test_intel_byte_aligned_16() {
  const uint8_t d[8] = {0x34, 0x12};
  TEST_ASSERT_EQUAL_INT64(0x1234, raw(d, sig(0, 16)));
}

void test_intel_unaligned_12() {
  const uint8_t d[8] = {0xF0, 0xAB};
  TEST_ASSERT_EQUAL_INT64(0xABF, raw(d, sig(4, 12)));
}

void test_motorola_16() {
  const uint8_t d[8] = {0x12, 0x34};
  TEST_ASSERT_EQUAL_INT64(0x1234, raw(d, sig(7, 16, true)));
}

void test_motorola_12_crosses() {
  const uint8_t d[8] = {0x0A, 0xBC};
  TEST_ASSERT_EQUAL_INT64(0xABC, raw(d, sig(3, 12, true)));
}

void test_signed_negative() {
  const uint8_t d[8] = {0xFF, 0xFF};
  TEST_ASSERT_EQUAL_INT64(-1, raw(d, sig(0, 16, false, true)));
}

void test_signed_8_min() {
  const uint8_t d[8] = {0x80};
  TEST_ASSERT_EQUAL_INT64(-128, raw(d, sig(0, 8, false, true)));
}

void test_unsigned_high_bit() {
  const uint8_t d[8] = {0x80};
  TEST_ASSERT_EQUAL_INT64(128, raw(d, sig(0, 8)));
}

void test_len_1() {
  const uint8_t d[8] = {0x04};
  TEST_ASSERT_EQUAL_INT64(1, raw(d, sig(2, 1)));
}

void test_len_32() {
  const uint8_t d[8] = {0x78, 0x56, 0x34, 0x12};
  TEST_ASSERT_EQUAL_INT64(0x12345678, raw(d, sig(0, 32)));
}

void test_signed_32_min() {
  const uint8_t d[8] = {0x00, 0x00, 0x00, 0x80};
  TEST_ASSERT_EQUAL_INT64(-2147483648LL, raw(d, sig(0, 32, false, true)));
}

void test_scale_offset() {
  const uint8_t d[8] = {100};
  NumSignal s = sig(0, 8);
  s.scale = 0.1f;
  s.offset = -40.0f;
  float v = 0;
  TEST_ASSERT_TRUE(decodeSignal(d, s, v));
  TEST_ASSERT_FLOAT_WITHIN(1e-4f, -30.0f, v);
}

void test_unmapped_len_0_fails() {
  const uint8_t d[8] = {0};
  int64_t r; float v;
  TEST_ASSERT_FALSE(decodeRaw(d, sig(0, 0), r));
  TEST_ASSERT_FALSE(decodeSignal(d, sig(0, 0), v));
  TEST_ASSERT_FALSE(sig(0, 0).mapped());
}

void test_len_33_fails() {
  const uint8_t d[8] = {0};
  int64_t r;
  TEST_ASSERT_FALSE(decodeRaw(d, sig(0, 33), r));
}

void test_intel_past_end_fails() {
  const uint8_t d[8] = {0};
  int64_t r;
  TEST_ASSERT_FALSE(decodeRaw(d, sig(60, 8), r));
}

void test_intel_last_bits_ok() {
  const uint8_t d[8] = {0, 0, 0, 0, 0, 0, 0, 0xA5};
  TEST_ASSERT_EQUAL_INT64(0xA5, raw(d, sig(56, 8)));
}

void test_motorola_past_end_fails() {
  const uint8_t d[8] = {0};
  int64_t r;
  TEST_ASSERT_FALSE(decodeRaw(d, sig(63, 16, true), r));
}

void test_start_bit_out_of_range_fails() {
  const uint8_t d[8] = {0};
  int64_t r;
  TEST_ASSERT_FALSE(decodeRaw(d, sig(64, 1), r));
  TEST_ASSERT_FALSE(decodeRaw(d, sig(64, 1, true), r));
}

void setUp(void) {}
void tearDown(void) {}

int main(int, char**) {
  UNITY_BEGIN();
  RUN_TEST(test_intel_byte_aligned_16);
  RUN_TEST(test_intel_unaligned_12);
  RUN_TEST(test_motorola_16);
  RUN_TEST(test_motorola_12_crosses);
  RUN_TEST(test_signed_negative);
  RUN_TEST(test_signed_8_min);
  RUN_TEST(test_unsigned_high_bit);
  RUN_TEST(test_len_1);
  RUN_TEST(test_len_32);
  RUN_TEST(test_signed_32_min);
  RUN_TEST(test_scale_offset);
  RUN_TEST(test_unmapped_len_0_fails);
  RUN_TEST(test_len_33_fails);
  RUN_TEST(test_intel_past_end_fails);
  RUN_TEST(test_intel_last_bits_ok);
  RUN_TEST(test_motorola_past_end_fails);
  RUN_TEST(test_start_bit_out_of_range_fails);
  return UNITY_END();
}
