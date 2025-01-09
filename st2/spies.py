import psycopg

from st2.agent import register_random_agent
from st2.logging import logger

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
            missing = [
                system
                for (system, agent) in faction2start_system2agent[faction]
                if agent is None
            ]
            while missing:
                data = register_random_agent(request, priority, faction)
                agent_symbol = data["agent"]["symbol"]
                system_symbol = data["ship"]["nav"]["systemSymbol"]
                if system_symbol not in missing:
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
                missing.remove(system_symbol)
                faction2start_system2agent[faction][system_symbol] = (
                    agent_symbol,
                    token,
                )

    for faction in faction2start_system2agent:
        for agent_symbol, token in faction2start_system2agent[faction].values():
            pass  # TODO: insert probes into each MARKETPLACE & start collecting data
