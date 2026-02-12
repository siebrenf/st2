from asyncio import sleep

from st2.agent import get_agent, get_agent_public
from st2.ai.contract_controller import get_active_traders, get_trader
from st2.ai.utils import get_tasks, queue_task
from st2.logging import logger
from st2.request import RequestMp
from st2.ship import Ship, buy_ship
from st2.system import System

DEBUG = True


@logger.catch  # catch errors in a separate thread
async def ai_start_system_controller(
    system_symbol,
    agent_symbol,
    qa_pairs,
    priority=2,
    interval=60,
    verbose=False,
):
    """
    Assign drones to supply the start system's basic needs

    This controller self-destructs after completing its task.
    """
    token = get_agent(agent_symbol)["token"]
    request = RequestMp(qa_pairs, priority, token)
    system = System(system_symbol, request, priority)

    # wait until all shipyards and marketplaces are charted & scouted
    while len(system.uncharted_markets()) + len(system.unscouted_markets()) != 0:
        await sleep(interval)
        system.refresh(refresh_graph=False)

    # load targeted probes
    target = {
        "siphon": 2,
        "extract_minerals": 0,
        "survey_minerals": 0,
        "extract_common_metals": 2,
        "survey_common_metals": 1,
        "extract_precious_metals": 0,
        "survey_precious_metals": 0,
        "extract_rare_metals": 0,
        "survey_rare_metals": 0,
    }

    # load assigned probes
    assigned = {}
    for k in target.keys():
        assigned[k] = 0
    for task in get_tasks(
        system_symbol=system.symbol,
        agent_symbol=agent_symbol,
        pname="traders",  # TODO: which pname: traders/probes/drones?
    ):
        for key in ["current", "queued"]:
            t = str(task[key]).split(" ")
            if t[0] == "siphon":
                assigned["siphon"] += 1
            if t[0] in ["extract", "survey"]:
                action, extract_wp = t[0:2]
                traits = system.waypoints[extract_wp]["traits"]
                if "COMMON_METAL_DEPOSITS" in traits:
                    assigned[f"{action}_common_metals"] += 1
                if "MINERAL_DEPOSITS" in traits:
                    assigned[f"{action}_minerals"] += 1
                if "PRECIOUS_METAL_DEPOSITS" in traits:
                    assigned[f"{action}_precious_metals"] += 1
                if "RARE_METAL_DEPOSITS" in traits:
                    assigned[f"{action}_rare_metals"] += 1

    while sum(target.values()) < sum(assigned.values()):
        seen = set()
        for k, v in target.items():
            if v <= assigned[k]:
                continue

            if k.startswith("siphon"):
                ship_type = "SHIP_SIPHON_DRONE"
                # task = f"siphon {system_symbol}"
            elif k.startswith("extract"):
                ship_type = "SHIP_MINING_DRONE"
            else:
                ship_type = "SHIP_SURVEYOR"
            best = None, {}
            for shipyard_symbol, md in system.shipyards_with(ship_type).items():
                if md["purchasePrice"] < best[1].get("purchasePrice", float("inf")):
                    best = shipyard_symbol, md
            shipyard_symbol, md = best

            cost = md["purchasePrice"]
            credits = get_agent_public(agent_symbol)["credits"]  # noqa
            supply = md["supply"]
            if credits < max(1_000_000, cost):
                if DEBUG:
                    logger.debug(
                        f"Start System Controller {system_symbol}: insufficient funds"
                    )
                break  # try again later
            if supply == "SCARCE":
                if ship_type in seen:
                    break
                seen.add(ship_type)
                if DEBUG:
                    logger.debug(
                        f"Start System Controller {system_symbol}: insufficient supply"
                    )
                continue  # try another ship_type

            # TODO: make sure a probe is present at the shipyard_symbol?
            ship = buy_ship(ship_type, shipyard_symbol, agent_symbol, request, verbose)

            if k.startswith("siphon"):
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
                task = f"siphon {siphon_wp} {sell_wp}"

            elif k.startswith("extract"):
                extract_wp = None  # TODO
                sell_wp = None
                task = f"survey {extract_wp} {sell_wp}"

            else:
                extract_wp = None  # TODO
                task = f"survey {extract_wp}"

            queue_task(ship, task)
            assigned[k] += 1

        await sleep(interval)

    if DEBUG:
        logger.debug(f"Start System Controller {system_symbol}: task completed")
    return "self destruct"
