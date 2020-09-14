from enum import Enum

class STATUSREQUESTTYPE(Enum):
    LATESTONLY=1
    NORMAL=2

class COMMANDTYPE(Enum):
    FINDDFM=1
    BUFFER_RESET=2
    LINKAGE=3
    INSTRUCTION=4
    STOP_READING=5
    SEND_DARK=6
    SEND_FREQ=7
    SEND_PW=8
    SEND_OPTOSTATE=9
    PAUSE_READING=10
    RESUME_READING=11
    RESET_COUNTER=12
    CLEAR_DATAQ=13
    CLEAR_DATAMESSQ=14
    SET_VERBOSE=15
    CLEAR_VERBOSE=16
    SET_STARTTIME=17
    SET_REFRESHRATE=18
    SET_FOCAL_DFM=19
    SET_GET_LATESTSTATUS=20
    SET_GET_NORMALSTATUS=21
    FIND_DFM=22

class COMMTYPE(Enum):
    UART=1
    I2C=2

class CURRENTSTATUS(Enum):
    READING=1
    RECORDING=2
    ERROR=3
    MISSING=4
    UNDEFINED=5

class PASTSTATUS(Enum):
    ALLCLEAR=1
    PASTERROR=2
    
class REPORTEDERRORSTATUS(Enum):
    CURRENT=1
    PAST=2
    NEVER=3

class PROCESSEDPACKETRESULT(Enum):
    WRONGID=1
    CHECKSUMERROR=2
    WRONGNUMBYTES=3
    NOANSWER=4
    INCOMPLETEPACKET=5
    OKAY=6

class COBSRESULT(Enum):
    NOANSWER=1
    INCOMPLETEPACKET=2
    OKAY=3


class INSTRUCTIONSETTYPE(Enum):
    LINEAR=1
    REPEATING=2
    CIRCADIAN=3
    CONSTANT=4

class DARKSTATE(Enum):
    OFF=0
    ON=1

class MESSAGETYPE(Enum):
    NOTICE=1
    WARNING=2
    ERROR=3

class OPTOTYPE(Enum):
    ALLON=1
    ADAPTIVE=2

class DFMTYPE(Enum):
    PLETCHERV2=1
    SABLEV2=2
    PLETCHERV3=3