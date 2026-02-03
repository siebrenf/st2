from psycopg import connect
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from st2 import time
from st2.logging import logger
from st2.pathing.travel import travel
from st2.ship import Ship
from st2.trade import get_a, get_base_price
from st2.trade.functions import x2supply, x2y, y2x


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
    t0 = time.now()
    log_entry = {
        "symbol": good,
        "units": units,
        "shipSymbol": ship_symbol,
        "timestamp": t0,
    }
    base_price = None
    if purchase_units != units:
        log = False  # only log complete tasks
    if log:
        base_price = get_base_price(good, "purchase")
        log_entry["purchase_start"] = log_trade_inference(
            good, units, base_price, "purchase", purchase_wp, ship_symbol, t0
        )
        log_entry["sell_start"] = log_trade_inference(
            good, units, base_price, "sell", sell_wp, ship_symbol, t0
        )

    if purchase_units > 0:
        fp += await travel(ship, purchase_wp, explore=True, verbose=False)
        if log:
            log_entry["purchase_inf"] = log_trade_inference(
                good,
                units,
                base_price,
                "purchase",
                purchase_wp,
                ship_symbol,
                time.now(),
            )
        pp = ship.buy(good, purchase_units, log, verbose=False)
        if log:
            pp, tgs, tas = pp
            log_entry["purchase_obs"] = {
                "market_a": get_a(purchase_wp, good),
                "totalPrice": pp,
                "tradeGoods": tgs,
                "transactions": tas,
            }

    fp += await travel(ship, sell_wp, explore=True, verbose=False)
    if log:
        log_entry["sell_inf"] = log_trade_inference(
            good, units, base_price, "sell", sell_wp, ship_symbol, time.now()
        )
    sp = ship.sell(good, units, log, verbose=False)
    if log:
        sp, tgs, tas = sp
        log_entry["sell_obs"] = {
            "market_a": get_a(sell_wp, good),
            "totalPrice": sp,
            "tradeGoods": tgs,
            "transactions": tas,
        }
        profit_inferred = (
            log_entry["sell_inf"]["totalPrice"]
            - log_entry["purchase_inf"]["totalPrice"]
        )
        profit_observed = sp - pp
        inference_accuracy = round(
            100 * (1 - abs(profit_inferred - profit_observed) / profit_observed), 2
        )

    travel_time = (time.now() - t0).seconds
    total_profit = round(sp - pp - fp)
    if purchase_units != units:
        return_on_investment = None
    else:
        return_on_investment = round((sp - pp - fp) / max(pp + fp, 1), 2)
    if verbose:
        msg = f"{ship.name()} traded {units} {good} for {total_profit:_} ({travel_time=}, {return_on_investment=})"
        if log:
            msg = msg[:-1] + f", {inference_accuracy=}%)"  # noqa
        logger.info(msg)
    if log:
        log_entry["travel_time"] = travel_time
        log_entry["fuel_cost"] = fp
        log_entry["profit"] = total_profit  # includes fuel
        log_entry["return_on_investment"] = return_on_investment  # includes fuel
        log_entry["accuracy"] = inference_accuracy  # excludes fuel
        submit_log_entry(log_entry)


def log_trade_inference(
    good, units, base_price, action, waypoint_symbol, ship_symbol, timestamp
):
    a, score = get_a(waypoint_symbol, good)
    md = {
        "market_a": (a, score),
        "totalPrice": 0,
        "tradeGoods": [],
        "transactions": [],
    }
    with connect(
        "dbname=st2 user=postgres", row_factory=dict_row
    ) as conn, conn.cursor() as cur:
        trade_good = cur.execute(
            """
            SELECT * FROM market_tradegoods
            WHERE "waypointSymbol" = %s AND "symbol" = %s
            ORDER BY "timestamp" DESC LIMIT 1
            """,
            (waypoint_symbol, good),
        ).fetchone()
    trade_good["timestamp"] = trade_good["timestamp"].isoformat()
    md["tradeGoods"].append(trade_good)

    y = trade_good[f"{action}Price"]
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
                "systemSymbol": waypoint_symbol.rsplit("-", 1)[0],
                "shipSymbol": ship_symbol,
                "tradeSymbol": good,
                "type": action,
                "units": u,
                "pricePerUnit": y,
                "totalPrice": y * u,
                "timestamp": timestamp.isoformat(),
            }
        )
        units_remaining -= u
        dx = u / trade_good["tradeVolume"]
        x += dx if action == "sell" else -dx
        y = x2y(x, a, base_price, trade_good["type"], action)
        md["tradeGoods"].append(
            {
                "waypointSymbol": waypoint_symbol,
                "systemSymbol": waypoint_symbol.rsplit("-", 1)[0],
                "symbol": good,
                "tradeVolume": trade_good["tradeVolume"],
                "type": trade_good["type"],
                "supply": x2supply(x),
                "activity": trade_good["activity"],
                "purchasePrice": None,
                "sellPrice": None,
                "timestamp": timestamp.isoformat(),
            }
        )
        if action == "sell":
            md["tradeGoods"][-1]["sellPrice"] = y
        else:
            md["tradeGoods"][-1]["purchasePrice"] = y

    md["totalPrice"] = round(price_total)
    return md


def submit_log_entry(log_entry):
    with connect("dbname=st2 user=postgres") as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO trades
            (symbol, units, "shipSymbol", timestamp, purchase_start, purchase_inf, purchase_obs, sell_start, sell_inf, sell_obs, travel_time, fuel_cost, profit, return_on_investment, accuracy)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                log_entry["profit"],
                log_entry["return_on_investment"],
                log_entry["accuracy"],
            ],
        )
