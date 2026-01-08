from psycopg import connect
from psycopg.types.json import Jsonb

from st2 import time
from st2.logging import logger


def contract(self, verbose=True):
    """Request a new contract. Ship must be present at a faction controlled waypoint"""
    self.dock()

    data = self.request.post(f'my/ships/{self["symbol"]}/negotiate/contract')["data"][
        "contract"
    ]
    with connect("dbname=st2 user=postgres") as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO contracts
                ("id", "agentSymbol", "factionSymbol", "type", "terms",
                 "accepted", "fulfilled", "deadlineToAccept")
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    data["id"],
                    self["agentSymbol"],
                    data["factionSymbol"],
                    data["type"],
                    Jsonb(data["terms"]),
                    data["accepted"],
                    data["fulfilled"],
                    time.read(data["deadlineToAccept"]),
                ),
            )
    if verbose:
        logger.info(f"Contract negotiated!")
    return data


def deliver(self, symbol, units, contract, verbose=True):
    self.dock()

    if not isinstance(contract, str):
        contract = contract["id"]
    data = self.request.post(
        f"my/contracts/{contract}/deliver",
        data={"shipSymbol": self["symbol"], "tradeSymbol": symbol, "units": units},
    )["data"]
    self._update(data)

    with connect("dbname=st2 user=postgres") as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE contracts
                SET terms = %s
                WHERE id = %s
                """,
                (
                    Jsonb(data["contract"]["terms"]),
                    data["contract"]["id"],
                ),
            )

    if verbose:
        wp = self["nav"]["waypointSymbol"]
        logger.info(f"{self.name()} delivered {units} {symbol} at {wp}")
