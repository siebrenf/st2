from asyncio import sleep

from st2.logging import logger
from st2.ship import Ship
from st2.system import System


async def ai_probe_waypoint(
    ship_symbol,
    waypoint_symbol,
    qa_pairs,
    priority=3,
    verbose=False,
):
    ship = Ship(ship_symbol, qa_pairs, priority)

    # navigate to the waypoint
    if ship["nav"]["waypointSymbol"] != waypoint_symbol:
        ship.navigate(waypoint_symbol, verbose=verbose)
    nav_sleep = ship.nav_remaining()
    if nav_sleep:
        await sleep(nav_sleep)

    # store if the waypoint is also a shipyard
    system = System(ship["nav"]["systemSymbol"], ship.request)
    traits = system.waypoints[waypoint_symbol]["traits"]
    is_shipyard = "SHIPYARD" in traits

    # start probing
    if verbose:
        trait = "shipyard" if is_shipyard else "market"
        logger.info(f"{ship.name()} is probing {trait} {waypoint_symbol}")
    while True:
        if is_shipyard:
            ship.shipyard()
        ship.market()
        await sleep(600)
