#include <unity.h>
#include "domain/reset_sequence.h"

void setUp(void) {}
void tearDown(void) {}

// Feed one level every 10 ms over [from, to). Counts each event kind seen.
struct Seen { int armed = 0, cancelled = 0, confirmed = 0; };
static Seen feed(ResetSequence& s, bool pressed, uint32_t from, uint32_t to) {
  Seen n;
  for (uint32_t t = from; t != to; t += 10) {
    switch (s.update(pressed, t)) {
      case ResetEvent::Armed: ++n.armed; break;
      case ResetEvent::Cancelled: ++n.cancelled; break;
      case ResetEvent::Confirmed: ++n.confirmed; break;
      case ResetEvent::None: break;
    }
  }
  return n;
}

void test_arms_at_ten_seconds(void) {
  ResetSequence s;
  Seen n = feed(s, true, 0, 10000);
  TEST_ASSERT_EQUAL(0, n.armed);
  TEST_ASSERT_EQUAL(ResetPhase::Idle, s.phase());
  TEST_ASSERT_EQUAL(ResetEvent::Armed, s.update(true, 10000));
  TEST_ASSERT_EQUAL(ResetPhase::Armed, s.phase());
}

void test_release_in_window_confirms_once(void) {
  ResetSequence s;
  feed(s, true, 0, 10010);                       // armed at 10000
  feed(s, true, 10010, 12000);
  Seen n = feed(s, false, 12000, 12040);         // 40 ms released: not yet
  TEST_ASSERT_EQUAL(0, n.confirmed);
  TEST_ASSERT_EQUAL(ResetEvent::Confirmed, s.update(false, 12050));
  n = feed(s, false, 12060, 30000);
  TEST_ASSERT_EQUAL(0, n.confirmed);
  n = feed(s, true, 30000, 50000);               // a later hold does nothing more
  TEST_ASSERT_EQUAL(0, n.armed + n.confirmed + n.cancelled);
  TEST_ASSERT_EQUAL(ResetPhase::Confirmed, s.phase());
}

void test_still_held_at_window_end_cancels(void) {
  ResetSequence s;
  feed(s, true, 0, 10010);                       // armed at 10000
  Seen n = feed(s, true, 10010, 15000);
  TEST_ASSERT_EQUAL(0, n.cancelled);
  TEST_ASSERT_EQUAL(ResetEvent::Cancelled, s.update(true, 15000));
  TEST_ASSERT_EQUAL(ResetPhase::Cancelled, s.phase());
  n = feed(s, true, 15010, 40000);               // stuck: nothing re-arms
  TEST_ASSERT_EQUAL(0, n.armed + n.confirmed + n.cancelled);
  n = feed(s, false, 40000, 45000);              // a later release does not confirm
  TEST_ASSERT_EQUAL(0, n.confirmed);
  TEST_ASSERT_EQUAL(ResetPhase::Cancelled, s.phase());
}

void test_release_then_new_hold_rearms_after_cancel(void) {
  ResetSequence s;
  feed(s, true, 0, 15010);                       // armed 10000, cancelled 15000
  TEST_ASSERT_EQUAL(ResetPhase::Cancelled, s.phase());
  feed(s, false, 15010, 15030);                  // 20 ms: bounce, not a release
  Seen n = feed(s, true, 15030, 30000);
  TEST_ASSERT_EQUAL(0, n.armed);
  feed(s, false, 30000, 30060);                  // released 50 ms (30000..30050)
  n = feed(s, true, 30060, 40060);
  TEST_ASSERT_EQUAL(0, n.armed);
  TEST_ASSERT_EQUAL(ResetEvent::Armed, s.update(true, 40060));
  feed(s, true, 40070, 41000);
  feed(s, false, 41000, 41050);
  TEST_ASSERT_EQUAL(ResetEvent::Confirmed, s.update(false, 41050));
}

void test_bounce_in_armed_does_not_confirm(void) {
  ResetSequence s;
  feed(s, true, 0, 10010);                       // armed at 10000
  Seen n = feed(s, false, 11000, 11040);         // 40 ms open contact
  n.confirmed += feed(s, true, 11040, 12000).confirmed;
  n.confirmed += feed(s, false, 12000, 12030).confirmed;
  TEST_ASSERT_EQUAL(0, n.confirmed);
  n = feed(s, true, 12030, 15000);
  TEST_ASSERT_EQUAL(0, n.confirmed + n.cancelled);
  TEST_ASSERT_EQUAL(ResetEvent::Cancelled, s.update(true, 15000));
}

void test_release_starting_in_window_confirms_after_it(void) {
  ResetSequence s;
  feed(s, true, 0, 10010);                       // armed at 10000
  feed(s, true, 10010, 14990);
  TEST_ASSERT_EQUAL(ResetEvent::None, s.update(false, 14990));   // release begins in window
  TEST_ASSERT_EQUAL(ResetEvent::None, s.update(false, 15000));   // window end: not a cancel
  feed(s, false, 15010, 15040);
  TEST_ASSERT_EQUAL(ResetEvent::Confirmed, s.update(false, 15040));
}

void test_release_after_window_is_cancel(void) {
  ResetSequence s;
  feed(s, true, 0, 10010);
  feed(s, true, 10010, 14990);
  // Sparse sampling: the first sample after the window is already released.
  TEST_ASSERT_EQUAL(ResetEvent::Cancelled, s.update(false, 15020));
  Seen n = feed(s, false, 15030, 20000);
  TEST_ASSERT_EQUAL(0, n.confirmed);
}

// Anchors chosen so the window [arm, arm+5000) spans the millis() wrap: arm
// at 0xFFFFF830 (wrap - 2000), window end at 3000 after the wrap. A naive
// `now >= armedAt + 5000` compares against 3000 and cancels on the first sample
// after arming; a signed/absolute compare never reaches the end. Wrap-safe
// arithmetic cancels exactly at 3000 and confirms a release at 1000.
static const uint32_t kStart = 0u - 12000u;     // hold starts; arm = wrap - 2000

void test_wrap_cancel_exactly_at_window_end(void) {
  ResetSequence s;
  const uint32_t arm = kStart + 10000;                 // 0xFFFFF830
  Seen n = feed(s, true, kStart, arm);
  TEST_ASSERT_EQUAL(0, n.armed);
  TEST_ASSERT_EQUAL(ResetEvent::Armed, s.update(true, arm));
  n = feed(s, true, arm + 10, 3000);                   // crosses 0
  TEST_ASSERT_EQUAL(0, n.cancelled);
  TEST_ASSERT_EQUAL(ResetPhase::Armed, s.phase());
  TEST_ASSERT_EQUAL(ResetEvent::Cancelled, s.update(true, 3000));
}

void test_wrap_release_confirms(void) {
  ResetSequence s;
  const uint32_t arm = kStart + 10000;
  feed(s, true, kStart, arm + 10);
  TEST_ASSERT_EQUAL(ResetPhase::Armed, s.phase());
  Seen n = feed(s, true, arm + 10, 1000);               // crosses 0
  TEST_ASSERT_EQUAL(0, n.cancelled);
  n = feed(s, false, 1000, 1050);
  TEST_ASSERT_EQUAL(0, n.confirmed + n.cancelled);
  TEST_ASSERT_EQUAL(ResetEvent::Confirmed, s.update(false, 1050));
}

int main(int, char**) {
  UNITY_BEGIN();
  RUN_TEST(test_arms_at_ten_seconds);
  RUN_TEST(test_release_in_window_confirms_once);
  RUN_TEST(test_still_held_at_window_end_cancels);
  RUN_TEST(test_release_then_new_hold_rearms_after_cancel);
  RUN_TEST(test_bounce_in_armed_does_not_confirm);
  RUN_TEST(test_release_starting_in_window_confirms_after_it);
  RUN_TEST(test_release_after_window_is_cancel);
  RUN_TEST(test_wrap_cancel_exactly_at_window_end);
  RUN_TEST(test_wrap_release_confirms);
  return UNITY_END();
}
