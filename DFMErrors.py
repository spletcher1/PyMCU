import Enums

# What the eight error checkboxes show, in bit order (bit 0 first): (label, description, bits
# it reports), or None to hide the box. The DFM page lays them out with bit n beside bit n+4.

# Environmental monitors and V2 (I2C) DFMs: the labels the page has always shown, one bit each.
DEFAULT_ERROR_DISPLAY = [
    ("I2C", "", (0,)), ("ID Ack", "", (1,)), ("P Type", "", (2,)), ("DMA Tx", "", (3,)),
    ("DMA Rx", "", (4,)), ("P Size", "", (5,)), ("AI Int", "", (6,)), ("O Int", "", (7,)),
]

# Bits 2-7 mean the same in every V3 firmware since April 2021 (DFMV3 and DFMV3_V2).
_V3_COMMON = [
    ("P Type", "A request had an unknown command. Firmware older than 2.0.0 also sets this when asked for its version.", (2,)),
    ("DMA Tx", "UART transmit DMA error.", (3,)),
    ("DMA Rx", "UART receive DMA error. From firmware 2.0.2, also a receive overrun, after which the DFM recovers.", (4,)),
    ("P Size", "A request had the wrong length.", (5,)),
    ("AI Int", "New ADC readings arrived before the last ones were used.", (6,)),
    ("O Int", "The 1 ms timer ticked before the main loop handled the last tick.", (7,)),
]

# Firmware before 2.0.2 reports a missing ACK on bit 1 (DFMV3, early DFMV3_V2 2.0.0 builds) or
# bit 0 (later DFMV3_V2), and the version string doesn't say which. Nothing else sets bits 0 or 1
# in a way that reaches the MCU, so both show as "No Ack".
V3_ERROR_DISPLAY_BEFORE_2_0_2 = [
    ("No Ack", "The MCU didn't acknowledge the last status packets, so the DFM sent them again.", (0, 1)),
    None,
] + _V3_COMMON

# DFMV3_V2 2.0.2 and later. Bit 1 reports that the status buffer overflowed.
OVERFLOW_MASK = 0x02
V3_ERROR_DISPLAY = [
    ("No Ack", "The MCU didn't acknowledge the last status packets, so the DFM sent them again.", (0,)),
    ("Overflow", "The DFM's status buffer filled up and its oldest packets were overwritten.", (1,)),
] + _V3_COMMON


def V3ErrorDisplay(version):
    """Error checkboxes for a V3 DFM running this firmware version."""
    try:
        parts = tuple(int(p) for p in version.split("."))
    except ValueError:
        parts = ()
    return V3_ERROR_DISPLAY if parts >= (2, 0, 2) else V3_ERROR_DISPLAY_BEFORE_2_0_2


class DFMErrors:
    """Tracks each bit of a DFM's error byte as never, currently or previously set."""
    def __init__(self, display=DEFAULT_ERROR_DISPLAY):
        self.display = display
        self.ClearErrors()

    def GetStatus(self, bits):
        """The most recent status of any of the bits: CURRENT, else PAST, else NEVER."""
        statuses = [self.currentErrorStatuses[bit] for bit in bits]
        for status in (Enums.REPORTEDERRORSTATUS.CURRENT, Enums.REPORTEDERRORSTATUS.PAST):
            if status in statuses:
                return status
        return Enums.REPORTEDERRORSTATUS.NEVER

    def ClearErrors(self):
        self.currentErrorByte=0x00
        self.currentErrorStatuses=[Enums.REPORTEDERRORSTATUS.NEVER]*8

    def UpdateErrors(self,errorByte):
        self.currentErrorByte=errorByte
        for bit in range(0,8):
            if(errorByte & (1<<bit)):
                self.currentErrorStatuses[bit]=Enums.REPORTEDERRORSTATUS.CURRENT
            elif self.currentErrorStatuses[bit]==Enums.REPORTEDERRORSTATUS.CURRENT:
                self.currentErrorStatuses[bit]=Enums.REPORTEDERRORSTATUS.PAST
