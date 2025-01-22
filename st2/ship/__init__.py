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
                ).fetchone()["token"]
        super().__init__(data)
        self.request = RequestMp(qa_pairs, priority, token)

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

    # def _update(self, data=None, keys=None, cur=None):
    #     """Update the ship data in the local dict and the remote database"""
    #     if keys is None:
    #         keys = [k for k in data.keys() if k not in ["symbol", "agentSymbol"]]
    #
    #     # update local ship
    #     if data:
    #         for key in keys:
    #             self[key] = data[key]
    #
    #     # update remote ship
    #     updates = ", ".join([f"{key} = %s" for key in keys])
    #     query = f"UPDATE ships SET {updates} WHERE symbol = %s"
    #     params = [Jsonb(self[key]) for key in keys] + [self["symbol"]]
    #     with connect("dbname=st2 user=postgres") as conn:
    #         with conn.cursor() as cur:
    #             cur.execute(query, params)

    def _update(self, data):
        keys = set(data.keys()) & set(self.keys())
        keys.discard("symbol")
        for key in keys:
            self[key] = data[key]

        with connect("dbname=st2 user=postgres") as conn:
            with conn.cursor() as cur:
                if keys:
                    updates = ", ".join([f'"{key}" = %s' for key in keys])
                    query = f"UPDATE ships SET {updates} WHERE symbol = %s"
                    params = [Jsonb(self[key]) for key in keys] + [self["symbol"]]
                    cur.execute(query, params)

                if "agent" in data:
                    agent = data["agent"]
                    cur.execute(
                        """
                        INSERT INTO agents_public
                        ("accountId", "symbol", "headquarters", "credits",
                         "startingFaction", "shipCount", "timestamp")
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            agent["accountId"],
                            agent["symbol"],
                            agent["headquarters"],
                            agent["credits"],
                            agent["startingFaction"],
                            agent["shipCount"],
                            time.now(),
                        ),
                    )

                if "transaction" in data:
                    # TODO: fails with repair-/scrap-/modificationTransaction
                    transaction = data["transaction"]
                    cur.execute(
                        """
                        INSERT INTO market_transactions
                        ("waypointSymbol", "systemSymbol", "shipSymbol", "tradeSymbol",
                         "type", "units", "pricePerUnit", "totalPrice", "timestamp")
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT ("waypointSymbol", "timestamp") DO NOTHING
                        """,
                        (
                            transaction["waypointSymbol"],
                            self["nav"]["systemSymbol"],
                            transaction["shipSymbol"],
                            transaction["tradeSymbol"],
                            transaction["type"],
                            transaction["units"],
                            transaction["pricePerUnit"],
                            transaction["totalPrice"],
                            time.read(transaction["timestamp"]),
                        ),
                    )

                for event in data.get("events", []):
                    activity = None
                    if "fuel" in data:
                        activity = "navigate"
                    elif "extraction" in data:
                        activity = "extract"
                    elif "siphon" in data:
                        activity = "siphon"
                    condition = self[event["component"].lower()]["condition"]
                    cur.execute(
                        """
                        INSERT INTO events
                        (symbol, "shipSymbol", activity, component, condition, timestamp)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                        (
                            event["symbol"],
                            self["symbol"],
                            activity,
                            event["component"],
                            condition,
                            time.now(),
                        ),
                    )

    def dock(self):
        self._nav_status()
        if self["nav"]["status"] == "IN_ORBIT":
            data = self.request.post(f'my/ships/{self["symbol"]}/dock')["data"]
            self._update(data)

    def orbit(self):
        self._nav_status()
        if self["nav"]["status"] == "DOCKED":
            data = self.request.post(f'my/ships/{self["symbol"]}/orbit')["data"]
            self._update(data)

    def _nav_status(self):
        """update IN_TRANSIT if the ship has arrived"""
        if self["nav"]["status"] == "IN_TRANSIT":
            if self.nav_remaining() == 0:
                data = {"nav": self["nav"]}
                data["nav"]["status"] = "IN_ORBIT"
                self._update(data)

    def refresh(self, online=True):
        if online:
            data = self.request.get(f'my/ships/{self["symbol"]}')["data"]
            self._update(data)
        else:
            with connect("dbname=st2 user=postgres", row_factory=dict_row) as conn:
                with conn.cursor() as cur:
                    data = cur.execute(
                        "SELECT * FROM ships WHERE symbol = %s", (self["symbol"],)
                    ).fetchone()
                    for k, v in data.items():
                        self[k] = v

    def buy_ship(self, ship_type, verbose=True):
        """
        Purchase the specified ship_type at the current waypoint's shipyard.
        Returns the new ship instance.
        """
        ship_symbol = buy_ship(
            ship_type,
            self["nav"]["waypointSymbol"],
            self["agentSymbol"],
            self.request,
            verbose,
        )
        self.shipyard()
        return ship_symbol

    # import methods
    from ._cargo import buy, cargo_yield, jettison, sell, supply, transfer
    from ._contract import contract, deliver
    from ._fuel import refuel
    from ._market import market
    from ._misc import chart
    from ._mounts import extract, siphon, survey
    from ._nav import jump, nav_patch, navigate
    from ._shipyard import shipyard


def buy_ship(ship_type, waypoint_symbol, agent_symbol, request, verbose=True):
    """
    Purchase the specified ship_type at the current waypoint's shipyard.
    Returns the new ship instance.
    """
    system_symbol = waypoint_symbol.rsplit("-", 1)[0]
    data = request.post(
        f"my/ships",
        data={
            "shipType": ship_type,
            "waypointSymbol": waypoint_symbol,
        },
    )["data"]

    with connect("dbname=st2 user=postgres") as conn:
        with conn.cursor() as cur:
            ship = data["ship"]
            ship["cooldown"]["expiration"] = time.write()
            cur.execute(
                """
                INSERT INTO ships
                ("symbol", "agentSymbol", "nav", "crew", "fuel", "cooldown", "frame",
                 "reactor", "engine", "modules", "mounts", "registration", "cargo")
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
                INSERT INTO tasks ("symbol", "agentSymbol", "current", "queued", "cancel", "pname", "pid")
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (ship["symbol"], agent_symbol, None, None, False, None, None),
            )

            agent = data["agent"]
            cur.execute(
                """
                INSERT INTO agents_public
                ("accountId", "symbol", "headquarters", "credits",
                 "startingFaction", "shipCount", "timestamp")
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    agent["accountId"],
                    agent["symbol"],
                    agent["headquarters"],
                    agent["credits"],
                    agent["startingFaction"],
                    agent["shipCount"],
                    time.now(),
                ),
            )

            transaction = data["transaction"]
            cur.execute(
                """
                INSERT INTO shipyard_transactions
                ("waypointSymbol", "systemSymbol", "shipSymbol",
                 "agentSymbol", "shipType", "price", "timestamp")
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT ("waypointSymbol", "timestamp") DO NOTHING
                """,
                (
                    transaction["waypointSymbol"],
                    system_symbol,
                    transaction["shipSymbol"],
                    transaction["agentSymbol"],
                    transaction["shipType"],
                    transaction["price"],
                    time.read(transaction["timestamp"]),
                ),
            )

    if verbose:
        logger.info(
            f'{ship["registration"]["role"].capitalize()} {ship["frame"]["name"].lower()} {ship["symbol"]} '
            f'bought at {waypoint_symbol} for {data["transaction"]["price"]} credits'
        )

    return ship["symbol"]
