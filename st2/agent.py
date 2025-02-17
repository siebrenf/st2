import os
import random
import string

from psycopg import connect
from psycopg.types.json import Jsonb

from st2 import time


def api_agent(request, priority=0):
    """
    Register an agent to use for agent-independent API requests.
    This is to notice server resets immediately.
    """
    role = "reset detection"
    with connect("dbname=st2 user=postgres") as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT symbol, token, role FROM agents WHERE role = %s",
                (role,),
            )
            ret = cur.fetchone()
            if ret is None:
                data = register_random_agent(
                    request,
                    priority,
                    insert_ship=False,
                    insert_probe=False,
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
            else:
                symbol, token, role = ret
    return symbol, token


def register_random_agent(
    request,
    priority,
    faction="COSMIC",
    email=None,
    insert_agent=False,
    insert_contract=False,
    insert_ship=True,
    insert_probe=True,
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
                insert_ship,
                insert_probe,
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
    insert_ship=True,
    insert_probe=True,
):
    assert symbol == symbol.upper()
    payload = {"symbol": symbol, "faction": faction}
    if email:
        payload["email"] = email
    # data keys: ['token', 'agent', 'contract', 'faction', 'ship']
    token = os.environ["ST_ACCOUNT_TOKEN"]
    data = request.post("register", priority, token, payload)["data"]
    with connect("dbname=st2 user=postgres") as conn:
        with conn.cursor() as cur:
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

            if insert_ship:
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

            if insert_probe:
                ship = request.get(f"my/ships/{symbol}-2", priority, data["token"])[
                    "data"
                ]
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
