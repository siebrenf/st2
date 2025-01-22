from asyncio import sleep

from st2.logging import logger
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
    if ship["nav"]["waypointSymbol"] != waypoint_symbol:
        ship.navigate(waypoint_symbol, verbose=verbose)
    if t := ship.nav_remaining():
        await sleep(t)

    # start probing
    if verbose:
        trait = "shipyard" if is_shipyard else "market"
        logger.info(f"{ship.name()} is probing {trait} {waypoint_symbol}")
    while True:
        if is_shipyard:
            ship.shipyard()
        ship.market()
        await sleep(600)
