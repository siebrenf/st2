from spacepyrates.caching import cache
from spacepyrates.data.gathering import log_cooldown, log_navigate
from spacepyrates.logging import logger
from spacepyrates.request import request

# def nav(self):
#     """update nav data with an API call"""
#     self.refresh()
#     return self["nav"]


def navigate(self, waypoint, verbose=True, log=True):  # override=False
    """navigate to a waypoint in the same system"""
    # if self._in_transit(verbose):
    #     return
    # waypoint = self._waypoint(waypoint)
    # if self._no_nav(waypoint, verbose):
    #     return
    # if self._no_fuel(waypoint, verbose):  # , override
    #     return
    self.orbit()

    payload = {"waypointSymbol": waypoint}
    data = request.post(f'my/ships/{self["symbol"]}/navigate', self["agent"], payload)[
        "data"
    ]
    self._update_cache(data, ["fuel", "nav"])
    if verbose:
        t2 = round(self.nav_remaining())
        logger.info(f"{self.name()} will arrive at {waypoint} in {t2}s")
        for event in data["events"]:
            component = event["component"].lower()
            condition = self[component]["condition"]
            logger.warning(f"{self.name()} {component} at {round(condition*100)}%")
    if log:
        log_navigate(self)
        # log_event(self, "navigate", data["events"])


# def _no_nav(self, waypoint: str, verbose=True):
#     if waypoint == self["nav"]["waypointSymbol"]:
#         if verbose:
#             logger.info(f"{self.name()} is already at {waypoint}")
#         return True
#     if not waypoint.startswith(self["nav"]["systemSymbol"]):
#         raise ValueError("Waypoint is in a different system")
#     return False
#
#
# def _no_fuel(self, waypoint: str, verbose=True):  # , override=False
#     fuel = self.nav_fuel(waypoint)
#     # if self["fuel"]["current"] < fuel * 2:
#     #     if override is False:
#     #         if verbose:
#     #             logger.warning(
#     #                 f"{self.name()} is low on fuel. Use the override to fly anyway."
#     #             )
#     #         return True
#     if self["fuel"]["current"] < fuel:
#         if verbose:
#             logger.warning(f"{self.name()} does not have enough fuel!")
#         return True
#     return False


# def _waypoint(self, waypoint):  # noqa: staticmethod
#     """Return the waypoint symbol"""
#     if isinstance(waypoint, str) and waypoint.count("-") == 2:
#         return waypoint
#     elif isinstance(waypoint, dict):
#         if "systemSymbol" in waypoint:  # Waypoint class
#             return waypoint["symbol"]
#         elif "frame" in waypoint:  # Ship class
#             return waypoint["nav"]["waypointSymbol"]
#     raise ValueError("Navigate requires a Waypoint (string or class) or Ship (class)")
#
#
# def nav_distance(self, waypoint):
#     """return the distance to the waypoint"""
#     here = self["nav"]["waypointSymbol"]
#     there = self._waypoint(waypoint)
#     return round(nd(here, there))
#
#
# def nav_fuel(self, waypoint):
#     """return the amount of fuel required to navigate to the waypoint"""
#     here = self["nav"]["waypointSymbol"]
#     there = self._waypoint(waypoint)
#     mode = self["nav"]["flightMode"]
#     reactor = self["reactor"]["symbol"]
#     return nf(wp1=here, wp2=there, mode=mode, reactor=reactor)
#
#
# def nav_time(self, waypoint):
#     """return the time required to navigate to the waypoint"""
#     here = self["nav"]["waypointSymbol"]
#     there = self._waypoint(waypoint)
#     mode = self["nav"]["flightMode"]
#     speed = self["engine"]["speed"]
#     reactor = self["reactor"]["symbol"]
#     return nt(wp1=here, wp2=there, mode=mode, speed=speed, reactor=reactor)


def nav_patch(self, mode):
    """update the nav configuration of the ship"""
    # mode = mode.upper()
    # if self["nav"]["flightMode"] == mode:
    #     return
    options = ("DRIFT", "STEALTH", "CRUISE", "BURN")
    if mode not in options:
        raise ValueError(f"nav_patch {options=}")

    payload = {"flightMode": mode}
    data = request.patch(f'my/ships/{self["symbol"]}/nav', self["agent"], payload)[
        "data"
    ]
    self["nav"] = data
    self._update_cache()


def jump(self, waypoint, verbose=True, log=True):
    # if self._in_transit(verbose):
    #     return
    # if self._on_cooldown(verbose):
    #     return
    self.orbit()

    payload = {"waypointSymbol": waypoint}
    data = request.post(f'my/ships/{self["symbol"]}/jump', self["agent"], payload)[
        "data"
    ]
    self._update_cache(data, ["nav", "cooldown"])
    cache.set(("credits", request.agent), data["agent"]["credits"])

    price = data["transaction"]["totalPrice"]
    if verbose:
        wp = self["nav"]["waypointSymbol"]
        cd = data["cooldown"]["totalSeconds"]
        logger.info(
            f"{self.name()} jumped to {wp} "
            f"({cd} seconds cooldown, "
            f"{price:_} credits)"
        )

    if log:
        log_cooldown(self, "jump")
    return price


# def _no_module(self, module):
#     modules = [m["symbol"] for m in self["modules"]]
#     if any(m.startswith(module) for m in modules):
#         return False
#     return True


# def jump_cooldown(self, waypoint):
#     """return the cooldown after the jump to the waypoint"""
#     s1 = System(self, waypoints=False, graph=False)
#     s2 = System(waypoint, waypoints=False, graph=False)
#     distance = dist(s1["x"], s1["y"], s2["x"], s2["y"])
#     cooldown = nc(distance)
#     return cooldown


def warp(self, waypoint):
    # if self._in_transit(verbose):
    #     return
    # if self._no_module("MODULE_WARP_DRIVE_"):
    #     return
    # if self._no_antimatter():
    #     return
    self.orbit()

    waypoint = "-".join(waypoint.split("-")[0:2])
    payload = {"systemSymbol": waypoint}
    data = request.post(f'my/ships/{self["symbol"]}/warp', self["agent"], payload)[
        "data"
    ]
    self._update_cache(data, ["nav", "fuel"])


# def _no_antimatter(self):
#     units_required = 1
#     for g, u in self.cargo_yield():
#         if g == "ANTIMATTER" and u >= units_required:
#             return False
#     return True
