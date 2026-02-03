from st2.contract import get_active_contract
from st2.logging import logger
from st2.pathing.travel import travel
from st2.ship import Ship


@logger.catch  # catch errors in a separate thread
async def ai_deliver_system(
    ship_symbol,
    good,
    units,
    purchase_wp,
    deliver_wp,
    qa_pairs,
    priority=1,
    verbose=False,
    log=True,
):
    if verbose:
        logger.info(
            f"{ship_symbol} will deliver {units} {good} between {purchase_wp} and {deliver_wp}"
        )

    ship = Ship(ship_symbol, qa_pairs=qa_pairs, priority=priority)
    contract = get_active_contract(ship["agentSymbol"])
    # jettison unrelated cargo
    purchase_units = units
    for g, u in ship.cargo_yield():
        if g == good:
            purchase_units -= u
        else:
            ship.jettison(g, u, verbose)

    if purchase_units > 0:
        await travel(ship, purchase_wp, explore=True, verbose=False)
        pp = ship.buy(good, purchase_units, log, verbose=False)
        if log:
            pp, md = pp
        # _update_purchase_contract_log(
        #     contract["id"], ship_symbol, purchase_wp, good, (time.now() - t0).seconds
        # )
        # t0 = time.now()
    await travel(ship, deliver_wp, explore=True, verbose=False)
    ship.deliver(good, units, contract, verbose=verbose)


#     _update_contract_log(contract["id"], ship_symbol, (time.now() - t0).seconds)
#
#
# def _update_purchase_contract_log(
#     contract_id, ship_symbol, waypoint_symbol, trade_symbol, time2purchase
# ):
#     deliver_transactions = []
#     fuel_transactions = []
#     with connect(
#         "dbname=st2 user=postgres", row_factory=dict_row
#     ) as conn, conn.cursor() as cur:
#         mt = cur.execute(
#             """
#             SELECT * FROM "market_transactions"
#             WHERE "shipSymbol" = %s
#             AND "tradeSymbol" = %s
#             AND "waypointSymbol" = %s
#             AND "timestamp" > %s - interval '5 minutes'
#             """,
#             [ship_symbol, trade_symbol, waypoint_symbol, time.now()],
#         ).fetchall()
#         for t in mt:
#             deliver_transactions.append((t["waypointSymbol"], t["timestamp"]))
#         ft = cur.execute(
#             """
#             SELECT * FROM "market_transactions"
#             WHERE "shipSymbol" = %s
#             AND "tradeSymbol" = %s
#             AND "timestamp" > %s - interval '5 minutes'
#             """,
#             [ship_symbol, "FUEL", time2purchase],
#         ).fetchall()
#         for t in ft:
#             fuel_transactions.append((t["waypointSymbol"], t["timestamp"]))
#         # column definition: my_list jsonb NOT NULL DEFAULT '[]'
#         cur.execute(
#             """
#             UPDATE contract_logs
#             WHERE contract_id = %s
#             SET items1 = items1 || %s::jsonb, items2 = items2 || %s::jsonb, items3 = items3 || %s::jsonb
#             """,
#             (contract_id,),
#         )
#     # TODO: update the list of purchases in the contract log row
#     # TODO: update the list of times2purchases in the contract log row
#     # TODO: update the list of fuel_prices in the contract log row
#
#
# def _update_contract_log(contract_id, ship_symbol, time2delivery):
#     fuel_transactions = []
#     with connect(
#         "dbname=st2 user=postgres", row_factory=dict_row
#     ) as conn, conn.cursor() as cur:
#         ft = cur.execute(
#             """
#             SELECT * FROM "market_transactions"
#             WHERE "shipSymbol" = %s
#             AND "tradeSymbol" = %s
#             AND "timestamp" > %s - interval '5 minutes'
#             """,
#             [ship_symbol, "FUEL", time2delivery],
#         ).fetchall()
#     for t in ft:
#         fuel_transactions.append((t["waypointSymbol"], t["timestamp"]))
#
#     # TODO: update the list of times2deliveries in the contract log row
#     # TODO: update the list of fuel_prices in the contract log row
#     raise NotImplementedError
