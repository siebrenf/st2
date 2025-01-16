from psycopg import connect
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from st2 import time
from st2.logging import logger
from st2.request import RequestMp


class Ship(dict):
    def __init__(self, symbol, qa_pairs, priority):
        with connect("dbname=st2 user=postgres", row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                data = cur.execute(
                    "SELECT * FROM ships WHERE symbol = %s", (symbol,)
                ).fetchone()
                token = cur.execute(
                    "SELECT token FROM agents WHERE symbol = %s", (data["agentSymbol"],)
                ).fetchone()[0]
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

    # def status(self, key="condition"):
    #     if key == "condition":
    #         return {
    #             "frame": self["frame"]["condition"],
    #             "reactor": self["reactor"]["condition"],
    #             "engine": self["engine"]["condition"],
    #         }
    #     elif key == "integrity":
    #         return {
    #             "frame": self["frame"]["integrity"],
    #             "reactor": self["reactor"]["integrity"],
    #             "engine": self["engine"]["integrity"],
    #         }
    #     else:
    #         raise ValueError

    def _update(self, data=None, keys=None):
        """Update the ship data in the local dict and the remote database"""
        if keys is None:
            keys = list(data)[2:]  # skip shipSymbol & agentSymbol
        if data:
            for key in keys:
                self[key] = data[key]

        updates = ", ".join([f"{key} = %s" for key in keys])
        query = f"UPDATE ships SET {updates} WHERE symbol = %s"
        params = [Jsonb(self[key]) for key in keys] + [self["symbol"]]
        with connect("dbname=st2 user=postgres") as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                # conn.commit()

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
        self._update(data)  # TODO: update whole row at once

    def buy_ship(self, ship_type, verbose=True):
        """
        Purchase the specified ship_type at the current waypoint's shipyard.
        Returns the new ship instance.
        """
        waypoint = self["nav"]["waypointSymbol"]
        data = self.request.post(
            f"my/ships",
            data={"shipType": ship_type, "waypointSymbol": waypoint},
        )["data"]

        # TODO: log data["agent"]
        # TODO: log data["transaction"]

        ship = data["ship"]
        agent_symbol = self["agent_symbol"]
        with connect("dbname=st2 user=postgres") as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO ships
                (symbol, agentSymbol, nav, crew, fuel, cooldown, frame,
                 reactor, engine, modules, mounts, registration, cargo)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    ship["symbol"],
                    agent_symbol,
                    Jsonb(ship["nav"]),
                    Jsonb(ship["crew"]),
                    Jsonb(ship["fuel"]),
                    Jsonb(ship["cooldown"]),
                    Jsonb(ship["frame"]),
                    Jsonb(ship["reactor"]),
                    Jsonb(ship["engine"]),
                    Jsonb(ship["modules"]),
                    Jsonb(ship["mounts"]),
                    Jsonb(ship["registration"]),
                    Jsonb(ship["cargo"]),
                ),
            )

            cur.execute(
                """
                INSERT INTO tasks (symbol, agentSymbol, current, queued, cancel, pname, pid) 
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (ship["symbol"], agent_symbol, None, None, False, None, None),
            )

        if verbose:
            logger.info(
                f"{data['symbol']} bought at {waypoint} "
                f'for {data["transaction"]["price"]} credits'
            )

    # import methods
    from ._cargo import buy, cargo_yield, jettison, sell, supply, transfer
    from ._contract import contract, deliver
    from ._fuel import refuel
    from ._market import market
    from ._misc import chart
    from ._mounts import extract, siphon, survey
    from ._nav import jump, nav_patch, navigate
    from ._shipyard import shipyard
