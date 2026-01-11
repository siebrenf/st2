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
    if verbose:
        logger.info(f"The Detective identified {n:_} active agents")


def private_eye(request, priority=3, verbose=True):
    """
    Update public agents that are already known to be active.
    """
    token = api_agent(request, priority)[1]
    n = 0
    with connect("dbname=st2 user=postgres") as conn, conn.cursor() as cur:
        for (agent_symbol,) in cur.execute(
            """SELECT DISTINCT symbol FROM agents_public WHERE credits > 175000"""
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
    if verbose:
        logger.info(f"The private eye tracked all {n:_} active agents")
