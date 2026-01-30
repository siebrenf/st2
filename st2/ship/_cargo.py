from psycopg import connect
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from st2.exceptions import ShipInTransitError
from st2.logging import logger
from st2.trade import get_a, get_base_price, set_a
from st2.trade.functions import A_VALUES, x2supply, y2x

DEBUG = True


def cargo_yield(self):
    for d in self["cargo"]["inventory"]:
        yield d["symbol"], d["units"]


def buy(self, symbol, units, verbose=True):
    price = _buy_sell(self, symbol, units, "purchase", verbose)
    return price


def sell(self, symbol, units, verbose=True):
    price = _buy_sell(self, symbol, units, "sell", verbose)
    return price


def _buy_sell(self, symbol, units, action, verbose):
    """
    Split the order by trade volumes, and request them.
    Collect tradeGood and transaction information where needed.
    """
    self.dock()

    total_price = 0
    wp = self["nav"]["waypointSymbol"]
    # If update_a=True, request the TradeGood information between each transaction
    # and use this to calculate the value of `a`.
    # If update_a=False, only request the TradeGood information after the order.
    update_a = False if get_a(wp, symbol)[1] < 1 / 200 else True
    if update_a:
        self.market()
    tg0 = _get_trade_good(self, symbol)
    remaining_units = units
    while remaining_units > 0:
        transaction_units = min(tg0["tradeVolume"], remaining_units)

        data = self.request.post(
            endpoint=f'my/ships/{self["symbol"]}/{action}',
            data={"symbol": symbol, "units": transaction_units},
        )["data"]
        self._update(data)
        if update_a:
            self.market()

        price = data["transaction"]["totalPrice"]
        total_price += price
        if verbose:
            key_word = "sold" if action == "sell" else "purchased"
            logger.info(
                f"{self.name()} {key_word} {transaction_units} {symbol} at {wp} for {price:_} credits"
            )

        remaining_units -= transaction_units
    if update_a:
        tg1 = _get_trade_good(self, symbol)
        _update_market_a(self["nav"]["waypointSymbol"], tg0, tg1, action)
    else:
        self.market()
    return total_price


def _get_trade_good(self, symbol):
    """
    Return the most recent tradegood. If none is present, request it.
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
    if ret is None:  # or (time.now() - ret["timestamp"]).seconds > max_age:
        data = self.market()
        if data is None:
            t = self.nav_remaining()
            if t == 0:
                raise RecursionError(
                    "System time and game time desynchronized!"
                )
            else:
                raise ShipInTransitError(
                    f"{self.name()} in transit {wp} ({t} seconds remaining)."
                )
        ret = _get_trade_good(self, symbol)
    return ret


def _update_market_a(waypoint_symbol, tg0, tg1, action):
    symbol = tg0["symbol"]
    base_price = get_base_price(symbol, action)
    a_new, score_new = a_posterior(waypoint_symbol, tg0, tg1, action, base_price)
    a_old, score_old = get_a(waypoint_symbol, symbol)
    if DEBUG:
        logger.debug(f"{a_old=} {score_old=}, {a_new=} {score_new=}")  # TODO: remove
    if score_new < score_old:
        if DEBUG:
            logger.debug(
                f"Updated `a` at {waypoint_symbol} for {symbol} from {a_old} to {a_new}"
            )
        set_a(waypoint_symbol, symbol, a_new, score_new)


def a_posterior(waypoint_symbol, tg0, tg1, action, base_price):
    # retrieve the tradegood and transaction information from the database
    symbol = tg0["symbol"]
    port = tg0["type"]
    tgs, tas = _get_tradegoods_and_transactions(
        waypoint_symbol, symbol, tg0["timestamp"], tg1["timestamp"]
    )
    if len(tgs) != len(tas) + 1:
        if DEBUG:
            logger.debug(f"Another ship influenced the {symbol} transaction")
            logger.debug(f"    {len(tgs)=} {len(tas)=}")
            logger.debug(f"    {tgs=}")
            logger.debug(f"    {tas=}")  # TODO: remove
            logger.debug("")
        return None, float("inf")

    # match the supply levels with the transaction prices
    units = 0
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
                # TODO: remove
                logger.debug(f"    {action=} {port=} {len(tgs)=} {len(tas)=}")
                logger.debug(f"    {tg=}")
                logger.debug(f"    {ta=}")
                logger.debug(f"    {tgs=}")
                logger.debug(f"    {tas=}")
                logger.debug("")
            return None, float("inf")
        units += ta["units"]
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
        # return None, float("inf")

    # find the value of a where the supply levels match the inferred value of x
    # and look for the lowest difference between the observed and inferred dx.
    best = A_VALUES[0], float("inf")
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
        logger.debug(
            f"a_posterior progress: {waypoint_symbol=} {port=} {symbol=} {a=} diff={round(diff, 6)}"
        )  # TODO: remove
        if diff < best[1]:
            best = a, float(diff)
    if best[1] == float("inf"):
        logger.warning(
            f"The {base_price=:_} for {symbol}, the values for `a`, or the {port} market functions, are incorrect!"
        )
        logger.warning(
            f"Source transactions: {waypoint_symbol=} {symbol=} {tg0['timestamp']=}"
        )
    return best


def _get_tradegoods_and_transactions(waypoint_symbol, symbol, t0, t1):
    with connect(
        "dbname=st2 user=postgres", row_factory=dict_row
    ) as conn, conn.cursor() as cur:
        tgs = cur.execute(
            """
            SELECT * FROM market_tradegoods 
            WHERE "waypointSymbol" = %s AND symbol = %s 
            AND timestamp >= %s AND timestamp <= %s
            ORDER BY timestamp ASC
            """,
            (waypoint_symbol, symbol, t0, t1),
        ).fetchall()
        tas = cur.execute(
            """
            SELECT * FROM market_transactions
            WHERE "waypointSymbol" = %s AND "tradeSymbol" = %s 
            AND timestamp >= %s AND timestamp <= %s
            ORDER BY timestamp ASC
            """,
            (waypoint_symbol, symbol, t0, t1),
        ).fetchall()

    # this function assumes exactly 1 tradeGood before and after each transaction
    if len(tgs) > len(tas) + 1:
        filtered_tgs = []
        # take the most recent tradeGood for each transaction
        i_tgs = 0
        for ta in tas:
            last = None
            for i in range(i_tgs, len(tgs)):
                tg = tgs[i]
                if tg["timestamp"] < ta["timestamp"]:
                    last = tg
                    i_tgs += 1
                else:
                    break
            if last:
                filtered_tgs.append(last)
        # take the first tradeGood after the latest transaction
        ta = tas[-1]
        for i in range(i_tgs, len(tgs)):
            tg = tgs[i]
            if tg["timestamp"] > ta["timestamp"]:
                filtered_tgs.append(tg)
                break
        tgs = filtered_tgs
    return tgs, tas


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
