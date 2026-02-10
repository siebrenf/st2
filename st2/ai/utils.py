from asyncio import sleep

from psycopg import connect
from psycopg.rows import dict_row, tuple_row

from st2.logging import logger

DEBUG = True


def get_tasks(
    ship_symbol=None,
    current=None,
    queued=None,
    current_prefix=None,
    queued_prefix=None,
    system_symbol=None,
    agent_symbol=None,
    pname=None,
    as_dict=True,
):
    query = """SELECT * FROM tasks"""
    params = []
    conditions = []
    if ship_symbol:
        conditions.append("""symbol = %s""")
        params.append(ship_symbol)
    if current:
        conditions.append("""current = %s""")
        params.append(current)
    if queued:
        conditions.append("""queued = %s""")
        params.append(queued)
    if current_prefix:
        conditions.append("""current LIKE %s""")
        params.append(f"{current_prefix}%")  # % = any length wildcard
    if queued_prefix:
        conditions.append("""queued LIKE %s""")
        params.append(f"{queued_prefix}%")  # % = any length wildcard
    if agent_symbol:
        conditions.append(""""agentSymbol" = %s""")
        params.append(agent_symbol)
    if pname:
        conditions.append("""pname = %s""")
        params.append(pname)
    if system_symbol:
        c = """symbol IN (SELECT symbol FROM ships WHERE "nav" ->> 'systemSymbol' = %s)"""
        params.append(system_symbol)
        if agent_symbol:
            c = c[:-1] + """ AND "agentSymbol" = %s)"""
            params.append(agent_symbol)
        conditions.append(c)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    factory = dict_row if as_dict else tuple_row
    with connect(
        "dbname=st2 user=postgres", row_factory=factory
    ) as conn, conn.cursor() as cur:
        tasks = cur.execute(query, params).fetchall()  # noqa
    return tasks


def queue_task(ship, task, pname=None, estimated_profit=None):
    query = """UPDATE tasks SET queued = %s"""
    params = [task]
    if pname:
        query += """, pname = %s"""
        params.append(pname)
    query += """ WHERE symbol = %s"""
    params.append(ship)
    with connect("dbname=st2 user=postgres") as conn, conn.cursor() as cur:
        cur.execute(query, params)  # noqa
    if DEBUG:
        msg = f"Queueing {task=} to {ship}"
        if estimated_profit:
            msg += f" for {estimated_profit=:_}"
        logger.debug(msg)


def cancel_task(ship, reason=None, task=None):
    with connect("dbname=st2 user=postgres") as conn, conn.cursor() as cur:
        cur.execute(
            """
            UPDATE tasks
            SET cancel = %s
            WHERE symbol = %s
            """,
            (True, ship),
        )
    if DEBUG:
        msg = "Cancelled " + (f"{task=}" if task else "task") + f" for {ship}"
        if reason:
            msg += f" {reason=}"
        logger.debug(msg)


def dequeue_task(ship, reason=None, task=None):
    with connect("dbname=st2 user=postgres") as conn, conn.cursor() as cur:
        cur.execute(
            """
            UPDATE tasks
            SET queued = %s
            WHERE symbol = %s
            """,
            (None, ship),
        )
    if DEBUG:
        msg = "Dequeued " + (f"{task=}" if task else "task") + f" for {ship}"
        if reason:
            msg += f" {reason=}"
        logger.debug(msg)


async def chart_system_marketplaces(system, interval=60):
    """
    Chart every potential marketplace.

    Uses one trader (for simplicity)
    """
    uncharted_markets = system.uncharted_markets()
    while uncharted_markets:
        if DEBUG:
            logger.debug(
                f"{len(uncharted_markets)} uncharted markets in {system.symbol}"
            )
        available_ship_symbol = None
        system_scouting_underway = False
        at = 0  # available traders
        tt = 0  # total traders
        for task in get_tasks(system_symbol=system.symbol):  # any agent
            # only queue one scouting task at a time
            for key in ["current", "queued"]:
                if str(task[key]).startswith("scout "):
                    system_scouting_underway = True
            # select a random available trader
            if task["pname"] == "traders":
                tt += 1
                if task["queued"] is None or task["queued"].startswith("trade "):
                    available_ship_symbol = task["symbol"]
                    at += 1
        if DEBUG:
            logger.debug(f"{at}/{tt} ships available to scout {system.symbol}")
        if available_ship_symbol and not system_scouting_underway:
            with connect(
                "dbname=st2 user=postgres", row_factory=dict_row
            ) as conn, conn.cursor() as cur:
                ship = cur.execute(
                    """SELECT * FROM ships WHERE symbol = %s""",
                    (available_ship_symbol,),
                ).fetchone()
            wp = ship["nav"]["waypointSymbol"]
            wps = system.shortest_passing_path(uncharted_markets, start=wp)
            assert (
                len(wps) > 1
            ), f"expected that {wp=} is not present in {uncharted_markets=}"
            waypoint_symbol = wps[1]
            task = f"scout {waypoint_symbol}"
            queue_task(ship["symbol"], task)
        await sleep(interval)
        system.refresh(refresh_graph=False)
        uncharted_markets = system.uncharted_markets()


async def scout_system_marketplaces(system, interval=60):
    """
    Scout every charted marketplace.

    Uses one trader (for simplicity)
    """
    unscouted_markets = system.unscouted_markets()
    while unscouted_markets:
        if DEBUG:
            logger.debug(
                f"{len(unscouted_markets)} unscouted markets in {system.symbol}"
            )
        available_ship_symbol = None
        system_scouting_underway = False
        at = 0  # available traders
        tt = 0  # total traders
        for task in get_tasks(system_symbol=system.symbol):  # any agent
            # only queue one scouting task at a time
            for key in ["current", "queued"]:
                if str(task[key]).startswith("scout "):
                    system_scouting_underway = True
            # select a random available trader
            if task["pname"] == "traders":
                tt += 1
                if task["queued"] is None or task["queued"].startswith("trade "):
                    available_ship_symbol = task["symbol"]
                    at += 1
        if DEBUG:
            logger.debug(f"{at}/{tt} ships available to scout {system.symbol}")
        if available_ship_symbol and not system_scouting_underway:
            with connect(
                "dbname=st2 user=postgres", row_factory=dict_row
            ) as conn, conn.cursor() as cur:
                ship = cur.execute(
                    """SELECT * FROM ships WHERE symbol = %s""",
                    (available_ship_symbol,),
                ).fetchone()
            wp = ship["nav"]["waypointSymbol"]
            wps = system.shortest_passing_path(unscouted_markets, start=wp)
            assert (
                len(wps) > 1
            ), f"expected that {wp=} is not present in {unscouted_markets=}"
            waypoint_symbol = wps[1]
            task = f"scout {waypoint_symbol}"
            queue_task(ship["symbol"], task)
        await sleep(interval)
        # system.refresh()  not needed
        unscouted_markets = system.unscouted_markets()
