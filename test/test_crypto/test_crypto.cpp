#include <unity.h>
#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <stddef.h>
#include "domain/sha256.h"
#include "domain/signature.h"
#include "../test_update_image/vectors.h"

void setUp() {}
void tearDown() {}

static void hex(const uint8_t* d, char* out) {
  for (int i = 0; i < 32; i++) sprintf(out + 2 * i, "%02x", d[i]);
}

static void expectDigest(const char* msg, const char* want) {
  Sha256 s;
  s.update((const uint8_t*)msg, strlen(msg));
  uint8_t d[32];
  s.finish(d);
  char h[65];
  hex(d, h);
  TEST_ASSERT_EQUAL_STRING(want, h);
}

void test_sha256_empty() {
  expectDigest("", "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855");
}
void test_sha256_abc() {
  expectDigest("abc", "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad");
}
void test_sha256_two_block() {
  expectDigest("abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq",
               "248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd419db06c1");
}
void test_sha256_split_updates() {
  Sha256 s;
  s.update((const uint8_t*)"a", 1);
  s.update((const uint8_t*)"bc", 2);
  uint8_t d[32];
  s.finish(d);
  char h[65];
  hex(d, h);
  TEST_ASSERT_EQUAL_STRING("ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad", h);
}

static bool verifyBuild7(int flipAt) {
  static uint8_t buf[sizeof(kMcupBuild7)];
  memcpy(buf, kMcupBuild7, kMcupBuild7Len);
  if (flipAt >= 0) buf[flipAt] ^= 0x01;
  size_t body = kMcupBuild7Len - 64;
  Sha256 s;
  s.update(buf, body);
  uint8_t d[32];
  s.finish(d);
  return verifyP256(kTestPubKey, d, buf + body);
}

void test_verify_good_signature() { TEST_ASSERT_TRUE(verifyBuild7(-1)); }
void test_verify_flipped_bit() { TEST_ASSERT_FALSE(verifyBuild7(100)); }
void test_verify_zero_key_fails() {
  size_t body = kMcupBuild7Len - 64;
  Sha256 s;
  s.update(kMcupBuild7, body);
  uint8_t d[32];
  s.finish(d);
  uint8_t zero[64] = {0};
  TEST_ASSERT_FALSE(verifyP256(zero, d, kMcupBuild7 + body));
}

int main() {
  UNITY_BEGIN();
  RUN_TEST(test_sha256_empty);
  RUN_TEST(test_sha256_abc);
  RUN_TEST(test_sha256_two_block);
  RUN_TEST(test_sha256_split_updates);
  RUN_TEST(test_verify_good_signature);
  RUN_TEST(test_verify_flipped_bit);
  RUN_TEST(test_verify_zero_key_fails);
  return UNITY_END();
}
