from st2.logging import logger


def navigate(self, waypoint, verbose=True):
    """navigate to a waypoint in the same system"""
    self.orbit()

    data = self.request.post(
        f'my/ships/{self["symbol"]}/navigate', data={"waypointSymbol": waypoint}
    )["data"]
    self._update(data, ["fuel", "nav"])

    # TODO: log data["events"]
    # TODO: log distance, mode, nav time & fuel cost?
    # TODO: create table navigates

    if verbose:
        t2 = round(self.nav_remaining())
        logger.info(f"{self.name()} will arrive at {waypoint} in {t2}s")
        for event in data["events"]:
            component = event["component"].lower()
            condition = self[component]["condition"]
            logger.warning(f"{self.name()} {component} at {round(condition*100)}%")


def nav_patch(self, mode):
    """update the nav configuration of the ship"""
    options = ("DRIFT", "STEALTH", "CRUISE", "BURN")
    if mode not in options:
        raise ValueError(f"nav_patch {options=}")

    data = self.request.patch(
        f'my/ships/{self["symbol"]}/nav',
        data={"flightMode": mode},
    )["data"]
    self._update(data, ["nav"])


def jump(self, waypoint, verbose=True):
    self.orbit()

    data = self.request.post(
        f'my/ships/{self["symbol"]}/jump',
        data={"waypointSymbol": waypoint},
    )["data"]
    self._update(data, ["nav", "cooldown"])

    # TODO: log data["agent"]
    # TODO: log data["transaction"]

    if verbose:
        wp = self["nav"]["waypointSymbol"]
        cd = data["cooldown"]["totalSeconds"]
        price = data["transaction"]["totalPrice"]
        logger.info(
            f"{self.name()} jumped to {wp} "
            f"({cd} seconds cooldown, "
            f"{price:_} credits)"
        )


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


# def warp(self, waypoint):
#     # if self._in_transit(verbose):
#     #     return
#     # if self._no_module("MODULE_WARP_DRIVE_"):
#     #     return
#     # if self._no_antimatter():
#     #     return
#     self.orbit()
#
#     waypoint = "-".join(waypoint.split("-")[0:2])
#     payload = {"systemSymbol": waypoint}
#     data = request.post(f'my/ships/{self["symbol"]}/warp', self["agent"], payload)[
#         "data"
#     ]
#     self._update_cache(data, ["nav", "fuel"])


# def _no_antimatter(self):
#     units_required = 1
#     for g, u in self.cargo_yield():
#         if g == "ANTIMATTER" and u >= units_required:
#             return False
#     return True
