"""Each Well's Tracked baseline under `Baseline: Adaptive` (docs/adaptive-baseline-plan.md, Rules).

The tracker sees every record of a recording. For each minute of records it takes each Well's Floor,
the 10th percentile of that minute's values, and moves the Well's Tracked baseline toward it by at
most the rate limit, the same up and down, within a cap around the Starting baseline. A long contact
lifts the Floor but can only drag the baseline at the rate limit, so it can't cut off the light.

Nothing here talks to a DFM. DFM.py decides what to send from the minutes this reports."""
import collections
import math

WELLS = 12
# Wells 1-12 by name, for messages.
WELL_NAMES = ["{}{}".format(row, side) for row in range(1, 7) for side in "AB"]
# Records in a minute of the recording: one every 200 ms.
RECORDS_PER_MINUTE = 300
# A minute with fewer records than this (lost records, a restart) is skipped.
MIN_RECORDS_PER_MINUTE = 150
# The Floor is this fraction of the way up a minute's sorted values.
FLOOR_FRACTION = 0.1
# D: a Well's Tracked baseline must be this far from the Baseline in force before PyMCU sends it.
UPDATE_STEP = 10
# T: how often, in minutes of the recording, PyMCU checks whether to send an update.
CHECK_MINUTES = 10
# Program defaults for BaselineRatePerHour and BaselineCapCounts.
DEFAULT_RATE_PER_HOUR = 5.0
DEFAULT_CAP = 50
# The smallest cap a Program may set: a smaller one could never be sent.
MIN_CAP = UPDATE_STEP

# A minute the tracker has finished with: its number (from 1), whether it had enough records to be
# used, whether an update check is due after it (a multiple of CHECK_MINUTES was reached), and the
# Wells, from 0, that reached the cap for the first time in it, as (well, +1 above or -1 below).
Minute = collections.namedtuple("Minute", "number used isCheck newlyCapped")


def Floor(values):
    """The value at position floor(0.1 x (n - 1)) of the sorted values, counting from 0."""
    ordered = sorted(values)
    return ordered[int(FLOOR_FRACTION * (len(ordered) - 1))]


def RoundCount(value):
    """Half away from zero for the positive values a baseline has (Python's round() goes to even)."""
    return int(math.floor(value + 0.5))


def MinuteOf(index):
    """The minute of the recording, from 1, that the record with this Index (from 1) belongs to."""
    return (index - 1) // RECORDS_PER_MINUTE + 1


class BaselineTracker:
    def __init__(self, start, ratePerHour=DEFAULT_RATE_PER_HOUR, cap=DEFAULT_CAP):
        """start: the 12 Starting baselines. ratePerHour: the most a baseline moves in an hour, either
        way. cap: how far a baseline may move from its start."""
        if len(start) != WELLS:
            raise ValueError("A tracker needs {} Starting baselines, not {}".format(WELLS, len(start)))
        self.start = [int(v) for v in start]
        self.tracked = [float(v) for v in start]
        self.ratePerHour = float(ratePerHour)
        self.cap = int(cap)
        self.minute = None
        self.values = [[] for _ in range(WELLS)]
        self.isCapped = [False] * WELLS

    def Rounded(self):
        """The Tracked baselines as the whole counts a Threshold is built from."""
        return [RoundCount(t) for t in self.tracked]

    def AddRecord(self, index, values):
        """Adds one record: its Index in the data file (from 1, after any restart offset) and its 12
        Well values. Returns the minutes it finished, usually none and at most one at a time."""
        minute = MinuteOf(index)
        if self.minute is None:
            self.minute = minute
        elif minute < self.minute:
            # Indexes only go up within a recording; an older record changes nothing.
            return []
        done = []
        if minute > self.minute:
            done.append(self._FinishMinute(minute))
            self.minute = minute
        for w in range(WELLS):
            self.values[w].append(values[w])
        return done

    def _FinishMinute(self, nextMinute):
        number = self.minute
        used = len(self.values[0]) >= MIN_RECORDS_PER_MINUTE
        capped = []
        if used:
            step = self.ratePerHour / 60.0
            for w in range(WELLS):
                target = Floor(self.values[w])
                moved = self.tracked[w] + max(-step, min(step, target - self.tracked[w]))
                low, high = self.start[w] - self.cap, self.start[w] + self.cap
                if moved > high or moved < low:
                    moved = high if moved > high else low
                    if not self.isCapped[w]:
                        self.isCapped[w] = True
                        capped.append((w, 1 if moved == high else -1))
                self.tracked[w] = moved
        self.values = [[] for _ in range(WELLS)]
        # A check is due if a multiple of CHECK_MINUTES lies between this minute and the one the new
        # record starts, so a gap in the records can't skip one.
        isCheck = any(m % CHECK_MINUTES == 0 for m in range(number, nextMinute))
        return Minute(number, used, isCheck, capped)

    def NeedsUpdate(self, inForce):
        """True if any Well's Tracked baseline is at least D from the Baseline in force."""
        return any(abs(t - f) >= UPDATE_STEP for t, f in zip(self.Rounded(), inForce))
