#include <unity.h>
#include <string.h>
#include <stdint.h>
#include <stddef.h>
#include <vector>
#include "domain/update_image.h"
#include "../test_update_image/vectors.h"

void setUp() {}
void tearDown() {}

struct FakeSink : IUpdateSink {
  int begins = 0;
  uint32_t beganLen = 0;
  int writes = 0;
  bool failWrite = false;
  std::vector<uint8_t> written;
  bool begin(uint32_t n) override { begins++; beganLen = n; return true; }
  bool write(const uint8_t* d, size_t n) override {
    writes++;
    if (failWrite) return false;
    written.insert(written.end(), d, d + n);
    return true;
  }
};

static std::vector<uint8_t> blob7() {
  return std::vector<uint8_t>(kMcupBuild7, kMcupBuild7 + kMcupBuild7Len);
}

static bool feedChunks(UpdateReceiver& r, const uint8_t* d, size_t n, size_t chunk) {
  bool ok = true;
  for (size_t i = 0; i < n && ok; i += chunk) ok = r.feed(d + i, (n - i < chunk) ? n - i : chunk);
  return ok;
}

void test_valid_file_streams_image_and_verifies() {
  FakeSink s;
  UpdateReceiver r(5, 100000, kTestPubKey, s);
  TEST_ASSERT_TRUE(feedChunks(r, kMcupBuild7, kMcupBuild7Len, 37));
  TEST_ASSERT_EQUAL(UpdateError::None, r.finish());
  TEST_ASSERT_EQUAL_INT(1, s.begins);
  TEST_ASSERT_EQUAL_UINT32(1000, s.beganLen);
  TEST_ASSERT_EQUAL_UINT(1000, s.written.size());
  TEST_ASSERT_EQUAL_MEMORY(kImage, s.written.data(), 1000);
  TEST_ASSERT_NOT_NULL(r.header());
  TEST_ASSERT_EQUAL_UINT32(7, r.header()->build);
  TEST_ASSERT_EQUAL_UINT32(1000, r.header()->imageLen);
  TEST_ASSERT_EQUAL_STRING("test-7", r.header()->display);
}

void test_same_build_accepted() {
  FakeSink s;
  UpdateReceiver r(7, 100000, kTestPubKey, s);
  TEST_ASSERT_TRUE(feedChunks(r, kMcupBuild7, kMcupBuild7Len, 100));
  TEST_ASSERT_EQUAL(UpdateError::None, r.finish());
}

void test_older_build_refused() {
  FakeSink s;
  UpdateReceiver r(7, 100000, kTestPubKey, s);
  TEST_ASSERT_FALSE(feedChunks(r, kMcupBuild3, kMcupBuild3Len, 50));
  TEST_ASSERT_EQUAL(UpdateError::Downgrade, r.error());
  TEST_ASSERT_EQUAL(UpdateError::Downgrade, r.finish());
  TEST_ASSERT_EQUAL_INT(0, s.begins);
  TEST_ASSERT_EQUAL_INT(0, s.writes);
}

void test_too_large_refused() {
  FakeSink s;
  UpdateReceiver r(5, 999, kTestPubKey, s);
  TEST_ASSERT_FALSE(feedChunks(r, kMcupBuild7, kMcupBuild7Len, 64));
  TEST_ASSERT_EQUAL(UpdateError::TooLarge, r.error());
  TEST_ASSERT_EQUAL_INT(0, s.begins);
}

void test_raw_firmware_bin_rejected() {
  FakeSink s;
  UpdateReceiver r(5, 100000, kTestPubKey, s);
  uint8_t raw[64];
  memset(raw, 0x11, sizeof raw);
  raw[0] = 0xE9;
  TEST_ASSERT_FALSE(r.feed(raw, sizeof raw));
  TEST_ASSERT_EQUAL(UpdateError::BadMagic, r.error());
  TEST_ASSERT_EQUAL_INT(0, s.begins);
  TEST_ASSERT_EQUAL_INT(0, s.writes);
}

void test_truncated_upload_fails() {
  FakeSink s;
  UpdateReceiver r(5, 100000, kTestPubKey, s);
  TEST_ASSERT_TRUE(feedChunks(r, kMcupBuild7, kMcupBuild7Len - 10, 37));
  TEST_ASSERT_EQUAL(UpdateError::Truncated, r.finish());
}

void test_truncated_in_header_fails() {
  FakeSink s;
  UpdateReceiver r(5, 100000, kTestPubKey, s);
  TEST_ASSERT_TRUE(r.feed(kMcupBuild7, 30));
  TEST_ASSERT_NULL(r.header());
  TEST_ASSERT_EQUAL(UpdateError::Truncated, r.finish());
  TEST_ASSERT_EQUAL_INT(0, s.begins);
}

void test_truncated_in_image_fails() {
  FakeSink s;
  UpdateReceiver r(5, 100000, kTestPubKey, s);
  TEST_ASSERT_TRUE(r.feed(kMcupBuild7, 64 + 400));
  TEST_ASSERT_EQUAL(UpdateError::Truncated, r.finish());
}

void test_extra_bytes_fail() {
  FakeSink s;
  UpdateReceiver r(5, 100000, kTestPubKey, s);
  std::vector<uint8_t> b = blob7();
  b.push_back(0x00);
  TEST_ASSERT_FALSE(feedChunks(r, b.data(), b.size(), 37));
  TEST_ASSERT_EQUAL(UpdateError::ExtraBytes, r.error());
  TEST_ASSERT_EQUAL(UpdateError::ExtraBytes, r.finish());
}

void test_tampered_image_fails() {
  FakeSink s;
  UpdateReceiver r(5, 100000, kTestPubKey, s);
  std::vector<uint8_t> b = blob7();
  b[64 + 500] ^= 0x01;
  TEST_ASSERT_TRUE(feedChunks(r, b.data(), b.size(), 37));
  TEST_ASSERT_EQUAL(UpdateError::BadSignature, r.finish());
}

void test_bad_format_version() {
  FakeSink s;
  UpdateReceiver r(5, 100000, kTestPubKey, s);
  std::vector<uint8_t> b = blob7();
  b[4] = 2;
  b[5] = 0;
  TEST_ASSERT_FALSE(feedChunks(r, b.data(), b.size(), 64));
  TEST_ASSERT_EQUAL(UpdateError::BadFormat, r.error());
  TEST_ASSERT_EQUAL_INT(0, s.begins);
}

void test_zero_length_rejected() {
  FakeSink s;
  UpdateReceiver r(5, 100000, kTestPubKey, s);
  std::vector<uint8_t> b = blob7();
  b[12] = b[13] = b[14] = b[15] = 0;
  TEST_ASSERT_FALSE(feedChunks(r, b.data(), b.size(), 64));
  TEST_ASSERT_EQUAL(UpdateError::BadLength, r.error());
  TEST_ASSERT_EQUAL_INT(0, s.begins);
}

void test_display_without_nul_rejected() {
  FakeSink s;
  UpdateReceiver r(5, 100000, kTestPubKey, s);
  std::vector<uint8_t> b = blob7();
  for (int i = 16; i < 48; i++) b[i] = 'A';
  TEST_ASSERT_FALSE(feedChunks(r, b.data(), b.size(), 64));
  TEST_ASSERT_EQUAL(UpdateError::BadLength, r.error());
  TEST_ASSERT_EQUAL_INT(0, s.begins);
}

void test_sink_failure_reported() {
  FakeSink s;
  s.failWrite = true;
  UpdateReceiver r(5, 100000, kTestPubKey, s);
  TEST_ASSERT_FALSE(feedChunks(r, kMcupBuild7, kMcupBuild7Len, 37));
  TEST_ASSERT_EQUAL(UpdateError::WriteFailed, r.error());
  TEST_ASSERT_EQUAL(UpdateError::WriteFailed, r.finish());
}

void test_errors_latch_and_sink_not_called_again() {
  FakeSink s;
  s.failWrite = true;
  UpdateReceiver r(5, 100000, kTestPubKey, s);
  TEST_ASSERT_FALSE(r.feed(kMcupBuild7, 200));
  int w = s.writes;
  TEST_ASSERT_FALSE(r.feed(kMcupBuild7 + 200, 100));
  TEST_ASSERT_EQUAL_INT(w, s.writes);
  TEST_ASSERT_EQUAL(UpdateError::WriteFailed, r.error());
}

void test_parked_rule() {
  TEST_ASSERT_FALSE(parkedForUpdate(false, false));
  TEST_ASSERT_TRUE(parkedForUpdate(true, false));
  TEST_ASSERT_TRUE(parkedForUpdate(false, true));
  TEST_ASSERT_TRUE(parkedForUpdate(true, true));
}

void test_not_parked_text() {
  TEST_ASSERT_EQUAL_STRING("Park the bike first: kickstand down or ignition off.", kNotParkedText);
}

void test_error_texts() {
  TEST_ASSERT_EQUAL_STRING("", updateErrorText(UpdateError::None));
  TEST_ASSERT_EQUAL_STRING("The upload was cut short. Nothing was changed.", updateErrorText(UpdateError::Truncated));
  TEST_ASSERT_EQUAL_STRING("That is not an MCCAN update file (.mcup).", updateErrorText(UpdateError::BadMagic));
  TEST_ASSERT_EQUAL_STRING("This update is not signed by MCCAN. Nothing was changed.", updateErrorText(UpdateError::BadSignature));
}

int main() {
  UNITY_BEGIN();
  RUN_TEST(test_valid_file_streams_image_and_verifies);
  RUN_TEST(test_same_build_accepted);
  RUN_TEST(test_older_build_refused);
  RUN_TEST(test_too_large_refused);
  RUN_TEST(test_raw_firmware_bin_rejected);
  RUN_TEST(test_truncated_upload_fails);
  RUN_TEST(test_truncated_in_header_fails);
  RUN_TEST(test_truncated_in_image_fails);
  RUN_TEST(test_extra_bytes_fail);
  RUN_TEST(test_tampered_image_fails);
  RUN_TEST(test_bad_format_version);
  RUN_TEST(test_zero_length_rejected);
  RUN_TEST(test_display_without_nul_rejected);
  RUN_TEST(test_sink_failure_reported);
  RUN_TEST(test_errors_latch_and_sink_not_called_again);
  RUN_TEST(test_parked_rule);
  RUN_TEST(test_not_parked_text);
  RUN_TEST(test_error_texts);
  return UNITY_END();
}
