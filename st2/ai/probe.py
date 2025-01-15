from psycopg import connect
from asyncio import sleep

from st2.request import RequestMp
from st2 import time
from psycopg.types.json import Jsonb


async def ai_probe_waypoint(ship_symbol, waypoint_symbol, qa_pairs, priority=3):
    request = RequestMp(qa_pairs)
    with connect("dbname=st2 user=postgres") as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT agentSymbol, nav FROM ships
            WHERE symbol = %s
            """,
            (ship_symbol,),
        )
        agent_symbol, nav = cur.fetchone()

        cur.execute(
            """
            SELECT token FROM agents
            WHERE symbol = %s
            """,
            (agent_symbol,),
        )
        token = cur.fetchone()[0]

        # navigate to the waypoint
        nav_sleep = time.remaining(nav["route"]["arrival"])
        if nav["waypointSymbol"] != waypoint_symbol:
            data = request.post(
                endpoint=f"my/ships/{ship_symbol}/navigate",
                priority=priority,
                token=token,
                data={"waypointSymbol": waypoint_symbol}
            )
            cur.execute(
                """
                UPDATE ships
                SET fuel = %s,
                    nav = %s
                WHERE symbol = %s
                """,
                (Jsonb(data["fuel"]), Jsonb(data["nav"]), ship_symbol),
            )
            nav_sleep = time.remaining(data["nav"]["route"]["arrival"])
            # TODO: move to Ship class
            # TODO: register event damage
            conn.commit()

    if nav_sleep:
        await sleep(nav_sleep)

    with connect("dbname=st2 user=postgres") as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT traits FROM waypoints
            WHERE symbol = %s
            """,
            (waypoint_symbol,),
        )
        # assumes the waypoint is charted & in the database
        traits = cur.fetchone()[0]
        if traits is None or traits == ["UNCHARTED"]:
            pass  # TODO: chart waypoint
            pass  # TODO: update database & commit
        is_shipyard = "SHIPYARD" in traits

    # start probing
    system_symbol = waypoint_symbol.rsplit("-", 1)[0]
    while True:
        with connect("dbname=st2 user=postgres") as conn, conn.cursor() as cur:
            timestamp = time.now()
            if is_shipyard:
                data = request.get(
                    endpoint=f"systems/{system_symbol}/waypoints/{waypoint_symbol}/shipyard",
                    priority=priority,
                    token=token,
                )["data"]
                for s in data.get("ships", []):
                    cur.execute(
                        """
                        INSERT INTO shipyard_ships
                        (waypointSymbol, systemSymbol, type,
                         supply, activity, purchasePrice, timestamp)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (waypointSymbol, symbol, timestamp) DO NOTHING
                        """,
                        (
                            waypoint_symbol,
                            system_symbol,
                            s["type"],
                            s["supply"],
                            s["activity"],
                            s["purchasePrice"],
                            timestamp,
                        ),
                    )
                for s in data.get("transactions", []):
                    cur.execute(
                        """
                        INSERT INTO shipyard_transactions
                        (waypointSymbol, systemSymbol, shipSymbol,
                         agentSymbol, shipType, price, timestamp)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (waypointSymbol, timestamp) DO NOTHING
                        """,
                        (
                            waypoint_symbol,
                            system_symbol,
                            s["shipSymbol"],
                            s["agentSymbol"],
                            s["shipType"],
                            s["price"],
                            time.read(s["timestamp"]),
                        ),
                    )

            data = request.get(
                endpoint=f"systems/{system_symbol}/waypoints/{waypoint_symbol}/market",
                priority=3,
                token=token,
            )["data"]
            for t in data.get("tradeGoods", []):
                cur.execute(
                    """
                    INSERT INTO market_tradegoods
                    (waypointSymbol, systemSymbol, symbol, tradeVolume, type,
                     supply, activity, purchasePrice, sellPrice, timestamp)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (waypointSymbol, symbol, timestamp) DO NOTHING
                    """,
                    (
                        waypoint_symbol,
                        system_symbol,
                        t["symbol"],
                        t["tradeVolume"],
                        t["type"],
                        t["supply"],
                        t["activity"],
                        t["purchasePrice"],
                        t["sellPrice"],
                        timestamp,
                    ),
                )
            for t in data.get("transactions", []):
                cur.execute(
                    """
                    INSERT INTO market_transactions
                    (waypointSymbol, systemSymbol, shipSymbol, tradeSymbol,
                     type, units, pricePerUnit, totalPrice, timestamp)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (waypointSymbol, timestamp) DO NOTHING
                    """,
                    (
                        waypoint_symbol,
                        system_symbol,
                        t["shipSymbol"],
                        t["tradeSymbol"],
                        t["type"],
                        t["units"],
                        t["pricePerUnit"],
                        t["totalPrice"],
                        time.read(t["timestamp"]),
                    ),
                )
            conn.commit()

        await sleep(600)
