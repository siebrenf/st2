from psycopg import connect

from st2 import time


def market(self, symbol=None, units=None):
    """get all marketplace details"""
    waypoint_symbol = self["nav"]["waypointSymbol"]
    system_symbol = self["nav"]["systemSymbol"]
    data = self.request.get(
        f"systems/{system_symbol}/waypoints/{waypoint_symbol}/market",
    )["data"]
    timestamp = time.now()
    tg = None
    ta = []
    with connect("dbname=st2 user=postgres") as conn, conn.cursor() as cur:
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
            if symbol and t["symbol"] == symbol:
                tg = t
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
            if symbol and t["symbol"] == symbol:
                ta.append(t)
        if symbol:
            y0 = None
            action = None
            remaining_units = units
            total_units = 0
            for t in ta:
                total_units += t["units"]
                if t["shipSymbol"] != self["symbol"]:
                    continue
                remaining_units -= t["units"]
                if action is None:
                    action = t["type"].lower()
                if action != t["type"].lower():
                    raise NotImplementedError("Mixed buying and selling of goods")
                if remaining_units < 0:
                    # TODO: check the order of transactions (asc/desc)
                    raise NotImplementedError
                if remaining_units == 0:
                    y0 = t["pricePerUnit"]
                    break
            y1 = tg[f"{action}Price"]
            s1 = tg["supply"]
            base_price = get_base_price(symbol, action)
            a, score = a_posterior2(y0, y1, s1, total_units, tg["tradeVolume"], tg["type"], action, base_price)
            _set_a(waypoint_symbol, symbol, a, score)
    return data
