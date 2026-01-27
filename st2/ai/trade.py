from psycopg import connect
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from st2 import time
from st2.logging import logger
from st2.pathing.travel import travel
from st2.ship import Ship
from st2.trade import a_prior, get_base_price, x2y, y2x


@logger.catch  # catch errors in a separate thread
async def ai_trade_system(
    ship_symbol,
    good,
    units,
    purchase_wp,
    sell_wp,
    qa_pairs,
    priority=1,
    verbose=False,
    log=True,
):
    if verbose:
        logger.info(
            f"{ship_symbol} will trade {units} {good} between {purchase_wp} and {sell_wp}"
        )

    ship = Ship(ship_symbol, qa_pairs=qa_pairs, priority=priority)
    # jettison unrelated cargo
    purchase_units = units
    for g, u in ship.cargo_yield():
        if g == good:
            purchase_units -= u
        else:
            ship.jettison(g, u, verbose)

    fp = 0
    pp = 0
    t = None
    t0 = time.now()
    log_entry = {
        "symbol": good,
        "units": units,
        "shipSymbol": ship_symbol,
        "timestamp": t0,
    }
    if purchase_units != units:
        log = False  # only log complete tasks
    if log:
        t = time.now()
        for (
            action,
            waypoint_symbol,
        ) in [("purchase", purchase_wp), ("sell", sell_wp)]:
            log_entry[f"{action}_start"] = log_trade_inference(
                good, units, action, waypoint_symbol, ship_symbol, t, False
            )
    if purchase_units > 0:
        fp += await travel(ship, purchase_wp, explore=True, verbose=False)
        if log:
            t = time.now()
            log_entry["purchase_inf"] = log_trade_inference(
                good, units, "purchase", purchase_wp, ship_symbol, t
            )
        pp = ship.buy(good, purchase_units, verbose=False)
        if log:
            log_entry["purchase_obs"] = log_trade_observation(
                good, "purchase", purchase_wp, ship_symbol, t
            )
    fp += await travel(ship, sell_wp, explore=True, verbose=False)
    if log:
        t = time.now()
        log_entry["sell_inf"] = log_trade_inference(good, units, "sell", sell_wp, t)
    sp = ship.sell(good, units, verbose=False)
    if log:
        log_entry["sell_obs"] = log_trade_observation(
            good, "sell", sell_wp, ship_symbol, t
        )

    travel_time = (time.now() - t0).seconds
    total_profit = sp - pp - fp
    return_of_investment = round((sp - pp - fp) / max(pp + fp, 1), 2)
    if verbose:
        logger.info(
            f"{ship.name()} traded {units} {good} for {total_profit:_} ({travel_time=}, {return_of_investment=})"
        )
    if log:
        log_entry["travel_time"] = travel_time
        log_entry["fuel_cost"] = fp
        log_entry["return_of_investment"] = return_of_investment
        submit_log_entry(log_entry)


def log_trade_inference(
    good, units, action, waypoint_symbol, ship_symbol, timestamp, infer=True
):
    md = {
        "market_a": (0, 0),
        "basePrice": 0,
        "totalPrice": 0,
        "tradeGood": {},
        "transactions": [],
    }
    with connect(
        "dbname=st2 user=postgres", row_factory=dict_row
    ) as conn, conn.cursor() as cur:
        a, score = cur.execute(
            """SELECT a, score FROM market_a WHERE "waypointSymbol" = %s AND "symbol" = %s""",
            (waypoint_symbol, good),
        ).fetchone()
        trade_good = cur.execute(
            """
            SELECT * FROM market_tradegoods
            WHERE "waypointSymbol" = %s AND "symbol" = %s
            ORDER BY "timestamp" DESC LIMIT 1
            """,
            (waypoint_symbol, good),
        ).fetchone()
    y = trade_good[f"{action}Price"]
    base_price = get_base_price(trade_good["symbol"], action)
    if infer:
        a_new, score_new = a_prior(
            y,
            trade_good["supply"],
            base_price,
            trade_good["type"],
            action,
        )
        if score_new < score:
            a, score = a_new, score_new
    price_total = 0
    units_remaining = units
    x = y2x(y, a, base_price, trade_good["type"], action)
    while units_remaining > 0:
        u = min(units_remaining, trade_good["tradeVolume"])
        price_total += y * u

        # mimic the transaction model
        md["transactions"].append(
            {
                "waypointSymbol": waypoint_symbol,
                "systemSymbol": waypoint_symbol.rstrip("-", 1)[0],
                "shipSymbol": ship_symbol,
                "tradeSymbol": good,
                "type": action,
                "units": u,
                "pricePerUnit": y,
                "totalPrice": y * u,
                "timestamp": timestamp,
                "x": x,
            }
        )
        units_remaining -= u
        dx = u / trade_good["tradeVolume"]
        x += -dx if action == "sell" else dx
        y = x2y(x, a, base_price, trade_good["type"], action)
    md["market_a"] = a, score
    md["basePrice"] = base_price
    md["tradeGood"] = trade_good
    md["totalPrice"] = round(price_total)
    return md


def log_trade_observation(good, action, waypoint_symbol, ship_symbol, timestamp):
    md = {
        "market_a": (0, 0),
        "basePrice": 0,
        "totalPrice": 0,
        "tradeGood": {},
        "transactions": [],
    }
    with connect(
        "dbname=st2 user=postgres", row_factory=dict_row
    ) as conn, conn.cursor() as cur:
        a, score = cur.execute(
            """SELECT a, score FROM market_a WHERE "waypointSymbol" = %s AND "symbol" = %s""",
            (waypoint_symbol, good),
        ).fetchone()
        trade_good = cur.execute(
            """
            SELECT * FROM market_tradegoods
            WHERE "waypointSymbol" = %s AND "symbol" = %s
            ORDER BY "timestamp" DESC LIMIT 1
            """,
            (waypoint_symbol, good),
        ).fetchone()
        transactions = cur.execute(
            """
            SELECT * FROM market_transactions
            WHERE "waypointSymbol" = %s AND "tradeSymbol" = %s AND "timestamp" >= %s
            ORDER BY "timestamp" ASC
            """,
            (waypoint_symbol, good, timestamp),
        ).fetchone()
    base_price = get_base_price(trade_good["symbol"], action)
    md["market_a"] = a, score
    md["basePrice"] = base_price
    md["tradeGood"] = trade_good

    price_total = 0
    for t in transactions:
        t["x"] = y2x(t["pricePerUnit"], a, base_price, trade_good["type"], action)
        md["transactions"].append(t)
        if t["shipSymbol"] == ship_symbol:
            price_total += t["totalPrice"]
    md["totalPrice"] = round(price_total)
    return md


def submit_log_entry(log_entry):
    with connect("dbname=st2 user=postgres") as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO trades
            (symbol, units, shipSymbol, timestamp, purchase_start, purchase_inf, purchase_obs, sell_start, sell_inf, sell_obs, travel_time, fuel_cost, return_of_investment)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            [
                log_entry["symbol"],
                log_entry["units"],
                log_entry["shipSymbol"],
                log_entry["timestamp"],
                Jsonb(log_entry["purchase_start"]),
                Jsonb(log_entry["purchase_inf"]),
                Jsonb(log_entry["purchase_obs"]),
                Jsonb(log_entry["sell_start"]),
                Jsonb(log_entry["sell_inf"]),
                Jsonb(log_entry["sell_obs"]),
                log_entry["travel_time"],
                log_entry["fuel_cost"],
                log_entry["return_of_investment"],
            ],
        )
