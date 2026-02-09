from psycopg import connect

from st2.logging import logger
from st2.pathing.travel import travel
from st2.ship import Ship


@logger.catch  # catch errors in a separate thread
async def ai_supply_system(
    ship_symbol,
    good,
    units,
    purchase_wp,
    supply_wp,
    qa_pairs,
    priority=1,
    verbose=False,
    log=True,
):
    if verbose:
        logger.info(
            f"{ship_symbol} will purchase {units} {good} from {purchase_wp} and supply at {supply_wp}"
        )

    ship = Ship(ship_symbol, qa_pairs=qa_pairs, priority=priority)
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
            # link purchase to construction
            pp, md = pp
            with connect("dbname=st2 user=postgres") as conn, conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO ai_supply_system
                    ("waypointSymbol", bulk_transactions_id)
                    VALUES (%s, %s)
                    """,
                    (supply_wp, md["id"]),
                )
    await travel(ship, supply_wp, explore=True, verbose=False)
    ship.supply(good, units, verbose=verbose)
