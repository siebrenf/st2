import math

from psycopg import connect
from psycopg.types.json import Jsonb

from st2.agent import api_agent
from st2.db.static.traits import TRAITS_WAYPOINT
from st2.logging import logger

DEBUG = False


def astronomer(request, priority=3):
    token = api_agent(request, priority)[1]
    with connect("dbname=st2 user=postgres") as conn, conn.cursor() as cur:
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
                priority=priority,
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
        total_pages = math.ceil(total / 20)
        while current < total:
            if DEBUG:
                logger.debug(f"Processing page {page:_}/{total_pages}")
            systems = request.get(
                endpoint="systems",
                priority=priority,
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
                        ("symbol", "systemSymbol", "type", "x", "y", "orbits", "orbitals")
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT ("symbol") DO NOTHING
                        """,
                        (
                            waypoints_symbol,
                            system_symbol,
                            wp["type"],
                            wp["x"],
                            wp["y"],
                            orbits,
                            orbitals,
                        ),
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


def cartographer(request, priority=3):
    with connect("dbname=st2 user=postgres") as conn, conn.cursor() as cur:
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

    # start systems (fully charted by default)
    index = "start systems"
    query = """
    SELECT "systemSymbol" 
    FROM "waypoints" 
    WHERE "type" = 'ENGINEERED_ASTEROID' 
    ORDER BY "systemSymbol"
    """
    _chart_systems(request, index, query, priority)

    # gate systems (can be charted by other players)
    index = "gate systems"
    query = """
    SELECT "systemSymbol" 
    FROM "waypoints" 
    WHERE "type" = 'JUMP_GATE'
    EXCEPT
    SELECT "systemSymbol" 
    FROM "waypoints" 
    WHERE "type" = 'ENGINEERED_ASTEROID'
    ORDER BY "systemSymbol"
    """
    _chart_systems(request, index, query, priority)

    logger.info(f"The Cartographer has completed its chart!")

    # TODO: run the cartographer every n hours for (partially) on uncharted systems


def _chart_systems(request, index, query, priority):
    with connect("dbname=st2 user=postgres") as conn, conn.cursor() as cur:
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

        token = api_agent(request, priority)[1]
        logger.info(f"The Cartographer has found {total-current:_} {index} to chart")
        cur.execute(query)
        ret = cur.fetchall()
        while current != total:
            if DEBUG:
                logger.debug(f"Processing {current+1:_}/{total:_}")
            system_symbol = ret[current][0]
            for ret2 in request.get_all(
                endpoint=f"systems/{system_symbol}/waypoints",
                priority=priority,
                token=token,
            ):
                for wp in ret2["data"]:
                    traits = [t["symbol"] for t in wp["traits"]]
                    # update the values that may have been updated
                    chart = Jsonb(wp.get("chart"))
                    faction = wp.get("faction", {}).get("symbol")
                    cur.execute(
                        """
                        UPDATE "waypoints"
                        SET "traits" = %s,
                            "chart" = %s,
                            "faction" = %s,
                            "isUnderConstruction" = %s
                        WHERE "symbol" = %s
                        """,
                        (
                            traits,
                            chart,
                            faction,
                            wp["isUnderConstruction"],
                            wp["symbol"],
                        ),
                    )

                    if traits in [["UNCHARTED"], []]:
                        continue

                    if wp["type"] == "JUMP_GATE":
                        _chart_gate(wp, request, token, cur)
                    if "MARKETPLACE" in traits:
                        _chart_market(wp, request, token, cur)
                    if "SHIPYARD" in traits:
                        _chart_shipyard(wp, request, token, cur)

                    # store unknown traits
                    for trait in traits:
                        if TRAITS_WAYPOINT.get(trait) is None:
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


def _chart_gate(symbol, request, token, cur):
    system_symbol = symbol.rsplit("-", 1)[0]
    connections = request.get(
        endpoint=f"systems/{system_symbol}/waypoints/{symbol}/jump-gate",
        priority=3,
        token=token,
    )["data"]["connections"]
    cur.execute(
        """
        INSERT INTO "jump_gates"
        ("symbol", "systemSymbol", "connections")
        VALUES (%s, %s, %s)
        ON CONFLICT ("symbol") DO NOTHING
        """,
        (
            symbol,
            system_symbol,
            connections,
        ),
    )


def _chart_market(symbol, request, token, cur):
    system_symbol = symbol.rsplit("-", 1)[0]
    ret = request.get(
        endpoint=f"systems/{system_symbol}/waypoints/{symbol}/market",
        priority=3,
        token=token,
    )["data"]
    cur.execute(
        """
        INSERT INTO "markets"
        ("symbol", "systemSymbol", "imports", "exports", "exchange")
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT ("symbol") DO NOTHING
        """,
        (
            symbol,
            system_symbol,
            [good["symbol"] for good in ret["imports"]],
            [good["symbol"] for good in ret["exports"]],
            [good["symbol"] for good in ret["exchange"]],
        ),
    )


def _chart_shipyard(symbol, request, token, cur):
    system_symbol = symbol.rsplit("-", 1)[0]
    ret = request.get(
        endpoint=f"systems/{system_symbol}/waypoints/{symbol}/shipyard",
        priority=3,
        token=token,
    )["data"]
    cur.execute(
        """
        INSERT INTO "shipyards"
        ("symbol", "systemSymbol", "shipTypes", "modificationsFee")
        VALUES (%s, %s, %s, %s)
        ON CONFLICT ("symbol") DO NOTHING
        """,
        (
            symbol,
            system_symbol,
            [ship["type"] for ship in ret["shipTypes"]],
            ret["modificationsFee"],
        ),
    )
