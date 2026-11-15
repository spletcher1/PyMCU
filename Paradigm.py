"""Paradigms: the named recipes in a Program that decide when a Well's LED turns on.

The terms are defined in CONTEXT.md, and each Paradigm type's rule in docs/ProgramFormat.md.
DFM firmware 4.0.0 and later runs the rules itself (DFMV3_V2 src/LEDControl.c). Older firmware
gets the old decay, delay, max-time-on and pulse-width-flag settings, which encode the same
behavior for the types it can run.
"""
from enum import IntEnum


class ParadigmType(IntEnum):
    OPENLOOP = 0
    CLOSEDLOOP = 1
    FIXEDINTERVAL = 2
    NONFEEDING = 3
    PROGRESSIVERATIO = 4
    FIXEDRATIO = 5


TYPE_NAMES = {
    ParadigmType.OPENLOOP: "OpenLoop",
    ParadigmType.CLOSEDLOOP: "ClosedLoop",
    ParadigmType.FIXEDINTERVAL: "FixedInterval",
    ParadigmType.NONFEEDING: "NonFeeding",
    ParadigmType.PROGRESSIVERATIO: "ProgressiveRatio",
    ParadigmType.FIXEDRATIO: "FixedRatio",
}


class Series(IntEnum):
    ARITHMETIC = 0
    EXPONENTIAL = 1


SERIES_NAMES = {Series.ARITHMETIC: "Arithmetic", Series.EXPONENTIAL: "Exponential"}


class Counter(IntEnum):
    """What a ratio Paradigm's Requirement counts: milliseconds of Contact (the default, the
    progressive ratio of firmware before 4.0.0), or Events (feeding bouts)."""
    EVENTS = 0
    CONTACT = 1


COUNTER_NAMES = {Counter.EVENTS: "Events", Counter.CONTACT: "Contact"}
# A ratio Paradigm without a Counter setting counts Contact (docs/adr/0006).
DEFAULT_COUNTER = Counter.CONTACT

MAX_MS = 0xFFFFFFFF
MAX_COUNT = 0xFFFF
# With Counter: Contact the DFM counts contact in steps of this many ms (CONTACT_UNIT_MS in
# DFMV3_V2 src/LEDControl.h), so the Requirement settings are ms in multiples of it.
CONTACT_UNIT_MS = 10
MAX_CONTACT_MS = MAX_COUNT * CONTACT_UNIT_MS
CONTACT_COUNTER_FIRMWARE = (4, 0, 1)
# The Paradigm instruction's flag that makes the ratio types count Contact (LEDControl.h).
INSTRUCTION_COUNT_CONTACT = 0x02
# Firmware 1.0.5 (DFMV3 before 2.0.0) has 2-byte decay, delay and max time on.
MAX_MS_1_0_5 = 0xFFFF
DEFAULT_EVENT_GAP_MS = 100
# Old programs flagged non-feeding activation by adding this to OptoPW.
NONFEEDING_PW_FLAG = 0x8000

REQUIRED = object()
_LIGHT = [("Frequency", "frequency", 40), ("PulseWidth", "pulsewidth", 8)]
_EVENTS = [("EventGapMs", "gap", DEFAULT_EVENT_GAP_MS)]
_ACCLIMATION = [("Acclimation", "count", 0)]
_COUNTER = [("Counter", "counter", DEFAULT_COUNTER)]
# The settings each type takes, in display order: (name, kind, default). A "requirement" or
# "requirement1" (at least 1) setting is in ms of contact, or in Events with Counter: Events.
_SETTINGS = {
    ParadigmType.OPENLOOP: [],
    ParadigmType.CLOSEDLOOP: [("HoldMs", "ms", 0), ("MaxOnMs", "ms", 0)] + _EVENTS,
    ParadigmType.FIXEDINTERVAL: [("ActivationMs", "ms", REQUIRED), ("LockoutMs", "ms", REQUIRED)]
                                + _EVENTS + _ACCLIMATION,
    ParadigmType.NONFEEDING: [("OnDelayMs", "ms", 0), ("MaxOnMs", "ms", 0)],
    ParadigmType.PROGRESSIVERATIO: [("ActivationMs", "ms", REQUIRED)] + _COUNTER
                                   + [("Series", "series", Series.ARITHMETIC),
                                      ("FirstRequirement", "requirement1", 1), ("Step", "requirement", REQUIRED),
                                      ("Scale", "decimal", 5.0), ("Rate", "decimal", 0.2), ("Cap", "requirement1", MAX_COUNT)]
                                   + _EVENTS + _ACCLIMATION,
    ParadigmType.FIXEDRATIO: [("ActivationMs", "ms", REQUIRED)] + _COUNTER + [("Ratio", "requirement1", REQUIRED)]
                             + _EVENTS + _ACCLIMATION,
}
_SERIES_SETTINGS = {Series.ARITHMETIC: {"FirstRequirement", "Step"}, Series.EXPONENTIAL: {"Scale", "Rate"}}
_ALL_SETTINGS = {name.lower() for settings in _SETTINGS.values() for name, _, _ in settings} | {"frequency", "pulsewidth"}
_UNITS = {"ms": " ms", "gap": " ms", "frequency": " Hz", "pulsewidth": " ms"}
_REQUIREMENT_KINDS = ("requirement", "requirement1")
RESERVED_NAMES = {"dark", "lit", "on", "off"}


class ParadigmError(ValueError):
    """A Paradigm that can't be used. lineNumber is where in the Program, if known."""
    def __init__(self, message, lineNumber=None):
        super().__init__(message)
        self.lineNumber = lineNumber


def _ParseValue(kind, name, raw, lineNumber):
    raw = raw.strip()
    if kind == "series":
        for series, seriesName in SERIES_NAMES.items():
            if raw.lower() == seriesName.lower():
                return series
        raise ParadigmError("Series must be Arithmetic or Exponential, not '{}'".format(raw), lineNumber)
    if kind == "counter":
        for counter, counterName in COUNTER_NAMES.items():
            if raw.lower() == counterName.lower():
                return counter
        raise ParadigmError("Counter must be Events or Contact, not '{}'".format(raw), lineNumber)
    try:
        value = float(raw) if kind == "decimal" else int(raw)
    except ValueError:
        raise ParadigmError("{} must be a {}, not '{}'".format(name, "number" if kind == "decimal" else "whole number", raw),
                            lineNumber) from None
    # A Requirement setting's range depends on the Counter, checked once it is known (_CheckRequirement).
    low, high = {"ms": (0, MAX_MS), "gap": (0, MAX_COUNT), "count": (0, MAX_COUNT), "count1": (1, MAX_COUNT),
                 "requirement": (0, MAX_CONTACT_MS), "requirement1": (1, MAX_CONTACT_MS),
                 "frequency": (1, 500), "pulsewidth": (1, 1000), "decimal": (0.001, 1000000)}[kind]
    if not low <= value <= high:
        raise ParadigmError("{} must be from {} to {}, not {}".format(name, low, high, raw), lineNumber)
    return value


def _CheckRequirement(kind, name, value, counter, lineNumber):
    """A Requirement setting is ms of contact that the DFM counts in steps of CONTACT_UNIT_MS, or a
    number of Events."""
    if counter == Counter.CONTACT:
        low = 0 if kind == "requirement" else CONTACT_UNIT_MS
        if value % CONTACT_UNIT_MS:
            # Most likely a Program written for Events, from before Contact was the default.
            raise ParadigmError("{} is in ms of contact (Counter: Contact, the default) and must be a multiple of {}, "
                                "not {}. To count feeding bouts instead, add 'Counter: Events'".format(
                                    name, CONTACT_UNIT_MS, value), lineNumber)
        if not low <= value <= MAX_CONTACT_MS:
            raise ParadigmError("{} must be from {} to {} ms, not {}".format(name, low, MAX_CONTACT_MS, value), lineNumber)
    elif value > MAX_COUNT:
        raise ParadigmError("{} must be from {} to {}, not {}".format(name, 0 if kind == "requirement" else 1, MAX_COUNT, value),
                            lineNumber)


class Paradigm:
    def __init__(self, name, paradigmType, settings=None):
        """settings maps setting names to values; missing ones take their defaults (no checks)."""
        self.name = name
        self.type = paradigmType
        self.settings = {}
        settings = settings or {}
        isContact = settings.get("Counter", DEFAULT_COUNTER) == Counter.CONTACT
        for settingName, _, default in _LIGHT + _SETTINGS[paradigmType]:
            # With Counter: Contact the defaults are the smallest and largest ms the DFM counts.
            if settingName == "Cap" and isContact:
                default = MAX_CONTACT_MS
            elif settingName == "FirstRequirement" and isContact:
                default = CONTACT_UNIT_MS
            value = settings.get(settingName, default)
            self.settings[settingName] = 0 if value is REQUIRED else value

    def Get(self, name):
        return self.settings[name]

    @property
    def frequency(self):
        return self.settings["Frequency"]

    @property
    def pulseWidth(self):
        return self.settings["PulseWidth"]

    @property
    def eventGapMs(self):
        return self.settings.get("EventGapMs", DEFAULT_EVENT_GAP_MS)

    @property
    def acclimation(self):
        return self.settings.get("Acclimation", 0)

    @property
    def typeName(self):
        return TYPE_NAMES[self.type]

    def IsRatioType(self):
        return self.type in (ParadigmType.PROGRESSIVERATIO, ParadigmType.FIXEDRATIO)

    @property
    def countsContact(self):
        """A ratio Paradigm whose Requirement is ms of contact rather than Events (firmware 4.0.1).
        Ratio Paradigms count Contact unless they say Counter: Events; other types have no Counter."""
        return self.IsRatioType() and self.settings.get("Counter", DEFAULT_COUNTER) == Counter.CONTACT

    #region Building
    @classmethod
    def FromSettings(cls, name, items, sectionLine):
        """A Paradigm from a [Paradigm NAME] section. items are (key, value, lineNumber)."""
        if not name or not name[0].isalpha() or not all(c.isalnum() or c in "_-." for c in name):
            raise ParadigmError("Paradigm names start with a letter and use only letters, digits, '_', '-' "
                                "and '.': '{}'".format(name), sectionLine)
        if name.lower() in RESERVED_NAMES:
            raise ParadigmError("'{}' can't be a Paradigm name".format(name), sectionLine)
        typeItems = [item for item in items if item[0].lower() == "type"]
        if not typeItems:
            raise ParadigmError("[Paradigm {}] needs a Type".format(name), sectionLine)
        typeName = typeItems[-1][1].strip()
        paradigmType = next((t for t, n in TYPE_NAMES.items() if n.lower() == typeName.lower()), None)
        if paradigmType is None:
            raise ParadigmError("Unknown Type '{}'. Types: {}".format(typeName, ", ".join(TYPE_NAMES.values())),
                                typeItems[-1][2])

        allowed = {settingName.lower(): (settingName, kind) for settingName, kind, _ in _LIGHT + _SETTINGS[paradigmType]}
        values, lines = {}, {}
        for key, raw, lineNumber in items:
            if key.lower() == "type":
                continue
            if key.lower() not in allowed:
                if key.lower() in _ALL_SETTINGS:
                    raise ParadigmError("{} Paradigms don't use {}".format(TYPE_NAMES[paradigmType], key), lineNumber)
                raise ParadigmError("Unknown setting '{}'".format(key), lineNumber)
            settingName, kind = allowed[key.lower()]
            if settingName in values:
                raise ParadigmError("{} is set twice".format(settingName), lineNumber)
            values[settingName] = _ParseValue(kind, settingName, raw, lineNumber)
            lines[settingName] = lineNumber

        counter = values.get("Counter", DEFAULT_COUNTER)
        for settingName, kind, _ in _SETTINGS[paradigmType]:
            if kind in _REQUIREMENT_KINDS and settingName in values:
                _CheckRequirement(kind, settingName, values[settingName], counter, lines[settingName])
        series = values.get("Series", Series.ARITHMETIC)
        if paradigmType == ParadigmType.PROGRESSIVERATIO:
            for other, seriesSettings in _SERIES_SETTINGS.items():
                for settingName in seriesSettings:
                    if other != series and settingName in values:
                        raise ParadigmError("{} is only for the {} Series".format(settingName, SERIES_NAMES[other]),
                                            lines[settingName])
            # Scale's default of 5 is the Richardson-Roberts series in Events; as ms of contact it
            # would be next to nothing, so with Contact it has to be given.
            if series == Series.EXPONENTIAL and counter == Counter.CONTACT and "Scale" not in values:
                raise ParadigmError("[Paradigm {}]: with Counter: Contact (the default), Scale is ms of contact and "
                                    "has no default; give it, or add 'Counter: Events'".format(name), sectionLine)
        for settingName, _, default in _SETTINGS[paradigmType]:
            if default is REQUIRED and settingName not in values:
                if paradigmType == ParadigmType.PROGRESSIVERATIO and settingName not in _SERIES_SETTINGS[series] \
                        and settingName != "ActivationMs":
                    continue
                raise ParadigmError("[Paradigm {}] needs {}".format(name, settingName), sectionLine)

        paradigm = cls(name, paradigmType, values)
        if paradigm.pulseWidth * paradigm.frequency >= 1000:
            raise ParadigmError("PulseWidth must be shorter than one period ({} ms at {} Hz)".format(
                1000 // paradigm.frequency, paradigm.frequency), lines.get("PulseWidth", sectionLine))
        return paradigm

    @classmethod
    def Legacy(cls, frequency, pulseWidth, decay, delay, maxTimeOn):
        """The Paradigm an old-style setting combination meant. Old progressive ratio and acclimation
        bits are refused: they counted milliseconds of contact (docs/adr/0001)."""
        if frequency > 500:
            raise ParadigmError("OptoFrequency above 500 is the old way of setting event-based acclimation. "
                                "Rewrite the program with a [Paradigm] section that sets Acclimation "
                                "(see docs/ProgramFormat.md).")
        if frequency < 1:
            raise ParadigmError("OptoFrequency must be from 1 to 500")
        if decay < 0 or delay < 0:
            raise ParadigmError("OptoDecay and OptoDelay can't be negative")
        # -1 was used for "no limit".
        maxTimeOn = max(maxTimeOn, 0)
        light = {"Frequency": frequency}
        if pulseWidth > 30000:
            if decay <= 0:
                raise ParadigmError("OptoPW above 32768 (non-feeding activation) needs OptoDecay above 0")
            paradigmType = ParadigmType.NONFEEDING
            settings = dict(light, PulseWidth=pulseWidth & 0x3FF, OnDelayMs=delay, MaxOnMs=decay)
        elif pulseWidth < 1:
            raise ParadigmError("OptoPW must be at least 1")
        elif delay == 0:
            paradigmType = ParadigmType.CLOSEDLOOP
            settings = dict(light, PulseWidth=pulseWidth, HoldMs=decay, MaxOnMs=maxTimeOn)
        elif maxTimeOn == 0:
            paradigmType = ParadigmType.FIXEDINTERVAL
            settings = dict(light, PulseWidth=pulseWidth, ActivationMs=decay, LockoutMs=delay)
        else:
            raise ParadigmError("Old progressive ratio settings (OptoDelay and MaxTimeOn both above 0) can't be "
                                "converted exactly. Rewrite the program with a [Paradigm] section of Type "
                                "ProgressiveRatio, which counts ms of contact as they did, with FirstRequirement "
                                "and Step from OptoDelay (see 'Rewriting progressive ratio' in docs/ProgramFormat.md).")
        # e.g. ClosedLoop-40Hz-8ms-Hold500-MaxOn0. Equal old settings give equal names, and so the
        # same Paradigm.
        name = "{}-{}Hz-{}ms".format(TYPE_NAMES[paradigmType], settings["Frequency"], settings["PulseWidth"]) + "".join(
            "-{}{}".format(key.replace("Ms", ""), value) for key, value in settings.items()
            if key not in ("Frequency", "PulseWidth"))
        return cls(name, paradigmType, settings)

    @classmethod
    def Idle(cls):
        """Every Well's LED off: used before a Program runs, with all thresholds Off."""
        return cls("Idle", ParadigmType.CLOSEDLOOP)
    #endregion

    #region Sending to the DFM
    def SettingsWords(self):
        """The 5 type-dependent numbers of the 4.0.0 instruction (LEDControl.h). With Counter:
        Contact the Requirement settings go in the DFM's units of CONTACT_UNIT_MS."""
        g = self.Get
        unit = CONTACT_UNIT_MS if self.countsContact else 1
        def Requirement(name):
            return g(name) // unit
        if self.type == ParadigmType.CLOSEDLOOP:
            words = [g("HoldMs"), g("MaxOnMs")]
        elif self.type == ParadigmType.FIXEDINTERVAL:
            words = [g("ActivationMs"), g("LockoutMs")]
        elif self.type == ParadigmType.NONFEEDING:
            words = [g("OnDelayMs"), g("MaxOnMs")]
        elif self.type == ParadigmType.PROGRESSIVERATIO:
            if g("Series") == Series.EXPONENTIAL:
                words = [g("ActivationMs"), Series.EXPONENTIAL, round(g("Scale") * 1000 / unit), round(g("Rate") * 1000),
                         Requirement("Cap")]
            else:
                words = [g("ActivationMs"), Series.ARITHMETIC, Requirement("FirstRequirement"), Requirement("Step"),
                         Requirement("Cap")]
        elif self.type == ParadigmType.FIXEDRATIO:
            words = [g("ActivationMs"), Requirement("Ratio")]
        else:
            words = []
        return [int(w) for w in words] + [0] * (5 - len(words))

    def InstructionFlags(self):
        """The flag bits of the 4.0.0 instruction that come from the Paradigm (LEDControl.h)."""
        return INSTRUCTION_COUNT_CONTACT if self.countsContact else 0

    def FirmwareNeeded(self, version=None):
        """Why DFM firmware with this version (a tuple such as (1, 0, 5), as COMM.FirmwareVersionTuple
        gives it) can't run this Paradigm, naming the firmware it needs, or None if it can. Ratio
        types and Acclimation need 4.0.0, and Counter: Contact, their default, 4.0.1: 4.0.0 would
        ignore it and count Events. Firmware 1.0.5, the only one below 2.0.0, also doesn't know the
        NonFeeding type (it would run fixed interval instead, with no warning) and its 2-byte times
        stop at 65535 ms. Without a version (a V2 DFM), only what needs 4.0.0 or later is reported."""
        if self.countsContact and (version is None or version < CONTACT_COUNTER_FIRMWARE):
            return ("counting contact (Counter: Contact, the {} default) needs firmware {}.{}.{}; with "
                    "'Counter: Events' it runs on 4.0.0").format(self.typeName, *CONTACT_COUNTER_FIRMWARE)
        if version is None or version < (4, 0, 0):
            if self.IsRatioType():
                return "the {} Paradigm type needs firmware 4.0.0".format(self.typeName)
            if self.acclimation > 0:
                return "Acclimation needs firmware 4.0.0"
        if version is not None and version < (2, 0, 0):
            if self.type == ParadigmType.NONFEEDING:
                return "the NonFeeding Paradigm type needs firmware 2.0.0"
            if max(self.LegacyFields()[2:]) > MAX_MS_1_0_5:
                return "times above 65535 ms need firmware 2.0.0"
        return None

    def LegacyFields(self):
        """(frequency, pulse width, decay, delay, max time on) for firmware before 4.0.0 and V2 DFMs."""
        g = self.Get
        if self.type == ParadigmType.CLOSEDLOOP:
            return self.frequency, self.pulseWidth, g("HoldMs"), 0, g("MaxOnMs")
        if self.type == ParadigmType.FIXEDINTERVAL:
            return self.frequency, self.pulseWidth, g("ActivationMs"), g("LockoutMs"), 0
        if self.type == ParadigmType.NONFEEDING:
            # Old firmware needs a decay above 0 for non-feeding activation; 0 meant no limit here.
            return (self.frequency, self.pulseWidth | NONFEEDING_PW_FLAG, g("MaxOnMs") or MAX_MS, g("OnDelayMs"), 0)
        # OpenLoop: thresholds become "always on". Ratio types can't be sent (FirmwareNeeded).
        return self.frequency, self.pulseWidth, 0, 0, 0
    #endregion

    def Describe(self):
        parts = []
        for settingName, kind, _ in _LIGHT + _SETTINGS[self.type]:
            if self.type == ParadigmType.PROGRESSIVERATIO:
                other = Series.EXPONENTIAL if self.Get("Series") == Series.ARITHMETIC else Series.ARITHMETIC
                if settingName in _SERIES_SETTINGS[other]:
                    continue
            # Counter is always shown: Program.txt written before 4.0.1 has none and counted Events,
            # so a reader can't take a missing Counter as the default.
            value = self.settings[settingName]
            unit = _UNITS.get(kind, "")
            if self.countsContact and (kind in _REQUIREMENT_KINDS or settingName == "Scale"):
                unit = " ms"
            if kind == "series":
                value = SERIES_NAMES[value]
            elif kind == "counter":
                value = COUNTER_NAMES[value]
            elif kind == "decimal":
                value = "{:g}".format(value)
            parts.append("{} {}{}".format(settingName, value, unit))
        return "{} ({}): {}".format(self.name, self.typeName, ", ".join(parts))

    def __str__(self):
        return self.name
