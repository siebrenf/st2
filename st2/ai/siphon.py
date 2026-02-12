from asyncio import sleep

from st2.logging import logger
from st2.pathing.travel import travel
from st2.pathing.utils import nav_fuel
from st2.ship import Ship
from st2.system import System


@logger.catch  # catch errors in a separate thread
async def ai_siphon_start_system(
    ship_symbol, system_symbol, qa_pairs, priority=1, verbose=False
):
    ship = Ship(ship_symbol, qa_pairs=qa_pairs, priority=priority)
    system = System(system_symbol, ship.request, priority)

    # select a market that exchanges siphoned goods, around a gas giant
    #  tiebreaker: distance to center
    best = None, None, float("inf")
    center_wp = system.central_waypoint()
    for sell_wp in system.markets_with("HYDROCARBON", "EXCHANGE"):
        siphon_wp = system.waypoints[sell_wp].get("orbits")
        if system.waypoints.get(siphon_wp, {}).get("type") == "GAS_GIANT":
            dist = system.graph[center_wp][siphon_wp]["distance"]
            if dist < best[2]:
                best = sell_wp, siphon_wp, dist
    sell_wp, siphon_wp, dist = best
    if verbose:
        logger.info(f"{ship_symbol} will siphon from {siphon_wp} and sell at {sell_wp}")

    # sanity check
    for g, u in ship.cargo_yield():
        if g not in ["HYDROCARBON", "LIQUID_HYDROGEN", "LIQUID_NITROGEN"]:
            ship.jettison(g, u, verbose)

    # fuel per roundtrip
    dist = system.graph[sell_wp][siphon_wp]["distance"]
    fuel_minimum = nav_fuel(dist) * 4  # add extra fuel for safety

    # start at the sell_wp
    if ship["nav"]["waypointSymbol"] not in [sell_wp, siphon_wp]:
        await travel(ship, sell_wp, explore=False, verbose=False)
    if ship["nav"]["waypointSymbol"] == siphon_wp:
        if t := ship.cooldown_remaining():
            await sleep(t)
        while ship["cargo"]["units"] < ship["cargo"]["capacity"]:
            ship.siphon(verbose=False)
            await sleep(ship.cooldown_remaining())
        ship.navigate(sell_wp)
        await sleep(ship.nav_remaining())

    while True:
        # at the sell_wp
        for g, u in ship.cargo_yield():
            ship.sell(g, u, verbose=False)
        if ship["fuel"]["current"] < fuel_minimum:
            ship.refuel()
        ship.navigate(siphon_wp)
        await sleep(max(ship.nav_remaining(), ship.cooldown_remaining()))

        # at the siphon_wp
        while ship["cargo"]["units"] < ship["cargo"]["capacity"]:
            ship.siphon(verbose=False)
            await sleep(ship.cooldown_remaining())
        ship.navigate(sell_wp)
        await sleep(ship.nav_remaining())
