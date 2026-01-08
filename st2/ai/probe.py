from asyncio import sleep

from psycopg import connect

from st2.logging import logger
from st2.pathing.travel import travel
from st2.ship import Ship


@logger.catch  # catch errors in a separate thread
async def ai_probe_waypoint(
    ship_symbol,
    waypoint_symbol,
    is_shipyard,
    qa_pairs,
    priority=3,
    verbose=False,
):
    ship = Ship(ship_symbol, qa_pairs, priority)
    # ship.refresh()

    # navigate to the waypoint
    await travel(ship, waypoint_symbol, explore=True, verbose=verbose)

    # start probing
    if verbose:
        trait = "shipyard" if is_shipyard else "market"
        logger.info(f"{ship.name()} is probing {trait} {waypoint_symbol}")
    while True:
        if is_shipyard:
            ship.shipyard()
        ship.market()
        await sleep(600)


@logger.catch  # catch errors in a separate thread
async def ai_probe_purchase(
    ship_symbol,
    waypoint_symbol,
    qa_pairs,
    priority=3,
    verbose=False,
):
    ship = Ship(ship_symbol, qa_pairs, priority)
    # ship.refresh()

    # navigate to the waypoint
    await travel(ship, waypoint_symbol, explore=True, verbose=False)

    # purchase probe
    probe_symbol = ship.buy_ship("SHIP_PROBE", verbose=verbose)

    # set its task
    task = f"probe shipyard {waypoint_symbol}"
    with connect("dbname=st2 user=postgres") as conn, conn.cursor() as cur:
        cur.execute(
            """
            UPDATE tasks
            SET "queued" = %s,
                "pname" = %s
            WHERE "symbol" = %s
            """,
            (task, "probes", probe_symbol),
        )
