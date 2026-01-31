from psycopg import connect

from st2.db.static import GOODS, SHIPS
from st2.trade.base_prices import BASE_PRICES
from st2.trade.functions import a_posterior, a_prior, x2y, y2x
from st2.trade.price_ranges import PRICE_RANGES


def price_estimate(trade_good, units, action):
    """Approximate the purchase/sell price for a batch of tradeGoods"""
    if action not in ["purchase", "sell"]:
        raise ValueError
    price = trade_good[f"{action}Price"]

    # simple scenario
    if units / trade_good["tradeVolume"] <= 1:
        price_total = price * units
        return round(price_total)

    # complex scenario
    base_price = get_base_price(trade_good["symbol"], action)
    a, score = get_a(trade_good["waypointSymbol"], trade_good["symbol"])
    if score >= 10:
        a, score = a_prior(
            price,
            trade_good["supply"],
            base_price,
            trade_good["type"],
            action,
        )
        set_a(trade_good["waypointSymbol"], trade_good["symbol"], a, score)

    price_total = 0
    units_remaining = units
    x = y2x(price, a, base_price, trade_good["type"], action)
    while units_remaining > 0:
        u = min(units_remaining, trade_good["tradeVolume"])
        price_total += price * u

        units_remaining -= u
        dx = u / trade_good["tradeVolume"]
        x += dx if action == "sell" else -dx
        y = x2y(x, a, base_price, trade_good["type"], action)
        price = max(y, 1)
    return round(price_total)


def get_base_price(good, action):
    bp = BASE_PRICES.get(good)
    if bp is None:
        bp = get_avg_price(good, action)
    return bp


def get_a(waypoint_symbol, symbol):
    with connect("dbname=st2 user=postgres") as conn, conn.cursor() as cur:
        ret = cur.execute(
            """
            SELECT "a", "score" FROM market_a
            WHERE "waypointSymbol" = %s AND "symbol" = %s
            """,
            (waypoint_symbol, symbol),
        ).fetchone()
    if ret is None:
        ret = None, 10.0
    return ret


def set_a(waypoint_symbol, symbol, a, score):
    with connect("dbname=st2 user=postgres") as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO market_a
            ("waypointSymbol", "symbol", "a", "score")
            VALUES (%s, %s, %s, %s)
            ON CONFLICT ("waypointSymbol", "symbol") DO UPDATE
            SET "a" = EXCLUDED."a",
            "score" = EXCLUDED."score"
            """,
            (waypoint_symbol, symbol, a, score),
        )


def get_avg_price(good, action):
    """return the approximate average price of a good in MODERATE supply.
    This value can be 2x worse depending on the market."""
    good = good.upper()
    if _in_database(good, "MODERATE"):
        md = PRICE_RANGES[good]["MODERATE"]
        buy = (md["purchasePrice"]["min"] + md["purchasePrice"]["max"]) / 2
        if md["sellPrice"]["min"] is not None:
            sell = (md["sellPrice"]["min"] + md["sellPrice"]["max"]) / 2
    elif _in_database(good, "LIMITED") and _in_database(good, "HIGH"):
        md = PRICE_RANGES[good]["LIMITED"]
        buy1 = (md["purchasePrice"]["min"] + md["purchasePrice"]["max"]) / 2
        if md["sellPrice"]["min"] is not None:
            sell1 = (md["sellPrice"]["min"] + md["sellPrice"]["max"]) / 2

        md = PRICE_RANGES[good]["HIGH"]
        buy2 = (md["purchasePrice"]["min"] + md["purchasePrice"]["max"]) / 2
        if md["sellPrice"]["min"] is not None:
            sell2 = (md["sellPrice"]["min"] + md["sellPrice"]["max"]) / 2

        buy = (buy1 + buy2) / 2
        if md["sellPrice"]["min"] is not None:
            sell = (sell1 + sell2) / 2
    elif _in_database(good, "SCARCE") and _in_database(good, "ABUNDANT"):
        md = PRICE_RANGES[good]["SCARCE"]
        buy1 = md["purchasePrice"]["min"]
        if md["sellPrice"]["min"] is not None:
            sell1 = md["sellPrice"]["min"]

        md = PRICE_RANGES[good]["ABUNDANT"]
        buy2 = md["purchasePrice"]["max"]
        if md["sellPrice"]["max"] is not None:
            sell2 = md["sellPrice"]["max"]

        buy = (buy1 + buy2) / 2
        if md["sellPrice"]["min"] is not None:
            sell = (sell1 + sell2) / 2
    elif _in_database(good, "LIMITED"):
        md = PRICE_RANGES[good]["LIMITED"]
        buy = (md["purchasePrice"]["min"] + md["purchasePrice"]["max"]) / 2
        if md["sellPrice"]["min"] is not None:
            sell = (md["sellPrice"]["min"] + md["sellPrice"]["max"]) / 2
    elif _in_database(good, "HIGH"):
        md = PRICE_RANGES[good]["HIGH"]
        buy = (md["purchasePrice"]["min"] + md["purchasePrice"]["max"]) / 2
        if md["sellPrice"]["min"] is not None:
            sell = (md["sellPrice"]["min"] + md["sellPrice"]["max"]) / 2
    elif _in_database(good, "SCARCE"):
        md = PRICE_RANGES[good]["SCARCE"]
        buy = md["purchasePrice"]["min"]
        if md["sellPrice"]["min"] is not None:
            sell = md["sellPrice"]["min"]
    elif _in_database(good, "ABUNDANT"):
        md = PRICE_RANGES[good]["ABUNDANT"]
        buy = md["purchasePrice"]["max"]
        if md["sellPrice"]["max"] is not None:
            sell = md["sellPrice"]["max"]
    elif good not in GOODS:
        raise ValueError(f"good '{good}' does not exist")
    else:
        return None

    if action.lower() == "sell":
        if good in SHIPS:
            raise TypeError("Use Ship.scrap() check sell prices")
        price = sell
    else:
        price = buy
    return round(price)


def _in_database(good, supply):
    return PRICE_RANGES[good][supply]["purchasePrice"]["min"] is not None
