from asyncio import sleep

from st2.ai.siphon import get_fuel_minimum
from st2.logging import logger
from st2.pathing.travel import travel
from st2.ship import Ship


@logger.catch  # catch errors in a separate thread
async def ai_extract_start_system(
    ship_symbol,
    trait,
    extract_wp,
    sell_wp,
    whitelist,
    qa_pairs,
    priority=2,
    verbose=False,
):
    ship = Ship(ship_symbol, qa_pairs=qa_pairs, priority=priority)
    fuel_minimum = get_fuel_minimum(ship, extract_wp, sell_wp)
    mode = "CRUISE"
    if fuel_minimum > ship["fuel"]["capacity"]:
        fuel_minimum = 2
        mode = "DRIFT"
    buffer = 3  # prevent too much waste
    whitelist = whitelist.split(",")
    if verbose:
        logger.info(
            f"{ship.name()} will extract the {trait} at {extract_wp} and {mode} to market {sell_wp}"
        )

    # on start, begin at the sell_wp
    # on restart, continue until the sell_wp
    if ship["nav"]["waypointSymbol"] not in [sell_wp, extract_wp]:
        await travel(ship, sell_wp, explore=False, verbose=False)
    elif ship["nav"]["waypointSymbol"] == extract_wp:
        await sleep(max(ship.nav_remaining(), ship.cooldown_remaining()))

        while True:
            if ship["cargo"]["units"] + buffer >= ship["cargo"]["capacity"]:
                for g, u in ship.cargo_yield():
                    if g not in whitelist:
                        ship.jettison(g, u, verbose=False)
                if ship["cargo"]["units"] + buffer >= ship["cargo"]["capacity"]:
                    break
            ship.extract(verbose=False)
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

        ship.navigate(extract_wp, verbose=False)
        await sleep(max(ship.nav_remaining(), ship.cooldown_remaining()))

        # at the extract_wp
        while True:
            if ship["cargo"]["units"] + buffer >= ship["cargo"]["capacity"]:
                for g, u in ship.cargo_yield():
                    if g not in whitelist:
                        ship.jettison(g, u, verbose=False)
                if ship["cargo"]["units"] + buffer >= ship["cargo"]["capacity"]:
                    break
            ship.extract(verbose=False)
            await sleep(ship.cooldown_remaining())

        ship.navigate(sell_wp, verbose=False)
        await sleep(ship.nav_remaining())
