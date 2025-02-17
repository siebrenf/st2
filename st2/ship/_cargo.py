from psycopg import connect
from psycopg.types.json import Jsonb

from st2.logging import logger


def cargo_yield(self):
    for d in self["cargo"]["inventory"]:
        yield d["symbol"], d["units"]


def buy(self, symbol, units, verbose=True):
    self.dock()

    # split the purchase order by trade volume
    price = 0
    trade_volume = _get_trade_volume(self, symbol)
    while units > 0:
        u = min(trade_volume, units)
        price += _buy_sell(self, symbol, u, "purchase", verbose)
        units -= u

    self.market()
    return price


def sell(self, symbol, units, verbose=True):
    self.dock()

    # split the sell order by trade volume
    price = 0
    trade_volume = _get_trade_volume(self, symbol)
    while units > 0:
        u = min(trade_volume, units)
        price += _buy_sell(self, symbol, u, "sell", verbose)
        units -= u

    self.market()
    return price


def _get_trade_volume(self, symbol):
    with connect("dbname=st2 user=postgres") as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT "tradeVolume" 
                FROM market_tradegoods 
                WHERE "waypointSymbol" = %s 
                AND symbol = %s
                """,
                (self["nav"]["waypointSymbol"], symbol),
            )
            ret = cur.fetchone()
    if ret:
        tv = ret[0]
        return tv
    else:
        self.market()
        return _get_trade_volume(self, symbol)


def _buy_sell(self, symbol, units, action, verbose=True):
    data = self.request.post(
        endpoint=f'my/ships/{self["symbol"]}/{action}',
        data={"symbol": symbol, "units": units},
    )["data"]
    self._update(data)

    price = data["transaction"]["totalPrice"]
    if verbose:
        wp = self["nav"]["waypointSymbol"]
        key_word = "sold" if action == "sell" else "purchased"
        logger.info(f"{self.name()} {key_word} {units} {symbol} for {price} at {wp}")
    return price


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
