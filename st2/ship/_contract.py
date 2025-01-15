from st2.logging import logger
from psycopg import connect
from psycopg.types.json import Jsonb
from st2 import time


def contract(self):
    """Request a new contract. Ship must be present at a faction controlled waypoint"""
    self.dock()

    data = self.request.post(
        f'my/ships/{self["symbol"]}/negotiate/contract'
    )["data"]["contract"]
    with connect("dbname=st2 user=postgres") as conn:
        conn.execute(
            """
            INSERT INTO contracts
            (id, agentSymbol, factionSymbol, type, terms,
             accepted, fulfilled, deadlineToAccept)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                data["id"],
                self["agent"],
                data["factionSymbol"],
                data["type"],
                Jsonb(data["terms"]),
                data["accepted"],
                data["fulfilled"],
                time.read(data["deadlineToAccept"]),
            ),
        )
        conn.commit()
    return data


def deliver(self, symbol, units, contract, verbose=True):
    self.dock()

    data = self.request.post(
        f'my/contracts/{contract["id"]}/deliver',
        data={"shipSymbol": self["symbol"], "tradeSymbol": symbol, "units": units}
    )["data"]
    self._update(data, ["cargo"])

    with connect("dbname=st2 user=postgres") as conn:
        conn.execute(
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
        conn.commit()

    # # update contract
    # contract["terms"] = data["contract"]["terms"]
    # contract["fulfilled"] = data["contract"]["fulfilled"]
    # wp = self["nav"]["waypointSymbol"]
    # contract.delivery_data[wp][symbol]["units"] -= units
    if verbose:
        wp = self["nav"]["waypointSymbol"]
        logger.info(f"{self.name()} delivered {units} {symbol} at {wp}")
