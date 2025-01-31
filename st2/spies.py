from psycopg import connect

from st2.agent import register_random_agent
from st2.logging import logger
from st2.system import System

DEBUG = False


def spymaster(request, priority=3):
    """
    Can be used after all start systems have been charted by the cartographer.
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
        logger.debug(f"{remaining:_}/{total:_} markets probed by the Spymaster")
    if remaining == 0:
        return

    logger.info(f"The Spymaster has found {total:_} markets in start systems")
    # register new agents to assign
    for faction, systems in faction2system.items():
        while remaining := [system for system in systems if len(system2market[system]) != 0]:
            if DEBUG:
                n = sum([len(system2market[system]) for system in remaining])
                logger.debug(
                    f"{len(remaining): >2} {faction} systems remaining ({n: >3} markets)"
                )
            data = register_random_agent(request, priority, faction)
            agent_symbol = data["agent"]["symbol"]
            system_symbol = data["ship"]["nav"]["systemSymbol"]
            if len(system2market[system_symbol]) == 0:
                continue

            with connect("dbname=st2 user=postgres") as conn:
                with conn.cursor() as cur:
                    _assign_agent(agent_symbol, role, system_symbol, cur)
                    for ship_symbol in [f"{agent_symbol}-1", f"{agent_symbol}-2"]:
                        _assign_ship(ship_symbol, system_symbol, system2market, pname, cur)


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
                ["SHIP_EXPLORER"]
            )
            for system, faction in cur.fetchall():
                if faction not in faction2system:
                    faction2system[faction] = []
                if system not in faction2system[faction]:
                    faction2system[faction].append(system)
    return faction2system


def _get_system2market(faction2system):
    # TODO: cache (lru, db?)
    system2market = {}
    system2faction = {v: k for (k, vs) in faction2system.items() for v in vs}
    for system_symbol in system2faction:
        system2market[system_symbol] = []
        # sort the markets by proximity to the center (ascending)
        # (central waypoints are faster to reach)
        system = System(system_symbol, None)
        source = list(system.waypoints_with(type="ENGINEERED_ASTEROID"))[0]
        for waypoint_symbol, dist in system.waypoints_sort(source, list(system.markets)):
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
            for ship_symbol, agent_symbol, task, current_pname in cur.fetchall():
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


# def spymaster(request, priority=3):
#     """
#     Can be used after all start systems have been charted by the cartographer.
#     """
#     # get a dict of start systems per faction
#     faction2start_system2agent = {}
#     faction2hq = {}
#     with connect("dbname=st2 user=postgres") as conn:
#         with conn.cursor() as cur:
#             cur.execute(
#                 """
#                 SELECT "systemSymbol", "faction"
#                 FROM "waypoints"
#                 WHERE type = 'ENGINEERED_ASTEROID'
#                 EXCEPT
#                 SELECT "headquarters", "symbol"
#                 FROM "factions"
#                 ORDER BY "faction", "systemSymbol"
#                 """
#             )
#             for system, faction in cur.fetchall():
#                 if faction not in faction2start_system2agent:
#                     faction2start_system2agent[faction] = {}
#                 if system not in faction2start_system2agent[faction]:
#                     faction2start_system2agent[faction][system] = None
#
#             if DEBUG:
#                 cur.execute(
#                     """
#                     SELECT headquarters, symbol
#                     FROM factions
#                     ORDER BY symbol
#                     """
#                 )
#                 for system, faction in cur.fetchall():
#                     faction2hq[faction] = system
#
#     # get agents for each start system per faction
#     role = "spy"
#     with connect("dbname=st2 user=postgres") as conn:
#         with conn.cursor() as cur:
#             for faction in faction2start_system2agent:
#                 if DEBUG:
#                     n = len(faction2start_system2agent[faction])
#                     logger.debug(
#                         f"{faction} has {n} start systems (HQ system excluded): "
#                     )
#
#                 # Load agents
#                 cur.execute(
#                     """
#                     SELECT *
#                     FROM agents
#                     WHERE (role, faction) = (%s, %s)
#                     ORDER BY other
#                     """,
#                     (role, faction),
#                 )
#                 for agent_symbol, _, _, _, system_symbol in cur.fetchall():
#                     faction2start_system2agent[faction][system_symbol] = agent_symbol
#                     if DEBUG:
#                         if system_symbol == faction2hq[faction]:
#                             logger.debug(f" - {system_symbol} (faction HQ)")
#                         else:
#                             logger.debug(f" - {system_symbol}")
#
#                 # Register agents
#                 while None in faction2start_system2agent[faction].values():
#                     data = register_random_agent(request, priority, faction)
#                     agent_symbol = data["agent"]["symbol"]
#                     system_symbol = data["ship"]["nav"]["systemSymbol"]
#                     if faction2start_system2agent[faction].get(system_symbol):
#                         continue
#
#                     cur.execute(
#                         """
#                         UPDATE agents
#                         SET role = %s,
#                             other = %s
#                         WHERE symbol = %s
#                         """,
#                         (role, system_symbol, agent_symbol),
#                     )
#                     conn.commit()
#                     faction2start_system2agent[faction][system_symbol] = agent_symbol
#                     if DEBUG:
#                         if system_symbol == faction2hq[faction]:
#                             logger.debug(f" - {system_symbol} (faction HQ)")
#                         else:
#                             logger.debug(f" - {system_symbol}")
#
#     # (Re)start the seeding & probing of each system
#     pname = "probes"
#     system = None
#     with connect("dbname=st2 user=postgres") as conn:
#         with conn.cursor() as cur:
#             for faction in faction2start_system2agent:
#                 for system_symbol, agent_symbol in faction2start_system2agent[
#                     faction
#                 ].items():
#                     commit = False  # commit per system
#                     cur.execute(
#                         """
#                         SELECT *
#                         FROM tasks
#                         WHERE "agentSymbol" = %s
#                         ORDER BY "symbol"
#                         """,
#                         (agent_symbol,),
#                     )
#                     for ship_symbol, _, current, _, _, _, _ in cur.fetchall():
#                         task = str(current).split(" ")
#                         if task[0] in ["probe", "seed"]:
#                             continue
#                         elif task[0] != "None":
#                             raise ValueError(
#                                 f"Task not recognized: {ship_symbol=}, {current=}"
#                             )
#
#                         commit = True
#                         if ship_symbol == f"{agent_symbol}-1":
#                             task = f"seed {pname} {system_symbol}"
#                             cur.execute(
#                                 """
#                                 UPDATE tasks
#                                 SET current = %s,
#                                     pname = %s
#                                 WHERE "symbol" = %s
#                                 """,
#                                 [task, pname, ship_symbol],
#                             )
#                         elif ship_symbol == f"{agent_symbol}-2":
#                             cur.execute(
#                                 """
#                                 SELECT nav
#                                 FROM ships
#                                 WHERE "symbol" = %s
#                                 """,
#                                 [ship_symbol],
#                             )
#                             waypoint_symbol = cur.fetchone()[0]["waypointSymbol"]
#                             if system is None or system.symbol != system_symbol:
#                                 system = System(system_symbol, request)
#                             wp_type = "market"
#                             if waypoint_symbol in system.shipyards:
#                                 wp_type = "shipyard"
#                             task = f"probe {wp_type} {waypoint_symbol}"
#                             cur.execute(
#                                 """
#                                 UPDATE tasks
#                                 SET current = %s,
#                                     pname = %s
#                                 WHERE "symbol" = %s
#                                 """,
#                                 [task, pname, ship_symbol],
#                             )
#                         else:
#                             # this happens if a probe is bought, but not assigned a waypoint
#                             logger.error(
#                                 f"Ship not recognized: {ship_symbol=}, {current=}"
#                             )
#                             continue
#
#                     if commit:
#                         conn.commit()
