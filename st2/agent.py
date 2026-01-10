import os
import random
import string

from psycopg import connect
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from st2 import time


def api_agent(request=None, priority=1):
    """
    Register an agent to use for agent-independent API requests.
    This is to notice server resets immediately.
    """
    role = "reset detection"
    with connect("dbname=st2 user=postgres") as conn, conn.cursor() as cur:
        ret = cur.execute(
            "SELECT symbol, token FROM agents WHERE role = %s",
            (role,),
        ).fetchone()
        if ret:
            symbol, token = ret
        else:
            if request is None:
                raise ValueError(
                    "Argument request is required when no api_agent exists!"
                )
            data = register_random_agent(
                request,
                priority,
                insert_ships=False,
            )
            symbol = data["agent"]["symbol"]
            token = data["token"]
            cur.execute(
                """
                UPDATE agents
                SET role = %s
                WHERE symbol = %s
                """,
                (role, symbol),
            )
    return symbol, token


def register_random_agent(
    request,
    priority,
    faction="COSMIC",
    email=None,
    insert_agent=False,
    insert_contract=False,
    insert_ships=True,
    max_tries=10,
):
    tries = []
    while len(tries) < max_tries:
        try:
            symbol = "".join(
                random.choices(string.ascii_uppercase + string.digits, k=14)
            )
            data = register_agent(
                request,
                priority,
                symbol,
                faction,
                email,
                insert_agent,
                insert_contract,
                insert_ships,
            )
            return data
        except Exception as e:
            tries.append(e)
    for error in tries:
        print(str(error))
    raise tries[-1]


def register_agent(
    request,
    priority,
    symbol,
    faction="COSMIC",
    email=None,
    insert_agent=True,
    insert_contract=True,
    insert_ships=True,
):
    assert symbol == symbol.upper()
    payload = {"symbol": symbol, "faction": faction}
    if email:
        payload["email"] = email
    # data keys: ['token', 'agent', 'contract', 'faction', 'ships']
    account_token = os.environ["ST_ACCOUNT_TOKEN"]
    data = request.post("register", priority, account_token, payload)["data"]
    with connect("dbname=st2 user=postgres") as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO agents
            (symbol, token, role, faction, other)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (symbol, data["token"], None, faction, None),
        )

        if insert_agent:
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

        if insert_contract:
            contract = data["contract"]
            cur.execute(
                """
                INSERT INTO contracts
                ("id", "agentSymbol", "factionSymbol", "type", "terms",
                 "accepted", "fulfilled", "deadlineToAccept")
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    contract["id"],
                    symbol,
                    contract["factionSymbol"],
                    contract["type"],
                    Jsonb(contract["terms"]),
                    contract["accepted"],
                    contract["fulfilled"],
                    time.read(contract["deadlineToAccept"]),
                ),
            )

        if insert_ships:
            for ship in data["ships"]:
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
                        symbol,
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
                    (ship["symbol"], symbol, None, None, False, None, None),
                )
    return data


def get_agent(symbol):
    with connect(
        "dbname=st2 user=postgres", row_factory=dict_row
    ) as conn, conn.cursor() as cur:
        agent = cur.execute(
            """SELECT token FROM agents WHERE symbol = %s""",
            (symbol,),
        ).fetchone()
    return agent


def get_agent_public(symbol):
    with connect(
        "dbname=st2 user=postgres", row_factory=dict_row
    ) as conn, conn.cursor() as cur:
        agent_public = cur.execute(
            """
            SELECT * 
            FROM "agents_public" 
            WHERE "symbol" = %s 
            ORDER BY "timestamp" DESC
            """,
            (symbol,),
        ).fetchone()
    return agent_public
