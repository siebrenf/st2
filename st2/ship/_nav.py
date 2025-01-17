import math

from psycopg import connect

from st2 import time
from st2.logging import logger


def dist(x1, y1, x2, y2):
    # Pythagorean theorem
    a = math.pow(x1 - x2, 2)
    b = math.pow(y1 - y2, 2)
    c = math.sqrt(a + b)
    return c


def navigate(self, waypoint, verbose=True):
    """navigate to a waypoint in the same system"""
    self.orbit()

    data = self.request.post(
        f'my/ships/{self["symbol"]}/navigate', data={"waypointSymbol": waypoint}
    )["data"]
    self._update(data)

    # Log travel distance/travel time/fuel use etc.
    origin = self["nav"]["route"]["origin"]
    destination = self["nav"]["route"]["destination"]
    distance = dist(
        origin["x"],
        origin["y"],
        destination["x"],
        destination["y"],
    )
    t0 = time.read(self["nav"]["route"]["departureTime"])
    t1 = time.read(self["nav"]["route"]["arrival"])
    travel_time = (t1 - t0).seconds
    with connect("dbname=st2 user=postgres") as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO navigation
                ("distance", "time", "fuel", "flightMode", "speed",
                "frame", "frame_condition", "frame_integrity", 
                "reactor", "reactor_condition", "reactor_integrity", 
                "engine", "engine_condition", "engine_integrity")
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    distance,
                    travel_time,
                    self["fuel"]["consumed"]["amount"],
                    self["nav"]["flightMode"],
                    self["engine"]["speed"],
                    self["frame"]["symbol"],
                    self["frame"]["condition"],
                    self["frame"]["integrity"],
                    self["reactor"]["symbol"],
                    self["reactor"]["condition"],
                    self["reactor"]["integrity"],
                    self["engine"]["symbol"],
                    self["engine"]["condition"],
                    self["engine"]["integrity"],
                ),
            )

    if verbose:
        t2 = round(self.nav_remaining())
        logger.info(f"{self.name()} will arrive at {waypoint} in {t2}s")
        for event in data["events"]:
            component = event["component"].lower()
            condition = self[component]["condition"]
            logger.warning(f"{self.name()} {component} at {round(condition*100)}%")


def nav_patch(self, mode):
    """update the nav configuration of the ship"""
    if mode != self["nav"]["flightMode"]:
        nav = self.request.patch(
            f'my/ships/{self["symbol"]}/nav',
            data={"flightMode": mode},
        )["data"]
        self._update({"nav": nav})


def jump(self, waypoint, verbose=True):
    self.orbit()

    data = self.request.post(
        f'my/ships/{self["symbol"]}/jump',
        data={"waypointSymbol": waypoint},
    )["data"]
    self._update(data)

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
