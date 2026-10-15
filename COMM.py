"""Transports between the MCU and the DFMs.

UARTCOMM talks to V3 DFMs (and the V3 environmental monitor) on a shared, half-duplex RS-485
bus. The protocol is defined by the DFM firmware (DFMV3_V2/src/UART2.c, and DFMV3 before it):

  * Every frame is COBS encoded and terminated by a single 0x00 byte.
  * Requests start with [ID, command]. Simple requests are [ID, command, ID]. Instruction and
    linkage requests carry a payload followed by a 4-byte big-endian checksum (see Checksum32).
  * A DFM answers 5 ms (firmware 2.0.x) or 15 ms (older firmware) after a request, plus 2-3 ms
    to turn its driver on. After its last byte it keeps driving the bus for another 2-3 ms.
  * A status reply holds up to 60 56-byte status packets. The DFM keeps them until it is ACKed,
    so packets that were never ACKed are sent again with the next status request. Firmware 3.5.0
    and later also take a partial ACK: [ID, 0xF9, index of the last packet kept, checksum]. The
    DFM then sends again only the packets after that one.
  * Buffer resets, instructions and linkages are answered with [ID] (ACK) or [0xFE] (NACK).

I2CCOMM talks to legacy V2 DFMs over I2C.
"""
import platform
import sys
import time

import serial
import smbus2
from cobs import cobs

import Enums
from StatusPacket import Checksum32, V3_PACKET_SIZE

if "MCU" in platform.node():
    from gpiozero import LED

SERIAL_PORT = "/dev/ttyAMA0"  # PL011 UART on GPIO14/15
BAUD_RATE = 250000            # Firmware: PBCLK 40 MHz, BRGH=1, U2BRG=39
SEND_ENABLE_PIN = 17          # RS-485 driver enable

STATUS_REQUEST = 0xFC
LATEST_STATUS_REQUEST = 0xEA
VERSION_REQUEST = 0xEB
BUFFER_RESET_REQUEST = 0xFE
INSTRUCTION_REQUEST = 0xFD
LINKAGE_REQUEST = 0xFB
ACK = 0xFA
PARTIAL_ACK = 0xF9
# The partial ACK and the buffer-overflow error bit both arrived in 3.5.0 (no 2.0.2 ever shipped).
PARTIAL_ACK_FIRMWARE = (3, 5, 0)
# Firmware 4.0.0 and later NACK the 0xFD instruction and send 127-byte records: it takes PyMCU
# 4.0.0 to drive such a board, so this PyMCU leaves it alone and says so.
PARADIGM_FIRMWARE = (4, 0, 0)
# Firmware MAXPACKETS. A reply this full means more packets are waiting on the DFM.
MAX_STATUS_PACKETS = 60

ENVMON_ID = 99

BYTE_TIME = 10 / BAUD_RATE    # Start bit, 8 data bits, stop bit
DRIVER_SETUP_TIME = 0.002     # Driver is on this long before the first byte goes out
DRIVER_HOLD_TIME = 0.002      # Driver stays on at least this long after write() returns
TX_MARGIN = 0.0005            # Slack on top of the computed time on the wire
# A DFM turns its driver off two to three 1 ms ticks after its last byte. Driving the bus before
# then garbles what is sent, which in practice is the ACK that follows a status reply.
BUS_RELEASE_TIME = 0.003
# Buffer reset, instruction, linkage and version replies arrive within ~20 ms on all firmware.
REPLY_TIMEOUT = 0.03
# A full status reply (60 packets, ~3.4 kB) takes ~0.15 s on the wire and has been measured
# at over 0.3 s end to end. This bounds the whole frame, not the gap between bytes.
STATUS_TIMEOUT = 2.0
# The bus counts as quiet after this long without a byte. Longer than any gap inside a frame,
# including the delay before Linux hands received bytes over.
QUIET_TIME = 0.005

ACK_FRAME_SIZE = 5
VERSION_FRAME_SIZE = 50
STATUS_FRAME_SIZE = 5000

# Reported for firmware older than 2.0.0, which doesn't answer version requests.
LEGACY_VERSION = b"1.0.5"


def _Field(value, size):
    """Big-endian bytes of value truncated to size bytes, so -1 is sent as all 0xFF."""
    return (value & ((1 << (8 * size)) - 1)).to_bytes(size, "big")


def FirmwareVersionTuple(version):
    """(major, minor, patch) from a version string or bytes such as GetVersion returns, or ()
    if it isn't one, which compares below every real version."""
    try:
        if isinstance(version, bytes):
            version = version.decode("ascii")
        return tuple(int(p) for p in version.split("."))
    except (UnicodeDecodeError, ValueError, AttributeError):
        return ()


def SupportsPartialAck(version):
    """True if DFM firmware with this version takes partial ACKs."""
    return FirmwareVersionTuple(version) >= PARTIAL_ACK_FIRMWARE


def UsesParadigmFirmware(version):
    """True if DFM firmware with this version needs PyMCU 4.0.0 or later."""
    return FirmwareVersionTuple(version) >= PARADIGM_FIRMWARE


def InstructionPayload(instruction, timingSize):
    """Instruction packet body: dark, frequency, pulse width, decay, delay, max time on and the
    12 thresholds. Decay, delay and max time on are 2 bytes for firmware 1.0.5 and 4 from 2.0.0.

    A -1 threshold goes out as 0xFFFF, which the firmware treats as 'never on'.
    """
    payload = bytes((1 if instruction.theDarkState == Enums.DARKSTATE.ON else 0,))
    payload += _Field(instruction.frequency, 2) + _Field(instruction.pulseWidth, 2)
    for value in (instruction.decay, instruction.delay, instruction.maxTimeOn):
        payload += _Field(value, timingSize)
    for threshold in instruction.adjustedThresholds:
        payload += _Field(threshold, 2)
    return payload


class UARTCOMM:
    def __init__(self):
        self.thePort = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=STATUS_TIMEOUT)
        self.SendPin = LED(SEND_ENABLE_PIN)
        self.SendPin.off()
        self.busFreeTime = 0.0

    def Close(self):
        self.thePort.close()
        self.SendPin.close()

    #region Framing
    def _Send(self, packet):
        frame = cobs.encode(bytes(packet)) + b"\x00"
        wait = self.busFreeTime - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        self.SendPin.on()
        time.sleep(DRIVER_SETUP_TIME)
        self.thePort.write(frame)
        # write() returns once the bytes are queued, not once they are sent. A V2 instruction
        # frame (49 bytes) takes 1.96 ms, so the driver must stay on for the full transmit time
        # or the closing 0x00 can be cut off and the DFMs never see the frame end. The drain
        # returns at once unless transmission started late.
        time.sleep(max(DRIVER_HOLD_TIME, len(frame) * BYTE_TIME + TX_MARGIN))
        self.thePort.flush()
        self.SendPin.off()
        # Whatever arrived while we held the bus is noise, not a reply.
        self.thePort.reset_input_buffer()

    def _ReadFrame(self, maxBytes, timeout):
        """Read and decode one frame. Returns (COBSRESULT, payload)."""
        deadline = time.monotonic() + timeout
        while True:
            self.thePort.timeout = max(0.0, deadline - time.monotonic())
            raw = self.thePort.read_until(b"\x00", maxBytes)
            # No frame is empty, so a lone 0x00 is line noise. The reply may still follow it.
            if raw != b"\x00" or time.monotonic() >= deadline:
                break
        if not raw:
            return Enums.COBSRESULT.NOANSWER, b""
        self.busFreeTime = time.monotonic() + BUS_RELEASE_TIME
        if raw[-1] != 0 or len(raw) == 1:
            self._WaitForQuietBus()
            return Enums.COBSRESULT.INCOMPLETEPACKET, b""
        try:
            return Enums.COBSRESULT.OKAY, cobs.decode(raw[:-1])
        except cobs.DecodeError:
            self._WaitForQuietBus()
            return Enums.COBSRESULT.INCOMPLETEPACKET, b""

    def _WaitForQuietBus(self):
        """Discards input until the bus has been quiet for QUIET_TIME. Called when a read ends
        early: the rest of that frame may still be on the bus, and sending now would garble both."""
        deadline = time.monotonic() + STATUS_TIMEOUT
        self.thePort.timeout = QUIET_TIME
        # read() returns early only if all 4096 bytes arrive, which takes far longer than QUIET_TIME.
        while self.thePort.read(4096) and time.monotonic() < deadline:
            pass
        self.busFreeTime = time.monotonic() + BUS_RELEASE_TIME

    def _SendRequest(self, ID, command):
        self._Send((ID, command, ID))

    def _SendChecksummedRequest(self, ID, command, payload):
        packet = bytes((ID, command)) + payload
        self._Send(packet + Checksum32(packet).to_bytes(4, "big"))

    def _ReadAck(self, ID):
        result, reply = self._ReadFrame(ACK_FRAME_SIZE, REPLY_TIMEOUT)
        return result == Enums.COBSRESULT.OKAY and reply == bytes((ID,))
    #endregion

    #region Specific DFM calls
    def PollSlave(self, ID):
        if not self.RequestBufferReset(ID):
            return None
        return Enums.DFMTYPE.ENVMONV3 if ID == ENVMON_ID else Enums.DFMTYPE.PLETCHERV3

    def GetStatusPacket(self, ID, DFMType, latestOnly):
        """Returns (COBSRESULT, payload); the payload holds whole 56-byte status packets."""
        self._SendRequest(ID, LATEST_STATUS_REQUEST if latestOnly else STATUS_REQUEST)
        result, payload = self._ReadFrame(STATUS_FRAME_SIZE, STATUS_TIMEOUT)
        if result == Enums.COBSRESULT.OKAY and len(payload) % V3_PACKET_SIZE != 0:
            # Not whole packets, so a corrupt byte ended the frame early and the rest of the
            # reply may still be arriving.
            self._WaitForQuietBus()
        return result, payload

    def SendAck(self, ID):
        self._SendRequest(ID, ACK)

    def SendPartialAck(self, ID, lastIndex):
        """Acknowledges the packets of the last status reply up to and including the one
        numbered lastIndex. Only for firmware where SupportsPartialAck() is true."""
        self._SendChecksummedRequest(ID, PARTIAL_ACK, lastIndex.to_bytes(4, "big"))

    def GetVersion(self, ID):
        self._SendRequest(ID, VERSION_REQUEST)
        result, reply = self._ReadFrame(VERSION_FRAME_SIZE, REPLY_TIMEOUT)
        return reply if result == Enums.COBSRESULT.OKAY else LEGACY_VERSION

    def RequestBufferReset(self, ID):
        self._SendRequest(ID, BUFFER_RESET_REQUEST)
        result, reply = self._ReadFrame(ACK_FRAME_SIZE, REPLY_TIMEOUT)
        # Only the first byte is checked, as the environmental monitor answers this too.
        return result == Enums.COBSRESULT.OKAY and reply[:1] == bytes((ID,))

    def SendLinkage(self, ID, linkage):
        self._SendChecksummedRequest(ID, LINKAGE_REQUEST, bytes(linkage[i] for i in range(12)))
        return self._ReadAck(ID)

    def SendInstructionDFMV1_0_5(self, ID, anInstruction):
        self._SendChecksummedRequest(ID, INSTRUCTION_REQUEST, InstructionPayload(anInstruction, 2))
        return self._ReadAck(ID)

    def SendInstructionDFMV2_0(self, ID, anInstruction):
        self._SendChecksummedRequest(ID, INSTRUCTION_REQUEST, InstructionPayload(anInstruction, 4))
        return self._ReadAck(ID)
    #endregion


class I2CCOMM:
    BASE_ADDRESS = 0x50

    def __init__(self):
        self.i2cbus = smbus2.SMBus(1)

    def Close(self):
        self.i2cbus.close()

    def _Read(self, ID, numBytes):
        msg = smbus2.i2c_msg.read(I2CCOMM.BASE_ADDRESS + ID, numBytes)
        self.i2cbus.i2c_rdwr(msg)
        return list(msg)

    def _Write(self, ID, register, values):
        try:
            self.i2cbus.write_i2c_block_data(I2CCOMM.BASE_ADDRESS + ID, register, values)
            return True
        except Exception:
            return False

    def PollSlave(self, ID):
        try:
            data = self._Read(ID, 64)
        except Exception:
            return None
        # Sable boards send 52 bytes, so the end of a 64-byte read is empty.
        return Enums.DFMTYPE.SABLEV2 if sum(data[60:64]) == 0 else Enums.DFMTYPE.PLETCHERV2

    def GetStatusPacket(self, ID, DFMType, latestOnly):
        try:
            return Enums.COBSRESULT.OKAY, self._Read(ID, 52 if DFMType == Enums.DFMTYPE.SABLEV2 else 64)
        except Exception:
            return Enums.COBSRESULT.NOANSWER, []

    def SendDark(self, ID, darkstate):
        return self._Write(ID, 1, [darkstate])

    def SendOptoState(self, ID, os1, os2):
        return self._Write(ID, 2, [os1, os2])

    def SendFrequency(self, ID, freq):
        return self._Write(ID, 4, [freq])

    def SendPulseWidth(self, ID, pw):
        return self._Write(ID, 5, [pw])

    def SendAck(self, ID):
        pass


#region Testing
def ModuleTest(ID):
    """Hardware check, run on the MCU: python3 COMM.py <DFM ID>"""
    import datetime
    import Board
    import StatusPacket
    Board.BoardSetup()
    time.sleep(3)
    port = UARTCOMM()
    print("Version:", port.GetVersion(ID))
    print("Buffer reset:", port.RequestBufferReset(ID))
    for _ in range(10):
        time.sleep(1)
        result, payload = port.GetStatusPacket(ID, Enums.DFMTYPE.PLETCHERV3, False)
        if result != Enums.COBSRESULT.OKAY:
            print(result)
            continue
        packets = []
        for i in range(len(payload) // StatusPacket.V3_PACKET_SIZE):
            sp = StatusPacket.StatusPacket(i, ID, Enums.DFMTYPE.PLETCHERV3)
            sp.ProcessStatusPacket(payload, datetime.datetime.today(), i)
            packets.append(sp)
            print(sp.GetConsolePrintPacket())
        if packets and all(p.processResult == Enums.PROCESSEDPACKETRESULT.OKAY for p in packets):
            port.SendAck(ID)
    port.Close()


if __name__ == "__main__":
    ModuleTest(int(sys.argv[1]) if len(sys.argv) > 1 else 1)
#endregion
