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
    ship = Ship(ship_symbol, qa_pairs=qa_pairs, priority=priority)
    if verbose:
        logger.info(
            f"{ship.name()} will trade {units} {good} between {purchase_wp} and {sell_wp}"
        )
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
        "systemSymbol": sell_wp.rsplit("-", 1)[0],
        "purchase_start": {},
        "purchase_inf": {},
        "purchase_obs": {},
        "sell_start": {},
        "sell_inf": {},
        "sell_obs": {},
        "accuracy": 0.0,
        "travel_time": -1,
        "fuel_cost": -1,
        "timestamp": t0,
    }
    base_price = None
    if purchase_units != units:
        log = False  # only log complete tasks
    if log:
        base_price = get_base_price(good, "purchase")
        market_a = get_a(purchase_wp, good)
        tg = get_tradegood(purchase_wp, good)
        log_entry["purchase_start"] = log_trade_inference(
            purchase_wp, market_a, tg, units, base_price, "purchase", ship_symbol, t0
        )
        market_a = get_a(sell_wp, good)
        tg = get_tradegood(sell_wp, good)
        log_entry["sell_start"] = log_trade_inference(
            sell_wp, market_a, tg, units, base_price, "sell", ship_symbol, t0
        )

    if purchase_units > 0:
        fp += await travel(ship, purchase_wp, explore=True, verbose=False)
        pp = ship.buy(good, purchase_units, log, verbose=False)
        if log:
            pp, md = pp
            log_entry["purchase_inf"] = log_trade_inference(
                purchase_wp,
                md["market_a0"],
                md["tradeGoods"][0],
                units,
                base_price,
                "purchase",
                ship_symbol,
            )
            log_entry["purchase_obs"] = {
                "market_a": md["market_a1"],
                "tradeGoods": md["tradeGoods"],
                "transactions": md["transactions"],
            }

    fp += await travel(ship, sell_wp, explore=True, verbose=False)
    sp = ship.sell(good, units, log, verbose=False)
    if log:
        sp, md = sp
        log_entry["sell_inf"] = log_trade_inference(
            sell_wp,
            md["market_a0"],
            md["tradeGoods"][0],
            units,
            base_price,
            "sell",
            ship_symbol,
        )
        log_entry["sell_obs"] = {
            "market_a": md["market_a1"],
            "tradeGoods": md["tradeGoods"],
            "transactions": md["transactions"],
        }
        profit_inferred = sum(
            t["totalPrice"] for t in log_entry["sell_inf"]["transactions"]
        ) - sum(t["totalPrice"] for t in log_entry["purchase_inf"]["transactions"])
        profit_observed = sp - pp
        inference_accuracy = float(
            round(
                100 * (1 - abs(profit_inferred - profit_observed) / profit_observed), 2
            )
        )

    travel_time = (time.now() - t0).total_seconds()
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
        log_entry["accuracy"] = inference_accuracy  # excludes fuel
        log_entry["travel_time"] = travel_time
        log_entry["fuel_cost"] = fp
        log_entry["timestamp"] = t0
        submit_log_entry(log_entry)


def get_tradegood(waypoint_symbol, symbol):
    with connect(
        "dbname=st2 user=postgres", row_factory=dict_row
    ) as conn, conn.cursor() as cur:
        trade_good = cur.execute(
            """
            SELECT * FROM market_tradegoods 
            WHERE "waypointSymbol" = %s AND symbol = %s 
            ORDER BY timestamp DESC LIMIT 1
            """,
            (waypoint_symbol, symbol),
        ).fetchone()
    trade_good["timestamp"] = trade_good["timestamp"].isoformat()
    return trade_good


def log_trade_inference(
    waypoint_symbol,
    market_a,
    trade_good,
    units,
    base_price,
    action,
    ship_symbol,
    timestamp=None,
):
    if timestamp is None:
        timestamp = trade_good["timestamp"]
    if not isinstance(timestamp, str):
        timestamp = timestamp.isoformat()
    md = {
        "market_a": market_a,
        "tradeGoods": [trade_good],
        "transactions": [],
    }
    price_total = 0
    units_remaining = units
    y = trade_good[f"{action}Price"]
    a = market_a[0]
    x = y2x(y, a, base_price, trade_good["type"], action)
    while units_remaining > 0:
        u = min(units_remaining, trade_good["tradeVolume"])
        price_total += y * u

        # mimic the transaction model
        md["transactions"].append(
            {
                "id": None,
                "waypointSymbol": waypoint_symbol,
                "systemSymbol": waypoint_symbol.rsplit("-", 1)[0],
                "shipSymbol": ship_symbol,
                "tradeSymbol": trade_good["symbol"],
                "type": action,
                "units": u,
                "pricePerUnit": y,
                "totalPrice": y * u,
                "timestamp": timestamp,
            }
        )

        units_remaining -= u
        dx = u / trade_good["tradeVolume"]
        x += dx if action == "sell" else -dx
        y = x2y(x, a, base_price, trade_good["type"], action)

        # mimic the tradegood model
        md["tradeGoods"].append(
            {
                "id": None,
                "waypointSymbol": waypoint_symbol,
                "systemSymbol": waypoint_symbol.rsplit("-", 1)[0],
                "symbol": trade_good["symbol"],
                "tradeVolume": trade_good["tradeVolume"],
                "type": trade_good["type"],
                "supply": x2supply(x),
                "activity": trade_good.get("activity"),
                "purchasePrice": None if action == "sell" else y,
                "sellPrice": None if action != "sell" else y,
                "timestamp": timestamp,
            }
        )
    return md


def submit_log_entry(log_entry):
    with connect("dbname=st2 user=postgres") as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO ai_trade_system
            (symbol, "systemSymbol", purchase_start, purchase_inf, purchase_obs, sell_start, sell_inf, sell_obs, accuracy, travel_time, fuel_cost, timestamp)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            [
                log_entry["symbol"],
                log_entry["systemSymbol"],
                Jsonb(log_entry["purchase_start"]),
                Jsonb(log_entry["purchase_inf"]),
                Jsonb(log_entry["purchase_obs"]),
                Jsonb(log_entry["sell_start"]),
                Jsonb(log_entry["sell_inf"]),
                Jsonb(log_entry["sell_obs"]),
                log_entry["accuracy"],
                log_entry["travel_time"],
                log_entry["fuel_cost"],
                log_entry["timestamp"],
            ],
        )
