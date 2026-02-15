from asyncio import sleep

from st2.logging import logger
from st2.pathing.travel import travel
from st2.pathing.utils import nav_fuel
from st2.ship import Ship
from st2.system import System


@logger.catch  # catch errors in a separate thread
async def ai_siphon_start_system(
    ship_symbol, siphon_wp, sell_wp, qa_pairs, priority=2, verbose=False
):
    ship = Ship(ship_symbol, qa_pairs=qa_pairs, priority=priority)
    fuel_minimum = get_fuel_minimum(ship, siphon_wp, sell_wp)
    mode = "CRUISE"
    if fuel_minimum > ship["fuel"]["capacity"]:
        fuel_minimum = 2
        mode = "DRIFT"
    buffer = 5  # prevent too much waste
    if verbose:
        logger.info(
            f"{ship.name()} will siphon the GAS_GIANT {siphon_wp} and {mode} to market {sell_wp}"
        )

    # on start, begin at the sell_wp
    # on restart, continue until the sell_wp
    if ship["nav"]["waypointSymbol"] not in [sell_wp, siphon_wp]:
        await travel(ship, sell_wp, explore=False, verbose=False)
    elif ship["nav"]["waypointSymbol"] == siphon_wp:
        await sleep(max(ship.nav_remaining(), ship.cooldown_remaining()))

        while ship["cargo"]["units"] + buffer < ship["cargo"]["capacity"]:
            ship.siphon(verbose=False)
            await sleep(ship.cooldown_remaining())

        ship.navigate(sell_wp, verbose=False)
        await sleep(ship.nav_remaining())
    elif ship["nav"]["waypointSymbol"] == sell_wp:
        await sleep(ship.nav_remaining())
    ship.nav_patch(mode)

    while True:
        # at the sell_wp
        for g, u in ship.cargo_yield():
            ship.sell(g, u, verbose=verbose)
        if ship["fuel"]["current"] < fuel_minimum:
            ship.refuel()

        ship.navigate(siphon_wp, verbose=False)
        await sleep(max(ship.nav_remaining(), ship.cooldown_remaining()))

        # at the siphon_wp
        while ship["cargo"]["units"] + buffer < ship["cargo"]["capacity"]:
            ship.siphon(verbose=False)
            await sleep(ship.cooldown_remaining())

        ship.navigate(sell_wp, verbose=False)
        await sleep(ship.nav_remaining())


def get_fuel_minimum(ship, action_wp, sell_wp):
    system_symbol = sell_wp.rsplit("-", 1)[0]
    system = System(system_symbol, ship.request)
    # fuel per roundtrip + extra for safety
    dist = system.graph[sell_wp][action_wp]["distance"]  # noqa
    fuel_minimum = nav_fuel(dist) * 2 * 1.2
    return fuel_minimum
