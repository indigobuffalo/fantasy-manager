from enum import Enum


class PositionType(Enum):
    SKATER = "SK"
    GOALIE = "G"


class Position(Enum):
    C = "C"
    LW = "LW"
    RW = "RW"
    D = "D"
    G = "G"
    UTIL = "UTIL"
    BN = "BN"
    IR = "IR"
    IR_PLUS = "IR+"
