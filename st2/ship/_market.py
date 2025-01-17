from psycopg import connect

from st2 import time


def market(self):
    """get all marketplace details"""
    waypoint_symbol = self["nav"]["waypointSymbol"]
    system_symbol = self["nav"]["systemSymbol"]
    data = self.request.get(
        f"systems/{system_symbol}/waypoints/{waypoint_symbol}/market",
    )["data"]
    timestamp = time.now()
    with connect("dbname=st2 user=postgres") as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO markets
                ("symbol", "systemSymbol", "imports", "exports", "exchange")
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT ("symbol") DO NOTHING
                """,
                (
                    waypoint_symbol,
                    system_symbol,
                    [good["symbol"] for good in data["imports"]],
                    [good["symbol"] for good in data["exports"]],
                    [good["symbol"] for good in data["exchange"]],
                ),
            )
            for t in data.get("tradeGoods", []):
                cur.execute(
                    """
                    INSERT INTO market_tradegoods
                    ("waypointSymbol", "systemSymbol", "symbol", "tradeVolume", "type",
                     "supply", "activity", "purchasePrice", "sellPrice", "timestamp")
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT ("waypointSymbol", "symbol", "timestamp") DO NOTHING
                    """,
                    (
                        waypoint_symbol,
                        system_symbol,
                        t["symbol"],
                        t["tradeVolume"],
                        t["type"],
                        t["supply"],
                        t.get("activity"),
                        t["purchasePrice"],
                        t["sellPrice"],
                        timestamp,
                    ),
                )
            for t in data.get("transactions", []):
                cur.execute(
                    """
                    INSERT INTO market_transactions
                    ("waypointSymbol", "systemSymbol", "shipSymbol", "tradeSymbol",
                     "type", "units", "pricePerUnit", "totalPrice", "timestamp")
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT ("waypointSymbol", "timestamp") DO NOTHING
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
    return data
