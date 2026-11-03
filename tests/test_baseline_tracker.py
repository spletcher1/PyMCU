"""The Tracked baseline under Baseline: Adaptive (docs/adaptive-baseline-plan.md, Rules 2-6),
on synthetic records."""
import support  # noqa: F401  (must come first)

import random
import unittest

import BaselineTracker as BT

PER_MINUTE = BT.RECORDS_PER_MINUTE


def Run(tracker, signal, minutes, wells=None):
    """Feeds `minutes` minutes of records, signal(minute from 0, record in minute) giving every
    Well's value (or wells(...) giving all 12). Acts on each check as DFM.py does. Returns the
    minutes at which an update would have been sent and the Baselines in force after each."""
    inForce = list(tracker.start)
    updates = []
    index = 0
    for m in range(minutes):
        for r in range(PER_MINUTE):
            index += 1
            values = wells(m, r) if wells else [signal(m, r)] * BT.WELLS
            for done in tracker.AddRecord(index, values):
                if done.isCheck and tracker.NeedsUpdate(inForce):
                    inForce = tracker.Rounded()
                    updates.append((done.number, list(inForce)))
    return updates


class Floor(unittest.TestCase):
    def test_floor_is_the_value_at_position_29_of_300(self):
        values = list(range(1000, 1300))
        random.Random(3).shuffle(values)
        self.assertEqual(BT.Floor(values), 1029)

    def test_rounding_is_half_up(self):
        self.assertEqual([BT.RoundCount(v) for v in (2.5, 3.5, 2.49)], [3, 4, 2])

    def test_minutes_from_indexes(self):
        self.assertEqual([BT.MinuteOf(i) for i in (1, 300, 301, 3000, 3001)], [1, 1, 2, 10, 11])


class Tracking(unittest.TestCase):
    def test_flat_noisy_signal_sends_nothing(self):
        noise = random.Random(1)
        t = BT.BaselineTracker([20] * 12)
        self.assertEqual(Run(t, lambda m, r: 20 + noise.randint(-3, 3), 24 * 60), [])

    def test_slow_ramp_is_followed(self):
        # 4 counts an hour, slower than the 5-count limit.
        t = BT.BaselineTracker([10] * 12)
        updates = Run(t, lambda m, r: int(10 + 4 * (m + r / PER_MINUTE) / 60), 6 * 60)
        self.assertLessEqual(abs(t.Rounded()[0] - (10 + 4 * 6)), 1)
        # The first update: once the ramp has risen 10, at the next 10-minute check.
        first = updates[0][0]
        self.assertEqual(first % BT.CHECK_MINUTES, 0)
        self.assertTrue(150 <= first <= 170, first)
        self.assertGreaterEqual(updates[0][1][0], 20)

    def test_long_plateau_is_not_absorbed(self):
        # A fly on the food for 76 minutes, 100 counts above a floor of 10.
        t = BT.BaselineTracker([10] * 12)
        updates = Run(t, lambda m, r: 110 if 60 <= m < 136 else 10, 136)
        self.assertEqual(updates, [])
        self.assertLessEqual(t.tracked[0] - 10, 76 / 60 * BT.DEFAULT_RATE_PER_HOUR + 1)
        risen = t.tracked[0]
        # It comes back at the same rate once the fly leaves.
        Run2 = BT.BaselineTracker([10] * 12)
        Run2.tracked = [risen] * 12
        Run(Run2, lambda m, r: 10, 30)
        self.assertAlmostEqual(Run2.tracked[0], risen - 29 * BT.DEFAULT_RATE_PER_HOUR / 60, places=6)

    def test_a_drop_is_followed_slowly(self):
        t = BT.BaselineTracker([40] * 12)
        Run(t, lambda m, r: 40 if m < 30 else 10, 90)
        # 59 minutes below at 5 counts an hour, not straight down to 10.
        self.assertAlmostEqual(t.tracked[0], 40 - 59 * 5 / 60, places=6)

    def test_a_step_stops_at_the_cap_once(self):
        t = BT.BaselineTracker([10] * 12, ratePerHour=60, cap=50)
        events = []
        index = 0
        for m in range(70):
            for r in range(PER_MINUTE):
                index += 1
                values = [210] + [10] * 11
                events += [c for done in t.AddRecord(index, values) for c in done.newlyCapped]
        # 60 counts an hour reaches the 50-count cap in 50 minutes, reported once.
        self.assertEqual(events, [(0, 1)])
        self.assertEqual(t.tracked[0], 60)
        self.assertEqual(t.tracked[1], 10)

    def test_the_cap_holds_below_too(self):
        t = BT.BaselineTracker([80] * 12, ratePerHour=600, cap=20)
        Run(t, lambda m, r: 0, 10)
        self.assertEqual(t.Rounded(), [60] * 12)
        self.assertTrue(all(t.isCapped))


class Minutes(unittest.TestCase):
    def Feed(self, t, minute, count, value):
        first = (minute - 1) * PER_MINUTE + 1
        out = []
        for i in range(first, first + count):
            out += t.AddRecord(i, [value] * 12)
        return out

    def test_a_short_minute_is_skipped(self):
        t = BT.BaselineTracker([10] * 12, ratePerHour=60)
        self.Feed(t, 1, 149, 100)
        done = self.Feed(t, 2, 1, 10)
        self.assertEqual((done[0].number, done[0].used), (1, False))
        self.assertEqual(t.tracked[0], 10)
        self.Feed(t, 2, 149, 100)   # 150 records in minute 2 with the one above
        done = self.Feed(t, 3, 1, 10)
        self.assertEqual((done[0].number, done[0].used), (2, True))
        self.assertEqual(t.tracked[0], 11)

    def test_a_gap_doesnt_skip_a_check(self):
        t = BT.BaselineTracker([10] * 12)
        for m in range(1, 10):
            self.Feed(t, m, PER_MINUTE, 10)
        # Minutes 10 and 11 lost, as after a restart; the check for minute 10 still happens.
        done = self.Feed(t, 12, 1, 10)
        self.assertEqual((done[0].number, done[0].isCheck), (9, True))
        done = self.Feed(t, 13, 1, 10)
        self.assertFalse(done[0].isCheck)

    def test_an_older_record_changes_nothing(self):
        t = BT.BaselineTracker([10] * 12)
        self.Feed(t, 3, 10, 10)
        self.assertEqual(t.AddRecord(5, [500] * 12), [])
        self.assertEqual(len(t.values[0]), 10)

    def test_needs_update_at_d(self):
        t = BT.BaselineTracker([10] * 12)
        t.tracked = [19.4] + [10.0] * 11
        self.assertFalse(t.NeedsUpdate([10] * 12))
        t.tracked = [19.5] + [10.0] * 11
        self.assertTrue(t.NeedsUpdate([10] * 12))
        t.tracked = [10.0] * 11 + [0.0]
        self.assertTrue(t.NeedsUpdate([10] * 12))


if __name__ == "__main__":
    unittest.main()
