import math
from asyncio import sleep

from psycopg import connect

from st2 import time
from st2.agent import api_agent
from st2.logging import logger

DEBUG = True


async def detective(request, priority=3, verbose=True):
    """
    Investigate all public agents, and update the active agents
    """
    token = api_agent(request, priority)[1]
    page = 1
    total = float("inf")
    n = 0
    with connect("dbname=st2 user=postgres") as conn, conn.cursor() as cur:
        while page < total:
            ret = request.get(
                "agents", priority, token, params={"page": page, "limit": 20}
            )
            if total == float("inf"):
                t = ret["meta"]["total"]
                total = math.ceil(t / 20)
                if verbose and DEBUG:
                    logger.debug(f"The Detective is investigating {t:_} agents")
            if verbose and DEBUG:
                logger.debug(f"Processing page {page:_}/{total:_}")
            timestamp = time.now()
            for agent in ret["data"]:
                if agent["credits"] > 175_000:
                    cur.execute(
                        """
                        INSERT INTO agents_public
                        ("symbol", "headquarters", "credits",
                         "startingFaction", "shipCount", "timestamp")
                        VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                        (
                            agent["symbol"],
                            agent["headquarters"],
                            agent["credits"],
                            agent["startingFaction"],
                            agent["shipCount"],
                            timestamp,
                        ),
                    )
                    n += 1
            page += 1
            await sleep(0)  # give other processes a turn
        # record the last time the detective completed its run
        # assumes the table was already created by the ai_advisor_controller()
        cur.execute(
            """
            UPDATE detective
            SET timestamp = %s
            WHERE id = %s;
            """,
            (time.now(), True),
        )
    if verbose:
        logger.info(f"The Detective identified {n:_} active agents")


async def private_eye(request, priority=3, verbose=True):
    """
    Update public agents that are already known to be active.
    """
    token = api_agent(request, priority)[1]
    n = 0
    with connect("dbname=st2 user=postgres") as conn, conn.cursor() as cur:
        for (agent_symbol,) in cur.execute(
            """
            SELECT DISTINCT ON (symbol) symbol 
            FROM agents_public 
            WHERE credits > 175000
            ORDER BY symbol, timestamp DESC
            """
        ).fetchall():
            agent = request.get(f"agents/{agent_symbol}", priority, token)["data"]
            timestamp = time.now()
            cur.execute(
                """
                INSERT INTO agents_public
                ("symbol", "headquarters", "credits",
                 "startingFaction", "shipCount", "timestamp")
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    agent["symbol"],
                    agent["headquarters"],
                    agent["credits"],
                    agent["startingFaction"],
                    agent["shipCount"],
                    timestamp,
                ),
            )
            n += 1
            await sleep(0)  # give other processes a turn
    if verbose:
        logger.info(f"The private eye tracked all {n:_} active agents")


def get_last_detective_run():
    with connect("dbname=st2 user=postgres") as conn, conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS detective
            (
                id boolean PRIMARY KEY,
                timestamp timestamptz
            )
            """
        )
        ret = cur.execute("""SELECT * FROM detective""").fetchone()
        if ret is None:
            ret = (True, time.read("2025-01-01T00:00:00.000Z"))
            cur.execute(
                """
                INSERT INTO detective (id, timestamp)
                VALUES (%s, %s);
                """,
                ret,
            )
    seconds_passed = (time.now() - ret[1]).total_seconds()
    return seconds_passed
