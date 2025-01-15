from psycopg import connect

from st2 import time


def shipyard(self):
    """get all shipyard details"""
    waypoint_symbol = self["nav"]["waypointSymbol"]
    system_symbol = self["nav"]["systemSymbol"]
    data = self.request.get(
        f'systems/{self["nav"]["systemSymbol"]}/waypoints/{self["nav"]["waypointSymbol"]}/shipyard',
    )["data"]
    timestamp = time.now()
    with connect("dbname=st2 user=postgres") as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO shipyards
            (symbol, systemSymbol, shipTypes, modificationsFee)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (symbol) DO NOTHING
            """,
            (
                waypoint_symbol,
                system_symbol,
                [ship["type"] for ship in data["shipTypes"]],
                data["modificationsFee"],
            ),
        )
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
        conn.commit()
    return data


# def repair(self, quote=True, verbose=True, log=True):
#     """Repair the ship. Returns the repair price if quote=True
#     (without repairing the ship)."""
#     self.dock()
#
#     func = request.get if quote else request.post
#     data = func(f'my/ships/{self["symbol"]}/repair', self["agent"])["data"]
#     if quote is False:
#         # update relevant ship stats
#         for k, v in data["ship"].items():
#             if "condition" in v:
#                 self[k] = v
#         self._update_cache()
#         cache.set(("credits", request.agent), data["agent"]["credits"])
#
#     price = data["transaction"]["totalPrice"]
#     if verbose:
#         wp = self["nav"]["waypointSymbol"]
#         if quote:
#             fc = round(100 * self["frame"]["condition"])
#             rc = round(100 * self["reactor"]["condition"])
#             ec = round(100 * self["engine"]["condition"])
#             logger.info(f"{self.name()} would be repaired for {price:_} at {wp}")
#             logger.debug(
#                 f"  Component conditions: frame {fc}%, reactor {rc}%, engine {ec}%"
#             )
#         else:
#             fi = round(100 * self["frame"]["integrity"])
#             ri = round(100 * self["reactor"]["integrity"])
#             ei = round(100 * self["engine"]["integrity"])
#             logger.info(f"{self.name()} was repaired for {price:_} at {wp}")
#             logger.debug(
#                 f"  Component integrities: frame {fi}%, reactor {ri}%, engine {ei}%"
#             )
#         # _log_parts(self)
#
#     if log:
#         log_repair_scrap(self, "repair", price)
#     return price
#
#
# def scrap(self, quote=True, verbose=True, log=True):
#     """Sell the ship for scrap. Returns the sell price if quote=True
#     (without selling the ship)."""
#     self.dock()
#
#     func = request.get if quote else request.post
#     data = func(f'my/ships/{self["symbol"]}/scrap', self["agent"])["data"]
#     if quote is False:
#         cache.set(("credits", request.agent), data["agent"]["credits"])
#         del cache[("ship", self["symbol"])]
#     price = data["transaction"]["totalPrice"]
#     if verbose:
#         wp = self["nav"]["waypointSymbol"]
#         if quote:
#             logger.info(f"{self.name()} would scrap for {price:_} at {wp}")
#         else:
#             logger.info(f"{self.name()} was scrapped for {price:_} at {wp}")
#         # _log_parts(self)
#
#     if log:
#         log_repair_scrap(self, "scrap", price)
#     return price
#
#
# def _log_parts(self):
#     market_data = self.market()
#     parts = None
#     plating = None
#     for tg in market_data["tradeGoods"]:
#         if tg["symbol"] == "SHIP_PARTS":
#             parts = tg["purchasePrice"], tg["supply"]
#         if tg["symbol"] == "SHIP_PLATING":
#             plating = tg["purchasePrice"], tg["supply"]
#     logger.debug(
#         f"  Materials: SHIP_PARTS={parts[0]:_} ({parts[1]}), "
#         f"SHIP_PLATING={plating[0]:_} ({plating[1]})"
#     )
