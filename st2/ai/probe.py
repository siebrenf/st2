from asyncio import sleep

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
    ship.refresh()

    # navigate to the waypoint
    await travel(ship, waypoint_symbol, verbose=verbose)

    # start probing
    if verbose:
        trait = "shipyard" if is_shipyard else "market"
        logger.info(f"{ship.name()} is probing {trait} {waypoint_symbol}")
    while True:
        if is_shipyard:
            ship.shipyard()
        ship.market()
        await sleep(600)
