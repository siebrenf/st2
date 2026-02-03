import json
from asyncio import sleep

from psycopg import connect
from psycopg.types.json import Jsonb

from st2.agent import api_agent, get_agent_public, register_random_agent
from st2.logging import logger
from st2.system import System

DEBUG = True


async def spymasters_apprentice(agent_symbol, request, priority=2, verbose=True):
    """
    Dispatch ships to all markets in one starting systems to automatically gather intelligence.

    Can be used on any start system.

    Requires an active taskmaster with 'pname = "probes"'.
    """
    token = api_agent(request, priority)[1]
    request = request.copy()
    request.token = token

    agent = get_agent_public(agent_symbol)
    system_symbol = agent["headquarters"].rsplit("-", 1)[0]
    faction = agent["startingFaction"]

    system2market = {system_symbol: []}
    # sort the markets by proximity to the center (ascending)
    # (central waypoints are faster to reach)
    system = System(system_symbol, request)
    source = list(system.waypoints_with(type="ENGINEERED_ASTEROID"))[0]
    for waypoint_symbol in system.waypoints_sort(source, list(system.markets)):
        wp_type = "shipyard" if waypoint_symbol in system.shipyards else "market"
        key = (wp_type, waypoint_symbol)
        system2market[system_symbol].append(key)
    total = len(system2market[system_symbol])

    role = "spy"
    pname = "probes"
    _load_assigned_ships(system2market, role, pname)
    _load_unassigned_ships(system2market, role, pname)

    remaining = len(system2market[system_symbol])
    if verbose and DEBUG:
        logger.debug(
            f"{total-remaining:_}/{total:_} markets probed by the Spymaster's apprentice "
            f"in start system {system_symbol}"
        )
    if remaining == 0:
        return

    if verbose:
        logger.info(
            f"The Spymaster's apprentice has found {total:_} markets in start system {system_symbol}"
        )
    target_system_symbol = system_symbol
    while len(system2market[target_system_symbol]) != 0:
        data = register_random_agent(request, priority, faction)
        agent_symbol = data["agent"]["symbol"]
        system_symbol = data["ships"][0]["nav"]["systemSymbol"]
        if len(system2market[system_symbol]) == 0:
            continue

        with connect("dbname=st2 user=postgres") as conn, conn.cursor() as cur:
            _assign_agent(agent_symbol, role, system_symbol, cur)
            for ship in data["ships"]:
                if len(system2market[system_symbol]) != 0:
                    _assign_ship(
                        ship["symbol"], system_symbol, system2market, pname, cur
                    )
        await sleep(0)  # give other processes a turn


async def spymaster(request, priority=3, verbose=True):
    """
    Dispatch ships to all markets in all starting systems to automatically gather intelligence.

    Can be used after all start systems have been charted by the cartographer.

    Requires an active taskmaster with 'pname = "probes"'.
    """
    # Get a dict of start systems per faction
    faction2system = _get_faction2system()

    # Get a dict of markets per system
    # Note: markets will be removed from this dict when assigned
    system2market = _get_system2market(faction2system, request)
    total = sum([len(markets) for markets in system2market.values()])

    role = "spy"
    pname = "probes"
    _load_assigned_ships(system2market, role, pname)
    _load_unassigned_ships(system2market, role, pname)

    remaining = sum([len(markets) for markets in system2market.values()])
    if verbose and DEBUG:
        logger.debug(f"{total-remaining:_}/{total:_} markets probed by the Spymaster")
    if remaining == 0:
        return

    if verbose:
        logger.info(f"The Spymaster has found {total:_} markets in start systems")
    # register new agents to assign
    for faction, systems in faction2system.items():
        while remaining := [
            system for system in systems if len(system2market[system]) != 0
        ]:
            if verbose and DEBUG:
                n = sum([len(system2market[system]) for system in remaining])
                logger.debug(
                    f"{len(remaining): >2} {faction} systems remaining ({n: >3} markets)"
                )
            data = register_random_agent(request, priority, faction)
            agent_symbol = data["agent"]["symbol"]
            system_symbol = data["ships"][0]["nav"]["systemSymbol"]
            if len(system2market[system_symbol]) == 0:
                continue

            with connect("dbname=st2 user=postgres") as conn, conn.cursor() as cur:
                _assign_agent(agent_symbol, role, system_symbol, cur)
                for ship in data["ships"]:
                    if len(system2market[system_symbol]) != 0:
                        _assign_ship(
                            ship["symbol"], system_symbol, system2market, pname, cur
                        )
            await sleep(0)  # give other processes a turn


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


def _get_system2market(faction2system, request):
    """
    This function wraps __get_system2market(), storing the output in table spymaster.
    """
    key = hash(json.dumps(faction2system, sort_keys=True))
    with connect("dbname=st2 user=postgres") as conn, conn.cursor() as cur:
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
            system2market = __get_system2market(faction2system, request)
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


def __get_system2market(faction2system, request):
    system2market = {}
    system2faction = {v: k for (k, vs) in faction2system.items() for v in vs}
    for system_symbol in system2faction:
        system2market[system_symbol] = []
        # sort the markets by proximity to the center (ascending)
        # (central waypoints are faster to reach)
        system = System(system_symbol, request)
        source = list(system.waypoints_with(type="ENGINEERED_ASTEROID"))[0]
        for waypoint_symbol in system.waypoints_sort(source, list(system.markets)):
            wp_type = "shipyard" if waypoint_symbol in system.shipyards else "market"
            key = (wp_type, waypoint_symbol)
            system2market[system_symbol].append(key)
    return system2market


def _load_assigned_ships(system2market, role, pname):
    """
    Remove markets from system2market that are already probed.
    """
    with connect("dbname=st2 user=postgres") as conn, conn.cursor() as cur:
        tasks = cur.execute(
            """
            SELECT symbol, current
            FROM tasks
            WHERE "agentSymbol" IN (
                  SELECT symbol 
                  FROM agents 
                  WHERE role = %s
            ) AND pname = %s
            """,
            [role, pname],
        ).fetchall()
    for ship_symbol, task in tasks:
        if task and task.startswith("probe "):
            wp_type, waypoint_symbol = task.split(" ")[1:]
            system_symbol = waypoint_symbol.rsplit("-", 1)[0]
            key = (wp_type, waypoint_symbol)
            # in case multiple ships have been assigned
            if key in system2market.get(system_symbol, []):
                system2market[system_symbol].remove(key)


def _load_unassigned_ships(system2market, role, pname):
    """
    Check if there are spare ships to spy with.

    - Ships from an agent with role "spy" should always have a current task.
      If not, then the ship is no longer in use.
    - Ships from an agent with role None are not in use.
    """
    with connect("dbname=st2 user=postgres") as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT symbol, agentSymbol, nav
            FROM ships
            WHERE symbol IN (
                SELECT symbol
                FROM tasks
                WHERE current IS NOT DISTINCT FROM %s
            )
            AND "agentSymbol" IN (
                SELECT symbol
                FROM agents
                WHERE role IS NOT DISTINCT FROM %s
                OR role = %s
            )
            """,
            [None, None, "spy"],
        )
        for ship_symbol, agent_symbol, nav in cur.fetchall():
            system_symbol = nav["systemSymbol"]
            if len(system2market[system_symbol]) != 0:
                _assign_agent(agent_symbol, role, system_symbol, cur)
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
    # frigates can fly to the furthest waypoints, probes to the nearest
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
