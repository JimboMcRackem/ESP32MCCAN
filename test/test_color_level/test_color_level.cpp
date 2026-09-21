#include <unity.h>
#include "domain/color.h"

void setUp(void) {}
void tearDown(void) {}

void test_gamma_endpoints_are_exact(void) {
  TEST_ASSERT_EQUAL_UINT8(0, kGammaEncode[0]);
  TEST_ASSERT_EQUAL_UINT8(255, kGammaEncode[255]);
  TEST_ASSERT_EQUAL_UINT8(0, kGammaDecode[0]);
  TEST_ASSERT_EQUAL_UINT8(255, kGammaDecode[255]);
}

void test_gamma_encode_is_monotonic(void) {
  for (int i = 0; i < 255; ++i) {
    TEST_ASSERT_TRUE_MESSAGE(kGammaEncode[i] <= kGammaEncode[i + 1],
                             "kGammaEncode must be non-decreasing");
  }
}

void test_resolve_at_full_level_is_the_hue(void) {
  ColorLevel c{ Rgb{255, 80, 0}, 255 };
  TEST_ASSERT_TRUE((resolveColor(c) == Rgb{255, 80, 0}));
}

void test_resolve_at_zero_level_is_off(void) {
  ColorLevel c{ Rgb{255, 80, 0}, 0 };
  TEST_ASSERT_TRUE((resolveColor(c) == Rgb{0, 0, 0}));
}

void test_resolve_scales_channels_by_one_gamma_corrected_level(void) {
  // gamma8(128) == 56, so {255,128,0} at level 128 -> {56, 128*56/255, 0}.
  TEST_ASSERT_EQUAL_UINT8(56, kGammaEncode[128]);
  ColorLevel c{ Rgb{255, 128, 0}, 128 };
  TEST_ASSERT_TRUE((resolveColor(c) == Rgb{56, 28, 0}));
}

void test_hue_ratio_is_preserved_across_levels(void) {
  // The point of levelwise gamma: dimming must not drift the hue. The ratio
  // green/red stays at 128/255 (within one count) at every level.
  const Rgb hue{255, 128, 0};
  for (int lvl = 8; lvl <= 255; ++lvl) {
    Rgb out = resolveColor(ColorLevel{hue, (uint8_t)lvl});
    int expectG = (128 * kGammaEncode[lvl]) / 255;
    TEST_ASSERT_EQUAL_UINT8(expectG, out.g);
    TEST_ASSERT_EQUAL_UINT8(0, out.b);
  }
}

void test_from_rgb_normalizes_hue_and_extracts_level(void) {
  ColorLevel c = colorFromRgb(Rgb{120, 0, 0});
  TEST_ASSERT_TRUE((c.hue == Rgb{255, 0, 0}));
  TEST_ASSERT_EQUAL_UINT8(kGammaDecode[120], c.level);
}

void test_from_rgb_black_keeps_a_usable_hue(void) {
  // Black has no hue to recover; default to white at level 0 so a user who
  // raises the level from a black entry gets white, not another black.
  ColorLevel c = colorFromRgb(Rgb{0, 0, 0});
  TEST_ASSERT_TRUE((c.hue == Rgb{255, 255, 255}));
  TEST_ASSERT_EQUAL_UINT8(0, c.level);
}

void test_migration_is_exact_for_every_shipped_default(void) {
  // The six values Config ships today. Migration must not change the bike.
  const Rgb shipped[6] = {
    {255, 255, 255},  // drlWhiteDay
    {120, 120, 120},  // drlWhiteNight
    {120, 0, 0},      // drlDimRedDay
    {60, 0, 0},       // drlDimRedNight
    {255, 80, 0},     // indicatorOrange
    {255, 0, 0},      // brakeRed
  };
  for (int i = 0; i < 6; ++i) {
    Rgb back = resolveColor(colorFromRgb(shipped[i]));
    TEST_ASSERT_TRUE_MESSAGE((back == shipped[i]),
                             "a shipped default did not migrate exactly");
  }
}

void test_migration_round_trip_on_a_red_ramp_is_within_one(void) {
  for (int r = 0; r <= 255; ++r) {
    Rgb src{(uint8_t)r, 0, 0};
    Rgb back = resolveColor(colorFromRgb(src));
    int err = (int)back.r - r;
    if (err < 0) err = -err;
    TEST_ASSERT_TRUE_MESSAGE(err <= 1, "red ramp round trip drifted by >1");
  }
}

void test_migration_round_trip_on_arbitrary_triples_is_within_two(void) {
  // Hue normalisation rounds as well as gamma, so a non-neutral triple can
  // land 2 counts out. Worst measured case: (162,121,0) -> (161,119,0).
  for (int r = 0; r <= 255; ++r) {
    const int gs[3] = {0, r / 2, r};
    for (int gi = 0; gi < 3; ++gi) {
      Rgb src{(uint8_t)r, (uint8_t)gs[gi], (uint8_t)(r / 3)};
      Rgb back = resolveColor(colorFromRgb(src));
      const int d[3] = {(int)back.r - src.r, (int)back.g - src.g, (int)back.b - src.b};
      for (int k = 0; k < 3; ++k) {
        int e = d[k] < 0 ? -d[k] : d[k];
        TEST_ASSERT_TRUE_MESSAGE(e <= 2, "arbitrary triple drifted by >2");
      }
    }
  }
}

int main(int, char**) {
  UNITY_BEGIN();
  RUN_TEST(test_gamma_endpoints_are_exact);
  RUN_TEST(test_gamma_encode_is_monotonic);
  RUN_TEST(test_resolve_at_full_level_is_the_hue);
  RUN_TEST(test_resolve_at_zero_level_is_off);
  RUN_TEST(test_resolve_scales_channels_by_one_gamma_corrected_level);
  RUN_TEST(test_hue_ratio_is_preserved_across_levels);
  RUN_TEST(test_from_rgb_normalizes_hue_and_extracts_level);
  RUN_TEST(test_from_rgb_black_keeps_a_usable_hue);
  RUN_TEST(test_migration_is_exact_for_every_shipped_default);
  RUN_TEST(test_migration_round_trip_on_a_red_ramp_is_within_one);
  RUN_TEST(test_migration_round_trip_on_arbitrary_triples_is_within_two);
  return UNITY_END();
}
