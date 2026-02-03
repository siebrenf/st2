from asyncio import sleep

from st2.agent import get_agent, get_agent_public
from st2.ai.utils import cancel_task, get_tasks, queue_task
from st2.logging import logger
from st2.request import RequestMp
from st2.ship import Ship, buy_ship
from st2.system import System

DEBUG = True


@logger.catch  # catch errors in a separate thread
async def ai_probe_controller(
    system_symbol,
    agent_symbol,
    qa_pairs,
    priority=2,
    interval=60,
    verbose=False,
):
    """
    Send a probe to each SHIPYARD (and optionally MARKETPLACE).
    Buys probes if needed, using a trader if no probes are available.

    This controller self-destructs after completing its task.
    """
    token = get_agent(agent_symbol)["token"]
    request = RequestMp(qa_pairs, priority, token)
    system = System(system_symbol, request, priority)

    # wait until all shipyards and marketplaces are charted & scouted
    while len(system.uncharted_markets()) + len(system.unscouted_markets()) != 0:
        await sleep(interval)
        system.refresh(refresh_graph=False)

    # non-overlapping sets of waypoints
    shipyards_selling_probes = set(system.shipyards_with("SHIP_PROBE"))
    shipyards = set(system.shipyards) - shipyards_selling_probes
    markets = set(system.markets) - set(system.shipyards)
    unprobed_shipyards_selling_probes = shipyards_selling_probes.copy()
    unprobed_shipyards = shipyards.copy()
    unprobed_markets = markets.copy()

    # load probes from the database
    shipyards_selling_probes2probes = dict()
    for task in get_tasks(pname="probes"):
        # check assumptions
        if task["current"] is not None:
            pass
        elif task["current"] is None and task["queued"] is None:
            raise NotImplementedError("Probes should be assigned already")
        elif task["queued"] is not None and task["current"] is not None:
            raise NotImplementedError("Probes should not have queued tasks")
        # update unprobed waypoints
        if task["current"].startswith("probe "):
            wp_type, waypoint_symbol = task["current"].split(" ")[1:]
            if wp_type == "shipyard":
                if task["agentSymbol"] != agent_symbol:
                    continue  # embed agent probes in all shipyards
                if waypoint_symbol in shipyards_selling_probes:
                    shipyards_selling_probes2probes[waypoint_symbol] = task["symbol"]
                    unprobed_shipyards_selling_probes.discard(waypoint_symbol)
                else:
                    unprobed_shipyards.discard(waypoint_symbol)
            else:
                unprobed_markets.discard(waypoint_symbol)

    probe_purchases_remaining = (
        len(unprobed_shipyards)
        + len(unprobed_shipyards_selling_probes)
        + len(unprobed_markets)
    )
    total = len(shipyards) + len(shipyards_selling_probes) + len(markets)
    if probe_purchases_remaining == 0:
        if DEBUG:
            logger.debug(f"probe controller {system_symbol} exiting")
        return "self destruct"
    if verbose:
        s = len(shipyards) + len(shipyards_selling_probes)
        m = len(markets)
        logger.info(f"{s} shipyards and {m} marketplaces in {system_symbol}")

    # assign an available ship to buy the first probe
    probe_purchase_underway = False
    while len(shipyards_selling_probes) == len(unprobed_shipyards_selling_probes):
        if DEBUG:
            logger.debug(
                f"No probes at shipyards in {system_symbol}. Attempting to purchase one"
            )
        available_ship_symbol = None
        for task in get_tasks(agent_symbol=agent_symbol, system_symbol=system_symbol):
            if task["pname"] == "traders":
                if task["queued"] is None or str(task["queued"]).startswith("trade "):
                    available_ship_symbol = task["ship"]
            if task["pname"] == "probes":
                if str(task["current"]).startswith("probe shipyard "):
                    waypoint_symbol = task["current"].split(" ")[2]
                    shipyards_selling_probes2probes[waypoint_symbol] = task["symbol"]
                    unprobed_shipyards_selling_probes.discard(waypoint_symbol)
                    probe_purchases_remaining -= 1
                    if DEBUG:
                        logger.debug(
                            f"probe controller {system_symbol}: {probe_purchases_remaining=}/{total}"
                        )
        if available_ship_symbol and not probe_purchase_underway:
            waypoint_symbol = sorted(unprobed_shipyards_selling_probes)[0]
            task = f"probe_purchase {waypoint_symbol}"
            queue_task(available_ship_symbol, task)
            probe_purchase_underway = True
        await sleep(interval)

    central_waypoint = system.central_waypoint()
    arrived = set()
    for waypoints_to_probe in [
        unprobed_shipyards_selling_probes,
        unprobed_shipyards,
        unprobed_markets,
    ]:
        # sort the waypoints from distal-proximal
        waypoints_to_probe = list(
            system.waypoints_sort(central_waypoint, waypoints_to_probe, reverse=True)
        )
        while len(waypoints_to_probe) > 0:
            # select the cheapest shipyard
            best = None, {}, float("inf")
            for shipyard_symbol, md in system.shipyards_with("SHIP_PROBE").items():
                if shipyard_symbol not in shipyards_selling_probes2probes:
                    continue
                price = md["purchasePrice"]
                if price < best[0]:
                    best = shipyard_symbol, md, price
            shipyard_symbol, md, price = best

            # wait until it's probe has arrived
            shipyard_probe = shipyards_selling_probes2probes[shipyard_symbol]
            if shipyard_probe not in arrived:
                ship = Ship(shipyards_selling_probes2probes[shipyard_symbol], request)
                t = ship.nav_remaining() + interval  # extra time to update the DB
                await sleep(t)
                arrived.add(shipyard_probe)
                continue

            # purchase a probe when affordable
            credits = get_agent_public(agent_symbol)["credits"]
            supply = md["supply"]
            if credits > 500_000 and supply != "SCARCE":
                probe_symbol = buy_ship(
                    "SHIP_PROBE", shipyard_symbol, agent_symbol, request, verbose
                )
                waypoint_symbol = waypoints_to_probe.pop(0)
                wp_type = (
                    "shipyard" if waypoint_symbol in system.shipyards else "market"
                )
                task = f"probe {wp_type} {waypoint_symbol}"
                for t in get_tasks(current=task):
                    # TODO: what to do with two player agents at one shipyard?
                    cancel_task(
                        t["symbol"], reason=f"{agent_symbol} taking over", task=task
                    )
                queue_task(probe_symbol, task, pname="probes")
                probe_purchases_remaining -= 1
                if DEBUG:
                    logger.debug(
                        f"probe controller {system_symbol}: {probe_purchases_remaining=}/{total}"
                    )
            await sleep(interval)

    if DEBUG:
        logger.debug(f"probe controller {system_symbol} exiting")
    return "self destruct"
