import math
from asyncio import sleep

from psycopg import connect
from psycopg.types.json import Jsonb

from st2.agent import api_agent
from st2.logging import logger

DEBUG = False


def merchant(request, priority=1):
    """
    Map all supply chains.
    """
    token = api_agent(request, priority)[1]
    data = request.get("market/supply-chain", priority, token)["data"]
    with connect("dbname=st2 user=postgres") as conn, conn.cursor() as cur:
        for export in sorted(data["exportToImportMap"]):
            imports = data["exportToImportMap"][export]
            cur.execute(
                """
                INSERT INTO supply_chain
                ("export", "imports")
                VALUES (%s, %s)
                ON CONFLICT ("export") DO NOTHING
                """,
                (export, imports),
            )


def ambassador(request, priority=1):
    """
    Map all factions.
    """
    factions = {}
    token = api_agent(request, priority)[1]
    for fs in request.get_all("factions", priority, token):
        for f in fs["data"]:
            factions[f["symbol"]] = f

    with connect("dbname=st2 user=postgres") as conn, conn.cursor() as cur:
        # insert factions & faction_traits
        for symbol in sorted(factions):
            f = factions[symbol]
            # description = f["description"].replace("'", "''")
            hq = f["headquarters"]
            if hq == "":
                hq = None
            traits = [t["symbol"] for t in f["traits"]]
            cur.execute(
                """
                INSERT INTO factions 
                ("symbol", "name", "description", "headquarters", "traits", "isRecruiting")
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT ("symbol") DO NOTHING
                """,
                (
                    f["symbol"],
                    f["name"],
                    f["description"],
                    hq,
                    traits,
                    f["isRecruiting"],
                ),
            )

            # traits_faction
            for trait in f["traits"]:
                # description = trait["description"].replace("'", "''")
                cur.execute(
                    """
                    INSERT INTO traits_faction
                    (symbol, name, description)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (symbol) DO NOTHING
                    """,
                    (trait["symbol"], trait["name"], trait["description"]),
                )


async def astronomer(request, priority=3, verbose=True):
    """
    Map all systems.
    """
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

        if verbose:
            logger.info(f"The Astronomer has found {total:_} stars in the night sky")
        total_pages = math.ceil(total / 20)
        while current < total:
            if verbose and DEBUG:
                logger.debug(f"Processing page {page:_}/{total_pages:_}")
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
            await sleep(0)  # give other processes a turn
    if verbose:
        logger.info(f"The Astronomer has completed its chart!")


async def cartographer(request, priority=3, chart="start systems", verbose=True):
    """
    Can be used after all systems have been mapped by the astronomer.
    """
    token = api_agent(request, priority)[1]
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

    # start systems (fully charted by default)
    if chart == "start systems":
        query = """
        SELECT "systemSymbol" 
        FROM "waypoints" 
        WHERE "type" = 'ENGINEERED_ASTEROID' 
        ORDER BY "systemSymbol"
        """
        completed = await _chart_systems(
            request, priority, token, "start systems", query, verbose
        )

    elif chart == "gate systems":
        # gate systems (can be charted by other players)
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
        completed = await _chart_systems(
            request, priority, token, "gate systems", query, verbose
        )

    else:
        raise ValueError(
            f"{chart=} not recognized! Options: 'start systems' or 'gate systems'"
        )

    if completed and verbose:
        logger.info(f"The Cartographer has completed its chart!")


async def _chart_systems(request, priority, token, index, query, verbose):
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
            return False

        if verbose:
            logger.info(
                f"The Cartographer has found {total-current:_} {index} to chart"
            )
        ret = cur.execute(query).fetchall()
        while current != total:
            if verbose and DEBUG:
                logger.debug(f"Processing {current+1:_}/{total:_}")
            system_symbol = ret[current][0]
            for ret2 in request.get_all(
                endpoint=f"systems/{system_symbol}/waypoints",
                priority=priority,
                token=token,
            ):
                for wp in ret2["data"]:
                    symbol = wp["symbol"]
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
                            symbol,
                        ),
                    )

                    if traits in [["UNCHARTED"], []]:
                        continue

                    if wp["type"] == "JUMP_GATE":
                        _get_gate(symbol, system_symbol, request, priority, token, cur)
                    if "MARKETPLACE" in traits:
                        _get_market(
                            symbol, system_symbol, request, priority, token, cur
                        )
                    if "SHIPYARD" in traits:
                        _get_shipyard(
                            symbol, system_symbol, request, priority, token, cur
                        )

                    # store unknown traits
                    for trait in traits:
                        t = [t for t in wp["traits"] if t["symbol"] == trait][0]
                        # description = t["description"].replace("'", "''")
                        cur.execute(
                            """
                            INSERT INTO traits_waypoint
                            (symbol, name, description) 
                            VALUES (%s, %s, %s)
                            ON CONFLICT ("symbol") DO NOTHING
                            """,
                            (t["symbol"], t["name"], t["description"]),
                        )
                await sleep(0)  # give other processes a turn
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
        return True


def _get_gate(symbol, system_symbol, request, priority, token, cur):
    connections = request.get(
        endpoint=f"systems/{system_symbol}/waypoints/{symbol}/jump-gate",
        priority=priority,
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


def _get_market(symbol, system_symbol, request, priority, token, cur):
    ret = request.get(
        endpoint=f"systems/{system_symbol}/waypoints/{symbol}/market",
        priority=priority,
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


def _get_shipyard(symbol, system_symbol, request, priority, token, cur):
    ret = request.get(
        endpoint=f"systems/{system_symbol}/waypoints/{symbol}/shipyard",
        priority=priority,
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
