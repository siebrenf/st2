from st2 import time
from st2.request import RequestMp

from psycopg import connect
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

# __all__ = [
#     "Ship",
#     "ship_buy",
#     "ship_list",
#     "ship_get",
# ]


class Ship(dict):
    def __init__(self, symbol, qa_pairs, priority):
        with connect("dbname=st2 user=postgres",  row_factory=dict_row) as conn:
            data = conn.execute("SELECT * FROM ships WHERE symbol = %s", (symbol,)).fetchone()
            token = conn.execute("SELECT token FROM agents WHERE symbol = %s", (data["agentSymbol"],)).fetchone()[0]
        super().__init__(data)
        self.request = RequestMp(qa_pairs, priority, token)
        # if "expiration" not in self["cooldown"]:
        #     self["cooldown"]["expiration"] = time.write()

    def name(self):
        return f'{self["registration"]["role"].capitalize()} {self["frame"]["name"].lower()} {self["symbol"]}'

    def nav_remaining(self):
        return time.remaining(self["nav"]["route"]["arrival"])

    def cooldown_remaining(self):
        return time.remaining(self["cooldown"]["expiration"])

    def status(self, key="condition"):
        if key == "condition":
            return {
                "frame": self["frame"]["condition"],
                "reactor": self["reactor"]["condition"],
                "engine": self["engine"]["condition"],
            }
        elif key == "integrity":
            return {
                "frame": self["frame"]["integrity"],
                "reactor": self["reactor"]["integrity"],
                "engine": self["engine"]["integrity"],
            }
        else:
            raise ValueError

    def _update(self, data=None, keys=None):
        """Update the ship data in the local dict and the remote database"""
        if keys is None:
            keys = data.keys()
        with connect("dbname=st2 user=postgres", row_factory=dict_row) as conn:
            for key in keys:
                if data:
                    self[key] = data[key]
                conn.execute(
                    f"UPDATE ships SET {key} = %s WHERE symbol = %s",
                    (Jsonb(self[key]), self["symbol"])
                )
            conn.commit()

    def dock(self):
        self._status()
        if self["nav"]["status"] == "IN_ORBIT":
            data = self.request.post(f'my/ships/{self["symbol"]}/dock')["data"]
            self._update(data, keys=["nav"])

    def orbit(self):
        self._status()
        if self["nav"]["status"] == "DOCKED":
            data = self.request.post(f'my/ships/{self["symbol"]}/orbit')["data"]
            self._update(data, keys=["nav"])

    def _status(self):
        """update IN_TRANSIT if the ship has arrived"""
        if self["nav"]["status"] == "IN_TRANSIT":
            if self.nav_remaining() == 0:
                self["nav"]["status"] = "IN_ORBIT"
                self._update(keys=["nav"])

    def refresh(self):
        """Update the ship with the API server"""
        data = self.request.get(f'my/ships/{self["symbol"]}')["data"]
        self._update(data)

    # def buy_ship(self, ship_type, verbose=True):
    #     """
    #     Purchase the specified ship_type at the current waypoint's shipyard.
    #     Returns the new ship instance.
    #     """
    #     waypoint = self["nav"]["waypointSymbol"]
    #     data = self.request.post(
    #         f"my/ships",
    #         data={"shipType": ship_type, "waypointSymbol": waypoint},
    #     )["data"]
    #
    #     ship = Ship(data["symbol"], qa_pairs=self.request.q)
    #     return ship

    # import methods
    from ._cargo import buy, cargo_yield, jettison, sell, supply, transfer
    from ._contract import contract, deliver
    from ._fuel import refuel
    from ._market import market
    from ._misc import chart
    from ._mounts import extract, siphon, survey
    from ._nav import jump, nav_patch, navigate
    from ._shipyard import shipyard


# def ship_buy(ship_type, waypoint, agent=None, verbose=True):
#     """
#     Purchase the specified ship_type at the waypoint's shipyard.
#     Requires a ship at the waypoint.
#     Returns the new ship instance.
#     """
#     payload =
#     data = request.post(f"my/ships", agent, payload)["data"]
#     ship = ship_get(data["ship"])
#
#     if verbose:
#         logger.info(
#             f"{ship.name()} bought at {waypoint} "
#             f'for {data["transaction"]["price"]} credits'
#         )
#     # noinspection PyArgumentList
#     ship.shipyard()
#     # noinspection PyArgumentList
#     ship.market()
#     return ship


# def ship_list(get_all=False, agent=None, page=1):
#     """list all ship classes (max 20 per function call)"""
#     if get_all:
#         data = []
#         for ret in request.get_all("my/ships", agent):
#             data.extend(ret["data"])
#     else:
#         payload = {"page": page, "limit": 20}
#         data = request.get("my/ships", agent, payload)["data"]
#     return [ship_get(d) for d in data]
#
#
# def ship_get(symbol: str or Ship):
#     """Return a Ship class instance from the cache"""
#     if isinstance(symbol, str):  # ship instance
#         symbol = symbol.upper()
#     elif isinstance(symbol, dict):  # ship instance
#         symbol = symbol["symbol"]
#     else:
#         raise ValueError("Need Ship or ship symbol")
#     ship = cache.get(("ship", symbol))
#     if ship is None:
#         ship = Ship(symbol)
#         cache[("ship", symbol)] = ship
#     return ship
