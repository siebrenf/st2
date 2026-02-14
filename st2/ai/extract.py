from asyncio import sleep

from st2.logging import logger
from st2.pathing.travel import travel
from st2.pathing.utils import nav_fuel
from st2.ship import Ship
from st2.system import System


@logger.catch  # catch errors in a separate thread
async def ai_extract_start_system(
    ship_symbol, extract_wp, sell_wp, qa_pairs, priority=1, verbose=False
):
    ship = Ship(ship_symbol, qa_pairs=qa_pairs, priority=priority)
    fuel_minimum = get_fuel_minimum(ship, sell_wp, extract_wp)
    avg_yield = 3  # prevent too much waste

    # on start, begin at the sell_wp
    if ship["nav"]["waypointSymbol"] not in [sell_wp, extract_wp]:
        await travel(ship, sell_wp, explore=False, verbose=False)
        ship.nav_patch("CRUISE")
    # on restart, continue until the sell_wp
    if ship["nav"]["waypointSymbol"] == extract_wp:
        await sleep(max(ship.nav_remaining(), ship.cooldown_remaining()))

        while ship["cargo"]["units"] + avg_yield < ship["cargo"]["capacity"]:
            ship.extract(verbose=False)
            await sleep(ship.cooldown_remaining())

        ship.navigate(sell_wp, verbose=False)
        await sleep(ship.nav_remaining())

    while True:
        # at the sell_wp
        for g, u in ship.cargo_yield():
            ship.sell(g, u, verbose=verbose)
        if ship["fuel"]["current"] < fuel_minimum:
            ship.refuel()

        ship.navigate(extract_wp, verbose=False)
        await sleep(max(ship.nav_remaining(), ship.cooldown_remaining()))

        # at the extract_wp
        while ship["cargo"]["units"] + avg_yield < ship["cargo"]["capacity"]:
            ship.extract(verbose=False)
            await sleep(ship.cooldown_remaining())

        ship.navigate(sell_wp, verbose=False)
        await sleep(ship.nav_remaining())


def get_fuel_minimum(ship, sell_wp, extract_wp):
    system_symbol = sell_wp.rsplit("-", 1)[0]
    system = System(system_symbol, ship.request)
    # fuel per roundtrip * 2 for safety
    dist = system.graph[sell_wp][extract_wp]["distance"]  # noqa
    fuel_minimum = nav_fuel(dist) * 4
    return fuel_minimum
