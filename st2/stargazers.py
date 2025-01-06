import psycopg
from psycopg.types.json import Jsonb

from st2.agent import api_agent
from st2.logging import logger


def astronomer(request):
    token = api_agent(request)[1]
    total, current, page = db_astronomer_init(request, token)
    if current == total:
        return

    logger.info(f"The Astronomer has found {total:_} stars in the night sky")
    with psycopg.connect(f"dbname=st2 user=postgres") as conn, conn.cursor() as cur:
        while current < total:
            # logger.debug(f'Processing page {page: >3}')
            systems = request.get(
                endpoint="systems",
                priority=3,
                token=token,
                params={"page": page, "limit": 20},
            )
            for s in systems["data"]:
                system_symbol = s["symbol"]
                cur.execute(
                    """INSERT INTO systems 
                    (symbol, type, x, y)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (symbol) DO NOTHING""",
                    (system_symbol, s["type"], s["x"], s["y"]),
                )

                # update waypoints (with very limited fields)
                waypoints = {}
                for wp in s["waypoints"]:
                    waypoints[wp["symbol"]] = wp
                for waypoints_symbol in sorted(waypoints):
                    wp = waypoints[waypoints_symbol]
                    orbits = wp.get("orbits")
                    orbitals = [o["symbol"] for o in wp["orbitals"]]
                    cur.execute(
                        """INSERT INTO waypoints
                        (symbol, systemSymbol, type, x, y, orbits, orbitals, traits, chart, faction, isUnderConstruction)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (symbol) DO NOTHING""",
                        (
                            waypoints_symbol,
                            system_symbol,
                            wp["type"],
                            wp["x"],
                            wp["y"],
                            orbits,
                            orbitals,
                            None,
                            None,
                            None,
                            None,
                        ),
                    )
                    cur.execute(
                        """INSERT INTO system_waypoints
                        (systemSymbol, waypointSymbol)
                        VALUES (%s, %s)
                        ON CONFLICT (systemSymbol, waypointSymbol) DO NOTHING""",
                        (system_symbol, waypoints_symbol),
                    )
                current += 1
            page += 1
            # log progress
            cur.execute(
                """UPDATE astronomer
                SET current = %s, page = %s
                WHERE total = %s""",
                (current, page, total),
            )
            conn.commit()
    logger.info(f"The Astronomer has completed its chart!")


def db_astronomer_init(request, token):
    """Track the astronomers' progress in a DB table"""
    with psycopg.connect(f"dbname=st2 user=postgres") as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
        """
        )
        tables = [row[0] for row in cur.fetchall()]

        if "astronomer" not in tables:
            cur.execute(
                """
                CREATE TABLE astronomer (
                    total integer PRIMARY KEY,
                    current integer,
                    page integer)
                """
            )

            total = request.get(
                endpoint="systems",
                priority=3,
                token=token,
                params={"page": 1, "limit": 1},
            )["meta"]["total"]
            current = 0
            page = 1
            cur.execute(
                """INSERT INTO astronomer
                (total, current, page)
                VALUES (%s, %s, %s)""",
                (total, current, page),
            )
            conn.commit()
        else:
            cur.execute("SELECT * FROM astronomer")
            total, current, page = cur.fetchone()

        return total, current, page


def cartographer(request):
    token = api_agent(request)[1]
    md = db_cartographer_init()

    def _chart_systems(index, query):
        total = md[index]["total"]
        current = md[index]["current"]
        if current == total:
            return

        unknown_traits = {"CRUSHING_GRAVITY", "JOVIAN", "UNDER_CONSTRUCTION"}
        logger.info(f"The Cartographer has found {total:_} {index}")
        with psycopg.connect(f"dbname=st2 user=postgres") as conn, conn.cursor() as cur:
            cur.execute(query)
            ret = cur.fetchall()
            while current != total:
                # logger.debug(f"Processing {index} {current+1:_}/{total:_}")
                system_symbol = ret[current][1]
                for ret2 in request.get_all(
                    endpoint=f"systems/{system_symbol}/waypoints",
                    priority=3,
                    token=token,
                ):
                    for wp in ret2["data"]:
                        orbits = wp.get("orbits")
                        orbitals = [o["symbol"] for o in wp["orbitals"]]
                        traits = [t["symbol"] for t in wp["traits"]]
                        chart = Jsonb(wp.get("chart"))
                        faction = wp.get("faction", {}).get("symbol")
                        # insert the waypoint in the table
                        #   or update the values that may have been updated
                        cur.execute(
                            """INSERT INTO waypoints
                            (symbol, systemSymbol, type, x, y, orbits, orbitals, traits, chart, faction, isUnderConstruction)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (symbol) DO UPDATE SET
                            traits = EXCLUDED.traits, 
                            chart = EXCLUDED.chart, 
                            faction = EXCLUDED.faction,
                            isUnderConstruction = EXCLUDED.isUnderConstruction 
                            """,
                            (
                                wp["symbol"],
                                system_symbol,
                                wp["type"],
                                wp["x"],
                                wp["y"],
                                orbits,
                                orbitals,
                                traits,
                                chart,
                                faction,
                                wp["isUnderConstruction"],
                            ),
                        )

                        # TODO: remove the UNCHARTED trait when >1 trait has been found
                        for trait in traits:
                            cur.execute(
                                """INSERT INTO waypoint_traits
                                (waypointSymbol, traitSymbol) 
                                VALUES (%s, %s)
                                ON CONFLICT (waypointSymbol, traitSymbol) DO NOTHING""",
                                (wp["symbol"], trait),
                            )

                        # only bother with the unknown traits
                        for trait in set(traits) & unknown_traits:
                            t = [t for t in wp["traits"] if t["symbol"] == trait][0]
                            description = t["description"].replace("'", "''")
                            cur.execute(
                                """INSERT INTO traits_waypoint
                                (symbol, name, description) 
                                VALUES (%s, %s, %s)""",
                                (t["symbol"], t["name"], description),
                            )
                            unknown_traits -= trait
                            logger.info(
                                f"The Cartographer has discovered a new trait: {t['symbol']}!"
                            )
                current += 1
                # log progress
                cur.execute(
                    """UPDATE cartographer
                    SET current = %s
                    WHERE index = %s""",
                    (current, index),
                )
                conn.commit()

    # start systems (fully charted by default, so only do once)
    index = "start systems"
    query = "SELECT * FROM waypoints WHERE type = 'ENGINEERED_ASTEROID' ORDER BY symbol"
    _chart_systems(index, query)

    # TODO: update totals & currents

    # gate systems (may be charted by other players)
    index = "gate systems"
    # query = "SELECT * FROM waypoints WHERE type = 'JUMP_GATE' ORDER BY symbol"
    query = """
    SELECT systemSymbol 
    FROM waypoints 
    WHERE type = 'JUMP_GATE'
    EXCEPT
    SELECT systemSymbol 
    FROM waypoints 
    WHERE type = 'ENGINEERED_ASTEROID'
    ORDER BY systemSymbol
    """
    _chart_systems(index, query)

    # all systems (not sure if we should chart these)
    index = "all systems"
    query = """
    SELECT symbol 
    FROM systems 
    EXCEPT
    SELECT systemSymbol 
    FROM waypoints 
    WHERE type = 'ENGINEERED_ASTEROID'
    ORDER BY symbol
    """
    _chart_systems(index, query)

    # TODO: rerun the cartographer every n hours


def db_cartographer_init():
    """Track the cartographer' progress in a DB table"""
    with psycopg.connect(f"dbname=st2 user=postgres") as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
        """
        )
        tables = [row[0] for row in cur.fetchall()]

        md = {}
        if "cartographer" not in tables:
            cur.execute(
                """
                CREATE TABLE cartographer (
                    index text PRIMARY KEY,
                    total integer,
                    current integer)
                """
            )

            def _update_md(index, query):
                """Update the metadata for the table and the local dict"""
                cur.execute(query)
                total = cur.fetchone()[0]
                current = 0
                cur.execute(
                    """INSERT INTO cartographer
                    (index, total, current)
                    VALUES (%s, %s, %s)""",
                    (index, total, current),
                )
                md[index] = {
                    "total": total,
                    "current": current,
                }

            # start systems (fully charted by default, so only do once)
            index = "start systems"
            query = "SELECT count(*) AS exact_count FROM waypoints WHERE type = 'ENGINEERED_ASTEROID'"
            _update_md(index, query)

            # systems with jump gates (may be charted by other players)
            index = "gate systems"
            query = """
            SELECT COUNT(*)
            FROM (
                SELECT systemSymbol 
                FROM waypoints 
                WHERE type = 'JUMP_GATE'
                EXCEPT
                SELECT systemSymbol 
                FROM waypoints 
                WHERE type = 'ENGINEERED_ASTEROID'
            ) AS result
            """
            _update_md(index, query)

            # TODO: exclude fully charted systems
            # all systems (not sure if we should chart these)
            index = "all systems"
            # query = "SELECT count(*) AS exact_count FROM systems"
            query = """
            SELECT COUNT(*)
            FROM (
                SELECT symbol 
                FROM systems 
                EXCEPT
                SELECT systemSymbol 
                FROM waypoints 
                WHERE type = 'ENGINEERED_ASTEROID'
            ) AS result
            """
            _update_md(index, query)

            conn.commit()
        else:
            cur.execute("SELECT * FROM cartographer")
            for index, total, current in cur.fetchall():
                md[index] = {
                    "total": total,
                    "current": current,
                }

        return md
