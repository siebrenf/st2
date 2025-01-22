from psycopg import connect

from st2.agent import register_random_agent
from st2.logging import logger
from st2.system import System

DEBUG = False


def spymaster(request, priority=3):
    """
    Can be used after all start systems have been charted by the cartographer.
    """
    # get a dict of start systems per faction
    faction2start_system2agent = {}
    faction2hq = {}
    with connect("dbname=st2 user=postgres") as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT "systemSymbol", "faction"
                FROM "waypoints"
                WHERE type = 'ENGINEERED_ASTEROID'
                EXCEPT
                SELECT "headquarters", "symbol"
                FROM "factions"
                ORDER BY "faction", "systemSymbol"
                """
            )
            for system, faction in cur.fetchall():
                if faction not in faction2start_system2agent:
                    faction2start_system2agent[faction] = {}
                if system not in faction2start_system2agent[faction]:
                    faction2start_system2agent[faction][system] = None

            if DEBUG:
                cur.execute(
                    """
                    SELECT headquarters, symbol
                    FROM factions
                    ORDER BY symbol
                    """
                )
                for system, faction in cur.fetchall():
                    faction2hq[faction] = system

    # get agents for each start system per faction
    role = "spy"
    with connect("dbname=st2 user=postgres") as conn:
        with conn.cursor() as cur:
            for faction in faction2start_system2agent:
                if DEBUG:
                    n = len(faction2start_system2agent[faction])
                    logger.debug(
                        f"{faction} has {n} start systems (HQ system excluded): "
                    )

                # Load agents
                cur.execute(
                    """
                    SELECT *
                    FROM agents 
                    WHERE (role, faction) = (%s, %s)
                    ORDER BY other
                    """,
                    (role, faction),
                )
                for agent_symbol, _, _, _, system_symbol in cur.fetchall():
                    faction2start_system2agent[faction][system_symbol] = agent_symbol
                    if DEBUG:
                        if system_symbol == faction2hq[faction]:
                            logger.debug(f" - {system_symbol} (faction HQ)")
                        else:
                            logger.debug(f" - {system_symbol}")

                # Register agents
                while None in faction2start_system2agent[faction].values():
                    data = register_random_agent(request, priority, faction)
                    agent_symbol = data["agent"]["symbol"]
                    system_symbol = data["ship"]["nav"]["systemSymbol"]
                    if faction2start_system2agent[faction].get(system_symbol):
                        continue

                    cur.execute(
                        """
                        UPDATE agents
                        SET role = %s,
                            other = %s
                        WHERE symbol = %s
                        """,
                        (role, system_symbol, agent_symbol),
                    )
                    conn.commit()
                    faction2start_system2agent[faction][system_symbol] = agent_symbol
                    if DEBUG:
                        if system_symbol == faction2hq[faction]:
                            logger.debug(f" - {system_symbol} (faction HQ)")
                        else:
                            logger.debug(f" - {system_symbol}")

    # (Re)start the seeding & probing of each system
    pname = "probes"  # TODO: where to start/host the probe/seed process(?)
    system = None
    with connect("dbname=st2 user=postgres") as conn:
        with conn.cursor() as cur:
            for faction in faction2start_system2agent:
                for system_symbol, agent_symbol in faction2start_system2agent[
                    faction
                ].items():
                    commit = False  # commit per system
                    cur.execute(
                        """
                        SELECT *
                        FROM tasks
                        WHERE "agentSymbol" = %s
                        ORDER BY "symbol"
                        """,
                        (agent_symbol,),
                    )
                    for ship_symbol, _, current, _, _, _, _ in cur.fetchall():
                        task = str(current).split(" ")
                        if task[0] in ["probe", "seed"]:
                            continue
                        elif task[0] != "None":
                            raise ValueError(
                                f"Task not recognized: {ship_symbol=}, {current=}"
                            )

                        commit = True
                        if ship_symbol == f"{agent_symbol}-1":
                            # TODO: count the number of probes & markets?
                            task = f"seed {pname} {system_symbol}"
                            cur.execute(
                                """
                                UPDATE tasks
                                SET current = %s,
                                    pname = %s
                                WHERE "symbol" = %s
                                """,
                                [task, pname, ship_symbol],
                            )
                        elif ship_symbol == f"{agent_symbol}-2":
                            cur.execute(
                                """
                                SELECT nav
                                FROM ships
                                WHERE "symbol" = %s
                                """,
                                [ship_symbol],
                            )
                            waypoint_symbol = cur.fetchone()[0]["waypointSymbol"]
                            if system is None or system.symbol != system_symbol:
                                system = System(system_symbol, request)
                            wp_type = "market"
                            if waypoint_symbol in system.shipyards:
                                wp_type = "shipyard"
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
                        else:
                            # this happens if a probe is bought, but not assigned a waypoint
                            logger.error(
                                f"Ship not recognized: {ship_symbol=}, {current=}"
                            )
                            continue

                    if commit:
                        conn.commit()
