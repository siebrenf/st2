from asyncio import sleep

from psycopg import connect
from psycopg.rows import dict_row

from st2 import time
from st2.ai.utils import queue_task
from st2.logging import logger
from st2.request import RequestMp
from st2.system import System
from st2.trade import price_estimate

DEBUG = True


@logger.catch  # catch errors in a separate thread
async def ai_trade_controller(
    system_symbol,
    agent_symbol,
    qa_pairs,
    interval=60,
):
    """
    Trade in the system by submitting assignments to the queued task list
    """
    pname = "traders"
    ships = {}  # cargo, fuel and speed per ship
    system = System(system_symbol, RequestMp(qa_pairs))
    uncharted_waypoints = _uncharted_waypoints(system)
    unscouted_markets = _unscouted_markets(system)
    del system
    while True:
        assigned_ships = _get_assigned_ships(system_symbol, pname, agent_symbol)
        if len(assigned_ships) == 0:
            await sleep(interval)
            continue

        queued_tasks = {}  # queued tasks that can be overwritten
        blacklisted_goods = set()  # max one trader per good
        for task in assigned_ships:
            ship = task["symbol"]
            if task["current"] is not None:
                args = task["current"].split(" ")
                if args[0] in ["trade", "supply", "deliver"]:
                    good = args[1]
                    blacklisted_goods.add(good)
            if task["queued"] is None:
                queued_tasks[ship] = None
            else:
                # ignore ships with deliver/supply tasks, or selling leftover cargo
                args = task["queued"].split(" ")
                if args[0] == "trade" and args[3] != "None":
                    queued_tasks[ship] = task["queued"]
            if ship not in ships:
                _set_ship_metadata(ship, ships)

        while len(uncharted_waypoints) and len(queued_tasks):
            if DEBUG:
                logger.debug(
                    f"{len(uncharted_waypoints)} uncharted waypoints found in {system_symbol}"
                )
            ship = _get_scout_ship(queued_tasks, ships)
            wp = uncharted_waypoints.pop(0)
            queue_task(ship, f"scout {wp}")

        while len(unscouted_markets) and len(queued_tasks):
            if DEBUG:
                logger.debug(
                    f"{len(unscouted_markets)} unscouted markets found in {system_symbol}"
                )
            ship = _get_scout_ship(queued_tasks, ships)
            wp = unscouted_markets.pop(0)
            queue_task(ship, f"scout {wp}")

        if len(queued_tasks) == 0:
            await sleep(interval)
            continue

        # identify trade opportunities
        trades, outdated_markets = _get_trade_goods(system_symbol, blacklisted_goods)
        if DEBUG:
            logger.debug(f"{len(trades)} trades found in {system_symbol}")
            logger.debug(
                f"{len(outdated_markets)} outdated markets found in {system_symbol}"
            )
        cargo_capacity_max = max([v["cargo"] for v in ships.values()])
        for good, (_, seller, buyer) in trades.items():
            max_units, purchase_price, sell_price = _get_trade_units(
                seller, buyer, cargo_capacity_max
            )
            if sell_price - purchase_price < 1000:
                break  # no worthwhile trades left

            estimated_time_cost = 0  # TODO
            estimated_fuel_cost = 0  # TODO
            estimated_max_profit = (
                sell_price - purchase_price - estimated_fuel_cost - estimated_time_cost
            )
            if estimated_max_profit < 1000:
                continue  # unworthwhile trade
            estimated_return_of_investment = (
                sell_price - purchase_price - estimated_fuel_cost - estimated_time_cost
            ) / (purchase_price + estimated_fuel_cost + estimated_time_cost)
            if estimated_return_of_investment < 0.05:
                continue  # unsafe trade

            ship, units, estimated_profit, task_old = _get_trade_ship(
                queued_tasks, ships, max_units, seller, buyer
            )
            task = f"trade {good} {units} {seller['waypointSymbol']} {buyer['waypointSymbol']}"
            if task != task_old:
                queue_task(ship, task, estimated_profit=estimated_profit)
            if len(queued_tasks) == 0:
                break

        while len(queued_tasks) and len(outdated_markets):
            ship = _get_scout_ship(queued_tasks, ships)
            wp = _get_scout_waypoint(outdated_markets)
            queue_task(ship, f"scout {wp}")

        await sleep(interval)


def _uncharted_waypoints(system, get_all=False):
    """Return uncharted waypoints with a good chance of containing a marketplace"""
    # https://github.com/SpaceTradersAPI/api-docs/blob/main/models/WaypointType.json
    wps = []
    for wp, md in system.waypoints.items():
        if len(md["traits"]) != 1:
            continue
        if md["traits"][0] != "UNCHARTED":
            continue
        if not get_all and md["type"] in {
            "ASTEROID",
            "ASTEROID_FIELD",
            "DEBRIS_FIELD",
            "GAS_GIANT",
            "GRAVITY_WELL",
            "NEBULA",
        }:
            continue
        wps.append(wp)
    wps = system.shortest_passing_path(wps)
    return wps


def _unscouted_markets(system):
    _ = system.waypoints
    with connect(
        "dbname=st2 user=postgres", row_factory=dict_row
    ) as conn, conn.cursor() as cur:
        # contains charted marketplaces
        ret1 = cur.execute(
            """
            SELECT "symbol" FROM markets
            WHERE "systemSymbol" = %s
            """,
            (system.symbol,),
        ).fetchall()
        # contains scouted marketplaces
        ret2 = cur.execute(
            """
            SELECT DISTINCT ON ("waypointSymbol") * FROM market_tradegoods
            WHERE "systemSymbol" = %s
            ORDER BY "waypointSymbol", "timestamp" DESC;
            """,
            (system.symbol,),
        ).fetchall()
    unscouted_markets = list(
        {row["symbol"] for row in ret1} - {row["waypointSymbol"] for row in ret2}
    )
    unscouted_markets = system.shortest_passing_path(unscouted_markets)
    return unscouted_markets


def _get_assigned_ships(system_symbol, pname, agent_symbol):
    with connect(
        "dbname=st2 user=postgres", row_factory=dict_row
    ) as conn, conn.cursor() as cur:
        assigned_ships = cur.execute(
            """
            SELECT * FROM "tasks" 
            WHERE "agentSymbol" = %s 
            AND "pname" = %s
            AND "symbol" IN (
                SELECT "symbol" FROM "ships"
                WHERE "agentSymbol" = %s
                AND "nav" ->> 'systemSymbol' = %s
            )
            """,
            (agent_symbol, pname, agent_symbol, system_symbol),
        ).fetchall()
    if DEBUG:
        logger.debug(
            f"{len(assigned_ships)} ships assigned to trade in {system_symbol}"
        )
    return assigned_ships


def _set_ship_metadata(ship_symbol, ships_dict):
    with connect(
        "dbname=st2 user=postgres", row_factory=dict_row
    ) as conn, conn.cursor() as cur:
        ship = cur.execute(
            """
            SELECT cargo, fuel, engine FROM "ships" 
            WHERE "symbol" = %s 
            """,
            (ship_symbol,),
        ).fetchone()
        ships_dict[ship_symbol] = {
            "cargo": ship["cargo"]["capacity"],
            "fuel": ship["fuel"]["capacity"],
            "speed": ship["engine"]["speed"],
        }


def _get_trade_goods(system_symbol, blacklisted_goods=None, max_age=3600):
    """
    Return a sorted dict of tradeGoods with the highest profit per unit, seller, and buyer.
    """
    # most recent market prices
    with connect(
        "dbname=st2 user=postgres", row_factory=dict_row
    ) as conn, conn.cursor() as cur:
        ret = cur.execute(
            """
            SELECT DISTINCT ON ("waypointSymbol", "symbol") * FROM market_tradegoods
            WHERE "systemSymbol" = %s
            ORDER BY "waypointSymbol", "symbol", "timestamp" DESC;
            """,
            (system_symbol,),
        ).fetchall()

    # split markets into buyers and sellers per good
    sellers = {}
    buyers = {}
    outdated_markets = {}
    if blacklisted_goods is None:
        blacklisted_goods = set()
    time_now = time.now()
    for row in ret:
        age = (time_now - row["timestamp"]).seconds
        if age > max_age:
            outdated_markets[row["waypointSymbol"]] = age
            continue
        good = row["symbol"]
        if good in blacklisted_goods:
            continue
        if row["type"] in ("IMPORT", "EXCHANGE") and row["supply"] in (
            "SCARCE",
            "LIMITED",
            "MODERATE",
        ):
            if good not in buyers:
                buyers[good] = []
            buyers[good].append(row)
        if row["type"] in ("EXPORT", "EXCHANGE") and row["supply"] in (
            "MODERATE",
            "HIGH",
            "ABUNDANT",
        ):
            if good not in sellers:
                sellers[good] = []
            sellers[good].append(row)

    # find the most profitable trade partners per good (ignoring distance)
    best = {}
    for good in buyers:
        if good not in sellers:
            continue
        best[good] = (-float("inf"), (), ())
        # the best buyer has the highest sellPrice
        best_buyer = -float("inf"), None, None, 0
        for wp in buyers[good]:
            if wp["sellPrice"] > best_buyer[0]:
                best_buyer = wp["sellPrice"], wp
        # the best seller has the lowest purchasePrice
        best_seller = float("inf"), None, None, 0
        for wp in sellers[good]:
            if wp["purchasePrice"] < best_seller[0]:
                best_seller = wp["purchasePrice"], wp
        # the best seller-buyer combo has the highest profit per unit
        profit_per_unit = best_buyer[0] - best_seller[0]
        if profit_per_unit > best[good][0]:
            best[good] = profit_per_unit, best_seller[1], best_buyer[1]
    best = {
        k: v for k, v in sorted(best.items(), key=lambda item: item[1][0], reverse=True)
    }
    return best, outdated_markets


def _get_trade_units(tradegood_at_seller, tradegood_at_buyer, cargo_capacity_max=80):
    """
    Estimate the optimal number of units & the buy and sell prices.
    """
    tv_min, tv_max = sorted(
        [tradegood_at_buyer["tradeVolume"], tradegood_at_seller["tradeVolume"]]
    )
    tvs_divisible = tv_max / tv_min == tv_max // tv_min
    n_min = 1
    n_max = 1
    units = 0
    best = 0, 0, 0
    while units < cargo_capacity_max:
        if tvs_divisible or (tv_min * n_min) < (tv_max * n_max):
            units = min(tv_min * n_min, cargo_capacity_max)
            n_min += 1
        else:
            units = min(tv_max * n_max, cargo_capacity_max)
            n_max += 1
        purchase_price = price_estimate(tradegood_at_seller, units, action="purchase")
        sell_price = price_estimate(tradegood_at_buyer, units, action="sell")
        if best[2] - best[1] >= sell_price - purchase_price:
            break
        best = units, purchase_price, sell_price
    return best


def _get_trade_ship(
    queued_tasks, ship_dict, max_units, tradegood_at_seller, tradegood_at_buyer
):
    # TODO: select the best ship based on cargo capacity and fuel capacity
    #   - SHIP_COMMAND_FRIGATE: 40 cargo, 30 speed, 400 fuel, limit: 1
    #     - for goods with small tradeVolumes/medium distances/update markets
    #   - SHIP_LIGHT_SHUTTLE: 40 cargo, 15 speed, 300 fuel, 100k
    #     - for goods with small tradeVolumes/short distances
    #   - SHIP_LIGHT_HAULER: 80 cargo, 15 speed, 600 fuel, 400k
    #     - for large tradeVolumes/long distances
    best = None, 0, -float("inf")
    for ship, task in queued_tasks.items():
        units = min(max_units, ship_dict[ship]["cargo"])
        purchase_price = price_estimate(tradegood_at_seller, units, action="purchase")
        sell_price = price_estimate(tradegood_at_buyer, units, action="sell")
        estimated_profit = sell_price - purchase_price
        if estimated_profit > best[-1]:
            best = ship, units, estimated_profit
    ship, units, estimated_profit = best
    task_old = queued_tasks.pop(ship)
    return ship, units, estimated_profit, task_old


def _get_scout_ship(queued_tasks, ships):
    """
    The best scout ship can fly fastest & without refueling
    """
    best = None, -float("inf")
    for ship in queued_tasks:
        score = ships[ship]["speed"] * 1.0 + ships[ship]["fuel"] * 0.1
        if score > best[-1]:
            best = ship, score
    ship = best[0]
    queued_tasks.pop(ship)
    return ship


def _get_scout_waypoint(outdated_markets):
    best = None, -float("inf")
    for wp, age in outdated_markets.items():
        if age > best[1]:
            best = wp, age
    wp = best[0]
    outdated_markets.pop(wp)
    return wp
