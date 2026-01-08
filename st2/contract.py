from psycopg import connect
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from st2 import time
from st2.agent import get_agent
from st2.exceptions import ContractNotFoundError
from st2.logging import logger
from st2.request import RequestMp
from st2.ship import Ship


class Contract(dict):
    def __init__(self, contract_id, request=None, qa_pairs=None, priority=1):
        with connect(
            "dbname=st2 user=postgres", row_factory=dict_row
        ) as conn, conn.cursor() as cur:
            data = cur.execute(
                "SELECT * FROM contracts WHERE id = %s", (contract_id,)
            ).fetchone()
            if data is None:
                raise ContractNotFoundError(f"Could not find contract {contract_id}")
            token = get_agent(data["agentSymbol"])["token"]
        super().__init__(data)
        if request:
            self.request = request.copy()
            if priority:
                self.request.priority = priority
            self.request.token = token
        elif qa_pairs:
            self.request = RequestMp(qa_pairs, priority, token)
        else:
            raise ValueError(f"Contract required arguments 'request' or 'qa_pairs'")

    def _update(self, data):
        agent = data.get("agent")  # accept and fulfill
        if "contract" in data:
            data = data["contract"]

        keys = []
        for k, v in data.items():
            if k in self and self[k] != v:
                self[k] = v
                keys.append(k)
        with connect("dbname=st2 user=postgres") as conn, conn.cursor() as cur:
            if keys:
                updates = ", ".join([f'"{key}" = %s' for key in keys])
                query = f"UPDATE contracts SET {updates} WHERE id = %s"
                params = []
                for key in keys:
                    value = Jsonb(self[key]) if key == "terms" else self[key]
                    params.append(value)
                params += [self["id"]]
                cur.execute(query, params)

            if agent:
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

    def refresh(self, online=True):
        if online:
            data = self.request.get(f"my/contracts/{self["id"]}")["data"]
            self._update(data)
        else:
            with connect(
                "dbname=st2 user=postgres", row_factory=dict_row
            ) as conn, conn.cursor() as cur:
                data = cur.execute(
                    "SELECT * FROM contracts WHERE id = %s", (self["id"],)
                ).fetchone()
                for k, v in data.items():
                    self[k] = v

    def accept(self, verbose=True):
        data = self.request.post(f"my/contracts/{self["id"]}/accept")["data"]
        self._update(data)
        if verbose:
            logger.info(f"Contract accepted!")
        return data

    def fulfill(self, verbose=True):
        data = self.request.post(f"my/contracts/{self["id"]}/fulfill")["data"]
        self._update(data)
        if verbose:
            logger.info(f"Contract fulfilled!")
        return data

    def deliver(self, ship_symbol, trade_symbol, units, verbose=True):
        ship = Ship(ship_symbol, self.request)
        ship.deliver(trade_symbol, units, self["id"], verbose)

    def negotiate(self, ship_symbol, verbose=True):
        """
        Negotiate a new contract. A new Contract instance will be required.
        """
        ship = Ship(ship_symbol, self.request)
        data = ship.contract(verbose)
        self._update(data)


def get_active_contract(agent_symbol):
    with connect(
        "dbname=st2 user=postgres", row_factory=dict_row
    ) as conn, conn.cursor() as cur:
        contract = cur.execute(
            """
            SELECT * FROM "contracts"
            WHERE "agentSymbol" = %s
            ORDER BY "deadlineToAccept" DESC
            LIMIT 1
            """,
            (agent_symbol,),
        ).fetchone()
    if contract["fulfilled"]:
        return None
    if time.remaining(contract["terms"]["deadline"]) == 0:
        return None
    if not contract["accepted"] and time.remaining(contract["deadlineToAccept"]) == 0:
        return None
    return contract
