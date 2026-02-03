from psycopg import connect
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from st2 import time
from st2.exceptions import ShipInTransitError
from st2.logging import logger
from st2.trade import get_a, get_base_price, set_a
from st2.trade.functions import A_VALUES, x2supply, y2x

DEBUG = True


def cargo_yield(self):
    for d in self["cargo"]["inventory"]:
        yield d["symbol"], d["units"]


def buy(self, symbol, units, log=False, verbose=True):
    return _buy_sell(self, symbol, units, "purchase", log, verbose)


def sell(self, symbol, units, log=False, verbose=True):
    return _buy_sell(self, symbol, units, "sell", log, verbose)


def _buy_sell(self, symbol, units, action, log, verbose):
    """
    Split the order by trade volumes, and request them.
    Collect tradeGood and transaction information where needed.
    """
    self.dock()

    wp = self["nav"]["waypointSymbol"]
    # If update_a=True, request the TradeGood information between each transaction
    # and use this to calculate the value of `a`.
    # If update_a=False, only request the TradeGood information after the order.
    a_old, score_old = get_a(wp, symbol)
    update_a = True if log or score_old >= 0.005 else False
    log_entry = {
        "market_a0": (a_old, score_old),  # before
        "market_a1": (a_old, score_old),  # after
        "tradeGoods": [],
        "transactions": [],
        "timestamp": time.now(),
    }
    if update_a:
        for tg in self.market()["tradeGoods"]:
            if tg["symbol"] == symbol:
                log_entry["tradeGoods"].append(tg)
        tv = log_entry["tradeGoods"][0]["tradeVolume"]
    else:
        tv = _get_tradegood(self, symbol)["tradeVolume"]
    total_price = 0
    remaining_units = units
    while remaining_units > 0:
        transaction_units = min(tv, remaining_units)

        data = self.request.post(
            endpoint=f'my/ships/{self["symbol"]}/{action}',
            data={"symbol": symbol, "units": transaction_units},
        )["data"]
        self._update(data)
        if update_a:
            log_entry["transactions"].append(data["transaction"])
            for tg in self.market()["tradeGoods"]:
                if tg["symbol"] == symbol:
                    log_entry["tradeGoods"].append(tg)

        price = data["transaction"]["totalPrice"]
        total_price += price
        if verbose:
            key_word = "sold" if action == "sell" else "purchased"
            logger.info(
                f"{self.name()} {key_word} {transaction_units} {symbol} at {wp} for {price:_} credits"
            )

        remaining_units -= transaction_units
    if update_a:
        base_price = get_base_price(symbol, action)
        a_new, score_new = a_posterior(
            wp, log_entry["tradeGoods"], log_entry["transactions"], action, base_price
        )
        if score_new < score_old:
            log_entry["market_a1"] = a_new, score_new
            set_a(wp, symbol, a_new, score_new)
            if DEBUG:
                logger.debug(
                    f"Updated `a` at {wp} for {symbol} from {a_old} to {a_new}"
                )
        with connect("dbname=st2 user=postgres") as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO ship_transactions
                (market_a0, market_a1, "tradeGoods", transactions, timestamp)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    Jsonb(log_entry["market_a0"]),
                    Jsonb(log_entry["market_a1"]),
                    Jsonb(log_entry["tradeGoods"]),
                    Jsonb(log_entry["transactions"]),
                    log_entry["timestamp"],
                ),
            )
    else:
        self.market()
    if log:
        return total_price, log_entry
    return total_price


def _get_tradegood(self, symbol):
    """
    Return the most recent tradeGood. If none is present, request it.
    """
    wp = self["nav"]["waypointSymbol"]
    with connect(
        "dbname=st2 user=postgres", row_factory=dict_row
    ) as conn, conn.cursor() as cur:
        ret = cur.execute(
            """
            SELECT * FROM market_tradegoods 
            WHERE "waypointSymbol" = %s AND symbol = %s 
            ORDER BY timestamp DESC LIMIT 1
            """,
            (wp, symbol),
        ).fetchone()
    if ret is None:
        data = self.market()
        if data is None:
            t = self.nav_remaining()
            if t == 0:
                raise RecursionError("System time and game time desynchronized!")
            else:
                raise ShipInTransitError(
                    f"{self.name()} in transit {wp} ({t} seconds remaining)."
                )
        ret = _get_tradegood(self, symbol)
    return ret


def a_posterior(waypoint_symbol, tgs, tas, action, base_price):
    symbol = tgs[0]["symbol"]
    port = tgs[0]["type"]

    # match the supply levels with the transaction prices
    ss = []
    ys = []
    dxs = []
    tvs = []
    for i, ta in enumerate(tas):
        tg = tgs[i]
        if tg[f"{action}Price"] != ta["pricePerUnit"]:
            if DEBUG:
                logger.debug(
                    f"Outside factors influenced the {symbol} transaction "
                    f"at {waypoint_symbol} (prices changed: "
                    f"tradeGood={tg[f"{action}Price"]:_} "
                    f"transaction={ta["pricePerUnit"]:_})"
                )
            return None, 100.0
        ss.append(tg["supply"])  # supply level before the transaction
        ys.append(ta["pricePerUnit"])  # price at the transaction
        dxs.append(ta["units"] / tg["tradeVolume"])  # supply change of the transaction
        tvs.append(tg["tradeVolume"])  # tradeVolume before the transaction
    ys.append(tgs[-1][f"{action}Price"])  # price after all transactions
    ss.append(tgs[-1]["supply"])  # supply level after all transactions
    if DEBUG and len(set(tvs)) != 1:
        logger.debug(
            f"The tradeVolume for {symbol} increased at {waypoint_symbol} "
            f"from {min(tvs)} to {max(tvs)}!"
        )
        # return None, 100.0

    # find the value of a where the supply levels match the inferred value of x
    # and look for the lowest difference between the observed and inferred dx.
    best = A_VALUES[0], 100.0
    for a in A_VALUES:
        # infer values for x
        xs = []
        for i, y in enumerate(ys):
            x = y2x(y, a, base_price, port, action)
            if ss[i] != x2supply(x):
                break  # inferred x not contained in supply level
            xs.append(x)
        if len(xs) != len(ys):
            continue  # next value of a

        # lowest difference between the observed and inferred dx
        diff = 0
        for i, dx_obs in enumerate(dxs):
            dx_inf = abs(xs[i + 1] - xs[i])
            diff += abs(dx_obs - dx_inf) / dx_obs
        if diff < best[1]:
            best = a, float(diff)
    if best[1] == float("inf"):
        logger.warning(
            f"The {base_price=:_} for {symbol}, the values for `a`, or the {port} market functions, are incorrect!"
        )
    return best


def transfer(self, symbol, units, ship, verbose=True):
    """Transfer cargo between ships"""
    # match the status of the target ship
    if isinstance(ship, str):
        with connect("dbname=st2 user=postgres") as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM ships WHERE symbol = %s",
                    (ship,),
                )
                ship = cur.fetchone()
    if ship["nav"]["status"] == "DOCKED":
        self.dock()
    else:
        self.orbit()

    # copy the cargo manifest
    for md in self["cargo"]["inventory"]:
        if md["symbol"] == symbol:
            md_good = md.copy()
            md_good["units"] = units
            break

    # make the transfer
    data = self.request.post(
        f'my/ships/{self["symbol"]}/transfer',
        data={
            "tradeSymbol": symbol,
            "units": units,
            "shipSymbol": ship["symbol"],
        },
    )["data"]
    self._update(data)

    # update the cargo manifest of the target ship
    for md in ship["cargo"]["inventory"]:
        if md["symbol"] == symbol:
            md["units"] += units
            break
    else:
        ship["cargo"]["inventory"].append(md_good)  # noqa
    ship["cargo"]["units"] += units
    with connect("dbname=st2 user=postgres") as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE ships SET cargo = %s WHERE symbol = %s",
                (Jsonb(ship["cargo"]), ship["symbol"]),
            )

    if verbose:
        logger.info(f"{self.name()} transferred {units} {symbol} to {ship['symbol']}")
    return units


# def transfer_from(self, symbol, units, ship_symbol, verbose=True):
#     """
#     Transfer cargo from another ship to this one
#     """
#     payload = {
#         "tradeSymbol": symbol,
#         "units": units,
#         "shipSymbol": self["symbol"],
#     }
#     _ = request.post(f"my/ships/{ship_symbol}/transfer", payload)["data"]
#
#     # update ship cargo
#     self["cargo"]["units"] += units
#     for i in self["cargo"]["inventory"]:
#         if i["symbol"] == symbol:
#             i["units"] += units
#             break
#     else:
#         tg = GOODS.get(symbol, {"symbol": symbol}).copy()
#         tg["units"] = units
#         self["cargo"]["inventory"].append(tg)
#     self._update_cache()
#
#     if verbose:
#         logger.info(f"{self.name()} transferred {units} {symbol} from {ship_symbol}")


# def refine(self, symbol, verbose=True, log=True):
#     """
#     Refine raw materials in a 30:10 ratio.
#
#     Allowed values:
#     IRON, COPPER, SILVER, GOLD, ALUMINUM,
#     PLATINUM, URANITE, MERITIUM, FUEL.
#     """
#     # if self._no_cargo(symbol, 30, verbose=verbose):
#     #     return
#     # if self._in_transit(verbose):
#     #     return
#     # module = "MODULE_ORE_REFINERY"
#     # if symbol == "FUEL":
#     #     module = "MODULE_FUEL_REFINERY"
#     # elif symbol in ["placeholder"]:
#     #     module = "MODULE_MICRO_REFINERY"
#     # if self._no_module(module, verbose):
#     #     return
#     # if self._on_cooldown(verbose):
#     #     return
#
#     payload = {"produce": symbol}
#     data = request.post(f'my/ships/{self["symbol"]}/refine', self["agent"], payload)[
#         "data"
#     ]
#     self._update_cache(data, ["cargo", "cooldown"])
#     if verbose:
#         logger.info(
#             f'{data["consumed"]["units"]} {data["consumed"]["tradeSymbol"]} '
#             f'consumed to produce {data["produced"]["units"]} '
#             f'{data["produced"]["tradeSymbol"]}'
#         )
#     if log:
#         log_cooldown(self, "refine")


def jettison(self, symbol, units, verbose=False):
    """Jettison cargo from your ship's cargo hold"""
    data = self.request.post(
        f'my/ships/{self["symbol"]}/jettison', data={"symbol": symbol, "units": units}
    )["data"]
    units = self["cargo"]["units"] - data["cargo"]["units"]
    self._update(data)
    if verbose:
        logger.info(f"{self.name()} jettisoned {units} {symbol}")


def supply(self, symbol, units, verbose=True):
    """Supply a construction site with the specified good"""
    self.dock()

    data = self.request.post(
        f'systems/{self["nav"]["systemSymbol"]}/waypoints/'
        f'{self["nav"]["waypointSymbol"]}/construction/supply',
        data={"shipSymbol": self["symbol"], "tradeSymbol": symbol, "units": units},
    )["data"]
    self._update(data)

    # TODO: log data["construction"]

    if verbose:
        if data["construction"]["isComplete"]:
            logger.info(
                f'Construction at {data["construction"]["symbol"]} has completed!'
            )
        else:
            logger.info(
                f"{self.name()} supplied {units} {symbol} to the construction "
                f"at {self['nav']['waypointSymbol']}. Remaining requirements:"
            )
            for material in data["construction"]["materials"]:
                if (
                    material["required"] > material["fulfilled"]
                    or material["tradeSymbol"] == symbol
                ):
                    logger.info(f"  {material}")
