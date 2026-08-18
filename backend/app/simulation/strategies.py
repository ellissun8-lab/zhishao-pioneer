from enum import StrEnum


class Strategy(StrEnum):
    NONE = "none"
    WARN = "warn"
    GUIDE_LEAVE = "guide_leave"
    INTERVENE = "intervene"


STRATEGY_EFFECTS = {
    Strategy.NONE: {"risk_factor": 1.04, "leave_probability": 0.05, "cost": 0},
    Strategy.WARN: {"risk_factor": 0.68, "leave_probability": 0.45, "cost": 1},
    Strategy.GUIDE_LEAVE: {"risk_factor": 0.41, "leave_probability": 0.82, "cost": 3},
    Strategy.INTERVENE: {"risk_factor": 0.16, "leave_probability": 1.0, "cost": 8},
}

