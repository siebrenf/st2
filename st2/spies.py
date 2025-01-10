import psycopg

from st2.agent import register_random_agent

DEBUG = False


def espionage(request, priority=3):
    # get a dict of start systems per faction
    faction2start_system2agent = {}
    with psycopg.connect(f"dbname=st2 user=postgres") as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT systemSymbol, faction
            FROM waypoints 
            WHERE type = 'ENGINEERED_ASTEROID' 
            ORDER BY faction
            """
        )
        for system, faction in cur.fetchall():
            if faction not in faction2start_system2agent:
                faction2start_system2agent[faction] = {}
            if system not in faction2start_system2agent[faction]:
                faction2start_system2agent[faction][system] = None

    # get agents for each start system
    role = "spy"
    with psycopg.connect(f"dbname=st2 user=postgres") as conn, conn.cursor() as cur:
        for faction in faction2start_system2agent:
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

            # Register agents
            while None in faction2start_system2agent[faction].values():
                data = register_random_agent(request, priority, faction)
                agent_symbol = data["agent"]["symbol"]
                system_symbol = data["ship"]["nav"]["systemSymbol"]
                if faction2start_system2agent[faction][system_symbol] is not None:
                    continue

                cur.execute(
                    """
                    INSERT INTO agents
                    (symbol, token, role, faction, other)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (agent_symbol, data["token"], role, faction, system_symbol),
                )
                conn.commit()
                faction2start_system2agent[faction][system_symbol] = (
                    agent_symbol,
                    token,
                )

    for faction in faction2start_system2agent:
        for system_symbol, (agent_symbol, token) in faction2start_system2agent[faction].items():
            pass  # TODO: insert probes into each MARKETPLACE & start collecting data

            # identify all markets

            # identify all shipyards

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


