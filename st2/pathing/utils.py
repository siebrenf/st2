import math

FUEL_WEIGHT = 0.65  # average FUEL purchase price/100
TIME_WEIGHT = 1  # credits/sec


def nav_score(
    distance,
    speed,
    mode="CRUISE",
    reactor="REACTOR_FISSION_I",
):
    score = (
        nav_fuel(distance, mode, reactor) * FUEL_WEIGHT
        + nav_time(distance, speed, mode, reactor) * TIME_WEIGHT
    )
    return score


def nav_fuel(
    distance,
    mode="CRUISE",
    reactor="REACTOR_FISSION_I",
):
    """return the amount of fuel required to navigate from one waypoint to another"""
    if reactor.startswith("REACTOR_SOLAR_I"):
        return 0

    multiplier = {
        "DRIFT": 0,
        "STEALTH": 1,
        "CRUISE": 1,
        "BURN": 2,
    }[mode]

    a = multiplier
    x = max(1, round(distance))
    return max(1, a * x)


def nav_fuel_inv(
    fuel: int,
    mode="CRUISE",
):
    """return the maximum distance covered by a given amount of fuel"""
    if fuel < 1:
        raise ValueError
    if mode == "DRIFT":
        return math.inf

    multiplier = {
        "DRIFT": 0,
        "STEALTH": 1,
        "CRUISE": 1,
        "BURN": 2,
    }[mode]
    return math.floor(fuel / multiplier)


def nav_time(
    distance,
    speed: int = 2,
    mode="CRUISE",
    reactor="REACTOR_FISSION_I",
):
    """return the time required to navigate from one waypoint to another"""
    if reactor.startswith("REACTOR_SOLAR_I"):
        multiplier = 25
    else:
        multiplier = {
            "DRIFT": 250,
            "STEALTH": 50,
            "CRUISE": 25,
            "BURN": 12.5,
        }[mode]

    a = multiplier / speed
    x = max(1, round(distance))
    b = 15
    return round(a * x + b)


def nav_cooldown(distance):
    """return the cooldown after jumping"""
    return round(distance + 60)


def action_cooldown(action, *args, **kwargs):
    """return the cooldown induced by the action"""
    cd = {
        "extract": 70,
        "siphon": 70,
        "jump": "nav_cooldown",
        # "refine"
        "survey": 70,
        "scan": 80,
    }[action]
    if cd == "nav_cooldown":
        cd = nav_cooldown(*args, **kwargs)  # lazy evaluation
    return cd
