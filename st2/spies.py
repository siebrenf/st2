import json
import math

from psycopg import connect
from psycopg.types.json import Jsonb

from st2 import time
from st2.agent import api_agent, register_random_agent
from st2.logging import logger
from st2.system import System

DEBUG = False


def spymaster(request, priority=3):
    """
    Dispatch ships to all markets in all starting systems to automatically gather intelligence.

    Can be used after all start systems have been charted by the cartographer.

    Requires an active taskmaster with 'pname = "probes"'.
    """
    # Get a dict of start systems per faction
    faction2system = _get_faction2system()

    # Get a dict of markets per system
    # Note: markets will be removed from this dict when assigned
    system2market = _get_system2market(faction2system)
    total = sum([len(markets) for markets in system2market.values()])

    # load assigned ships
    role = "spy"
    pname = "probes"
    unassigned = _load_assigned_ships(system2market, role, pname)

    # load unassigned ships
    _load_unassigned_ships(system2market, unassigned, pname)

    remaining = sum([len(markets) for markets in system2market.values()])
    if DEBUG:
        logger.debug(f"{total-remaining:_}/{total:_} markets probed by the Spymaster")
    if remaining == 0:
        return

    logger.info(f"The Spymaster has found {total:_} markets in start systems")
    # register new agents to assign
    for faction, systems in faction2system.items():
        while remaining := [
            system for system in systems if len(system2market[system]) != 0
        ]:
            if DEBUG:
                n = sum([len(system2market[system]) for system in remaining])
                logger.debug(
                    f"{len(remaining): >2} {faction} systems remaining ({n: >3} markets)"
                )
            data = register_random_agent(request, priority, faction)
            agent_symbol = data["agent"]["symbol"]
            system_symbol = data["ships"][0]["nav"]["systemSymbol"]
            if len(system2market[system_symbol]) == 0:
                continue

            with connect("dbname=st2 user=postgres") as conn:
                with conn.cursor() as cur:
                    _assign_agent(agent_symbol, role, system_symbol, cur)
                    for ship_symbol in [f"{agent_symbol}-1", f"{agent_symbol}-2"]:
                        _assign_ship(
                            ship_symbol, system_symbol, system2market, pname, cur
                        )


def _get_faction2system():
    """
    Start systems:
      - contain an ENGINEERED_ASTEROID
      - do not sell "SHIP_EXPLORER"
      - can be the faction's headquarters
      - (might) have 3 "ORBITAL_STATION"s instead of 2?
    """
    faction2system = {}
    with connect("dbname=st2 user=postgres") as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT "systemSymbol", "faction"
                FROM "waypoints"
                WHERE "type" = 'ENGINEERED_ASTEROID'
                  AND "systemSymbol" NOT IN (
                      SELECT "systemSymbol"
                      FROM "shipyards"
                      WHERE %s = ANY("shipTypes")
                  )
                ORDER BY "faction", "systemSymbol"
                """,
                ["SHIP_EXPLORER"],
            )
            for system, faction in cur.fetchall():
                if faction not in faction2system:
                    faction2system[faction] = []
                if system not in faction2system[faction]:
                    faction2system[faction].append(system)
    return faction2system


def _get_system2market(faction2system):
    """
    This function wraps __get_system2market(), storing the output in table spymaster.
    """
    key = hash(json.dumps(faction2system, sort_keys=True))
    with connect("dbname=st2 user=postgres") as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS spymaster
                (
                    id BIGINT,
                    system2market JSONB
                )
                """
            )
            cur.execute(
                """
                SELECT system2market
                FROM spymaster
                WHERE id = %s
                """,
                [key],
            )
            ret = cur.fetchone()
            if ret is None:
                system2market = __get_system2market(faction2system)
                cur.execute(
                    """
                    INSERT INTO spymaster
                    (id, system2market)
                    VALUES (%s, %s)
                    """,
                    [key, Jsonb(system2market)],
                )
            else:
                system2market = ret[0]
    return system2market


def __get_system2market(faction2system):
    system2market = {}
    system2faction = {v: k for (k, vs) in faction2system.items() for v in vs}
    for system_symbol in system2faction:
        system2market[system_symbol] = []
        # sort the markets by proximity to the center (ascending)
        # (central waypoints are faster to reach)
        system = System(system_symbol, None)
        source = list(system.waypoints_with(type="ENGINEERED_ASTEROID"))[0]
        for waypoint_symbol, dist in system.waypoints_sort(
            source, list(system.markets)
        ):
            wp_type = "shipyard" if waypoint_symbol in system.shipyards else "market"
            key = (wp_type, waypoint_symbol)
            system2market[system_symbol].append(key)
    return system2market


def _load_assigned_ships(system2market, role, pname):
    unassigned = []
    with connect("dbname=st2 user=postgres") as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT symbol, "agentSymbol", current 
                FROM tasks
                WHERE "agentSymbol" IN (
                      SELECT symbol 
                      FROM agents 
                      WHERE role = %s
                ) AND pname = %s
                """,
                [role, pname],
            )
            for ship_symbol, agent_symbol, task in cur.fetchall():
                if task is None:
                    unassigned.append(ship_symbol)
                elif task.startswith("probe "):
                    _, wp_type, waypoint_symbol = task.split(" ")
                    system_symbol = waypoint_symbol.rsplit("-", 1)[0]
                    key = (wp_type, waypoint_symbol)
                    # in case multiple ships have been assigned
                    if key in system2market[system_symbol]:
                        system2market[system_symbol].remove(key)
                else:
                    raise NotImplementedError(f"{ship_symbol=} {task=}")
    return unassigned


def _load_unassigned_ships(system2market, unassigned, pname):
    with connect("dbname=st2 user=postgres") as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT symbol, nav
                FROM ships
                WHERE symbol = ANY(%s)
                """,
                [unassigned],
            )
            for ship_symbol, nav in cur.fetchall():
                system_symbol = nav["systemSymbol"]
                _assign_ship(ship_symbol, system_symbol, system2market, pname, cur)


def _assign_agent(agent_symbol, role, system_symbol, cur):
    cur.execute(
        """
        UPDATE agents
        SET role = %s,
            other = %s
        WHERE symbol = %s
        """,
        (role, system_symbol, agent_symbol),
    )


def _assign_ship(ship_symbol, system_symbol, system2market, pname, cur):
    if len(system2market[system_symbol]) != 0:
        # frigates can fly to the furthest waypoints, probed the nearest
        i = -1 if ship_symbol.endswith("-1") else 0
        wp_type, waypoint_symbol = system2market[system_symbol].pop(i)
        task = f"probe {wp_type} {waypoint_symbol}"
        cur.execute(
            """
            UPDATE tasks
            SET current = %s,
                pname = %s
            WHERE "symbol" = %s
            """,
            [task, pname, ship_symbol],
        )
        if DEBUG:
            logger.debug(f"Assigned {ship_symbol} to {wp_type} {waypoint_symbol}")


def detective(request, priority=3):
    """
    Investigate all public agents, and update the active agents
    """
    token = api_agent(request, priority)[1]
    page = 1
    total = float("inf")
    n = 0
    with connect("dbname=st2 user=postgres") as conn:
        with conn.cursor() as cur:
            while page < total:
                ret = request.get(
                    "agents", priority, token, params={"page": page, "limit": 20}
                )
                if total == float("inf"):
                    t = ret["meta"]["total"]
                    total = math.ceil(t / 20)
                    if DEBUG:
                        logger.debug(f"The Detective is investigating {t:_} agents")
                if DEBUG:
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
    if DEBUG:
        logger.debug(f"The Detective identified {n:_} active agents")


def private_eye(request, priority=3):
    """
    Update public agents that are already known to be active.
    """
    token = api_agent(request, priority)[1]
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
