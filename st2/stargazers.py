import psycopg
from psycopg.types.json import Jsonb

from st2.agent import api_agent
from st2.logging import logger

DEBUG = False


def astronomer(request):
    token = api_agent(request)[1]
    with psycopg.connect(f"dbname=st2 user=postgres") as conn, conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS astronomer 
            (
                total integer PRIMARY KEY,
                current integer,
                page integer
            )
            """
        )
        cur.execute("SELECT * FROM astronomer")
        ret = cur.fetchone()
        if ret is None:
            total = request.get(
                endpoint="systems",
                priority=3,
                token=token,
                params={"page": 1, "limit": 1},
            )["meta"]["total"]
            current = 0
            page = 1
            cur.execute(
                """
                INSERT INTO astronomer
                (total, current, page)
                VALUES (%s, %s, %s)
                """,
                (total, current, page),
            )
            conn.commit()
        else:
            total, current, page = ret

        if current == total:
            return

        logger.info(f"The Astronomer has found {total:_} stars in the night sky")
        while current < total:
            if DEBUG:
                logger.debug(f"Processing page {page:_}")
            systems = request.get(
                endpoint="systems",
                priority=3,
                token=token,
                params={"page": page, "limit": 20},
            )
            for s in systems["data"]:
                system_symbol = s["symbol"]
                cur.execute(
                    """
                    INSERT INTO systems 
                    (symbol, type, x, y)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (symbol) DO NOTHING
                    """,
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
                        """
                        INSERT INTO waypoints
                        (symbol, systemSymbol, type, x, y, orbits, orbitals, traits, chart, faction, isUnderConstruction)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (symbol) DO NOTHING
                        """,
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
                        """
                        INSERT INTO system_waypoints
                        (systemSymbol, waypointSymbol)
                        VALUES (%s, %s)
                        ON CONFLICT (systemSymbol, waypointSymbol) DO NOTHING
                        """,
                        (system_symbol, waypoints_symbol),
                    )
                current += 1
            page += 1
            # log progress
            cur.execute(
                """
                UPDATE astronomer
                SET current = %s, page = %s
                WHERE total = %s
                """,
                (current, page, total),
            )
            conn.commit()
    logger.info(f"The Astronomer has completed its chart!")


def cartographer(request):
    with psycopg.connect(f"dbname=st2 user=postgres") as conn, conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS cartographer 
            (
                index text PRIMARY KEY,
                total integer,
                current integer
            )
            """
        )
        conn.commit()

    def _chart_systems(index, query):
        with psycopg.connect(f"dbname=st2 user=postgres") as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM cartographer WHERE index = %s",
                (index,),
            )
            ret = cur.fetchone()
            if ret is None:
                current = 0
                cur.execute(query)
                total = len(cur.fetchall())
                cur.execute(
                    """
                    INSERT INTO cartographer
                    (index, total, current)
                    VALUES (%s, %s, %s)
                    """,
                    (index, total, current),
                )
                conn.commit()
            else:
                total, current = ret[1:]

            if current == total:
                return

            token = api_agent(request)[1]
            unknown_traits = {"CRUSHING_GRAVITY", "JOVIAN", "UNDER_CONSTRUCTION"}
            logger.info(
                f"The Cartographer has found {total-current:_} {index} to chart"
            )
            cur.execute(query)
            ret = cur.fetchall()
            while current != total:
                if DEBUG:
                    logger.debug(f"Processing {current+1:_}/{total:_}")
                system_symbol = ret[current][0]
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
                            """
                            INSERT INTO waypoints
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

                        if traits in [["UNCHARTED"], []]:
                            continue

                        if wp["type"] == "JUMP_GATE":
                            _chart_gate(wp, token, cur)
                        if "MARKETPLACE" in traits:
                            _chart_market(wp, token, cur)
                        if "SHIPYARD" in traits:
                            _chart_shipyard(wp, token, cur)

                        # store traits of charted waypoints
                        for trait in traits:
                            cur.execute(
                                """
                                INSERT INTO waypoint_traits
                                (waypointSymbol, traitSymbol) 
                                VALUES (%s, %s)
                                ON CONFLICT (waypointSymbol, traitSymbol) DO NOTHING
                                """,
                                (wp["symbol"], trait),
                            )

                        # store unknown traits
                        for trait in set(traits) & unknown_traits:
                            t = [t for t in wp["traits"] if t["symbol"] == trait][0]
                            description = t["description"].replace("'", "''")
                            cur.execute(
                                """
                                INSERT INTO traits_waypoint
                                (symbol, name, description) 
                                VALUES (%s, %s, %s)
                                """,
                                (t["symbol"], t["name"], description),
                            )
                            logger.info(
                                f"The Cartographer has discovered a new trait: {t['symbol']}!"
                            )
                current += 1
                # log progress
                cur.execute(
                    """
                    UPDATE cartographer
                    SET current = %s
                    WHERE index = %s
                    """,
                    (current, index),
                )
                conn.commit()

    def _chart_gate(wp, token, cur):
        connections = request.get(
            endpoint=f"systems/{wp['systemSymbol']}/waypoints/{wp['symbol']}/jump-gate",
            priority=3,
            token=token,
        )["data"]["connections"]
        cur.execute(
            """
            INSERT INTO jump_gates
            (symbol, connections)
            VALUES (%s, %s)
            ON CONFLICT (symbol) DO NOTHING
            """,
            (
                wp["symbol"],
                connections,
            ),
        )

    def _chart_market(wp, token, cur):
        ret = request.get(
            endpoint=f"systems/{wp['systemSymbol']}/waypoints/{wp['symbol']}/market",
            priority=3,
            token=token,
        )["data"]
        cur.execute(
            """
            INSERT INTO markets
            (symbol, imports, exports, exchange)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (symbol) DO NOTHING
            """,
            (
                wp["symbol"],
                [good["symbol"] for good in ret["imports"]],
                [good["symbol"] for good in ret["exports"]],
                [good["symbol"] for good in ret["exchange"]],
            ),
        )

    def _chart_shipyard(wp, token, cur):
        ret = request.get(
            endpoint=f"systems/{wp['systemSymbol']}/waypoints/{wp['symbol']}/shipyard",
            priority=3,
            token=token,
        )["data"]
        cur.execute(
            """
            INSERT INTO shipyards
            (symbol, shipTypes, modificationsFee)
            VALUES (%s, %s, %s)
            ON CONFLICT (symbol) DO NOTHING
            """,
            (
                wp["symbol"],
                [ship["type"] for ship in ret["shipTypes"]],
                ret["modificationsFee"],
            ),
        )

    # start systems (fully charted by default)
    index = "start systems"
    query = """
    SELECT systemSymbol 
    FROM waypoints 
    WHERE type = 'ENGINEERED_ASTEROID' 
    ORDER BY systemSymbol 
    """
    _chart_systems(index, query)

    # gate systems (can be charted by other players)
    index = "gate systems"
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

    logger.info(f"The Cartographer has completed its chart!")

    # TODO: run the cartographer every n hours for (partially) on uncharted systems
