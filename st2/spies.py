from psycopg import connect

from st2.agent import register_random_agent
from st2.logging import logger

DEBUG = False


def spymaster(request, priority=3):
    # get a dict of start systems per faction
    faction2start_system2agent = {}
    faction2hq = {}
    with connect("dbname=st2 user=postgres") as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT systemSymbol, faction
            FROM waypoints 
            WHERE type = 'ENGINEERED_ASTEROID'
            EXCEPT 
            SELECT headquarters, symbol
            FROM factions
            ORDER BY faction, systemSymbol
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
    with connect("dbname=st2 user=postgres") as conn, conn.cursor() as cur:
        for faction in faction2start_system2agent:
            if DEBUG:
                n = len(faction2start_system2agent[faction])
                logger.debug(f"{faction} has {n} start systems: ")

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
            for agent_symbol, token, _, _, system_symbol in cur.fetchall():
                faction2start_system2agent[faction][system_symbol] = (
                    agent_symbol,
                    token,
                )
                if DEBUG:
                    if system_symbol == faction2hq[faction]:
                        logger.debug(f" - {system_symbol} (faction HQ)")
                    else:
                        logger.debug(f" - {system_symbol}")

            # Register agents
            while None in faction2start_system2agent[faction].values():
                data = register_random_agent(request, priority, faction)
                agent_symbol = data["agent"]["symbol"]
                token = data["token"]
                system_symbol = data["ship"]["nav"]["systemSymbol"]
                if faction2start_system2agent[faction].get(system_symbol):
                    continue

                cur.execute(
                    """
                    INSERT INTO agents
                    (symbol, token, role, faction, other)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (agent_symbol, token, role, faction, system_symbol),
                )
                for ship in request.get("my/ships", token=token, priority=priority)[
                    "data"
                ]:
                    insert_ship(ship, agent_symbol, cur)
                conn.commit()
                faction2start_system2agent[faction][system_symbol] = (
                    agent_symbol,
                    token,
                )
                if DEBUG:
                    if system_symbol == faction2hq[faction]:
                        logger.debug(f" - {system_symbol} (faction HQ)")
                    else:
                        logger.debug(f" - {system_symbol}")

    for faction in faction2start_system2agent:
        for system_symbol, (agent_symbol, token) in faction2start_system2agent[
            faction
        ].items():
            pass  # TODO: insert probes into each MARKETPLACE & start collecting data

            with connect("dbname=st2 user=postgres") as conn, conn.cursor() as cur:
                # identify all markets
                cur.execute(
                    """
                    SELECT symbol, traits
                    FROM waypoints
                    WHERE systemSymbol = %s
                    AND %s = ANY(traits)
                    """,
                    (system_symbol, "MARKETPLACE"),
                )
                ret = cur.fetchall()
                markets = [wp[0] for wp in ret]

                # identify all and shipyards that sell probes
                shipyards = []
                for wp, traits in ret:  # all shipyards are also markets
                    if "SHIPYARD" not in traits:
                        continue
                    cur.execute(
                        "SELECT shipTypes FROM shipyards WHERE symbol = %s", (wp,)
                    )
                    ship_types = cur.fetchone()[0]
                    if "SHIP_PROBE" in ship_types:
                        shipyards.append(wp)

                cur.execute(
                    """
                    SELECT *
                    FROM ships
                    WHERE agentSymbol = %s
                    """,
                    (agent_symbol,),
                )
                ret = cur.fetchall()
                for ship in ret:
                    ship_symbol = ship[0]
                    cur.execute(
                        """
                        SELECT *
                        FROM tasks
                        WHERE symbol = %s
                        """,
                        (ship_symbol,),
                    )
                    _, current, queued, cancel, pid = cur.fetchone()
                    if current is None:
                        # idle, unmanaged ship
                        cur.execute(
                            """
                            UPDATE tasks
                            SET queued = %s
                            WHERE symbol = %s
                            """,
                            (
                                task,
                                ship_symbol,
                            ),
                        )
                    elif check_pid(pid):
                        # busy, managed ship
                        continue
                    else:
                        # busy, unmanaged ship
                        cur.execute(
                            """
                            UPDATE tasks
                            SET current = %s, queued = %s, cancel = %s, pid = %s
                            WHERE symbol = %s
                            """,
                            (
                                None,
                                task,
                                False,
                                None,
                                ship_symbol,
                            ),
                        )

            # if starting ships are not logged:
            #     fly starting frigate to second shipyard with probes
            #     log starting ships to shipyards with probes

            # for wp in markets:
            #     check log for probe
            #     if probe is None:
            #         buy cheapest probe
            #         log (probe, wp) in db
            #     if ship is not at its market:
            #         navigate to the market
            #     collect data on timer


def insert_ship(ship, agent_symbol, cur):
    cur.execute(
        """
        INSERT INTO ships
        (symbol, agentSymbol, nav, crew, fuel, cooldown, frame,
         reactor, engine, modules, mounts, registration, cargo)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            ship["symbol"],
            agent_symbol,
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
        INSERT INTO tasks (symbol, agentSymbol, current, queued, cancel, pname, pid) 
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        (ship["symbol"], agent_symbol, None, None, False, None, None),
    )
