from asyncio import sleep

from st2.agent import get_agent, get_agent_public
from st2.ai.contract_controller import get_active_traders, get_trader
from st2.ai.utils import queue_task
from st2.logging import logger
from st2.request import RequestMp
from st2.system import System

DEBUG = True


@logger.catch  # catch errors in a separate thread
async def ai_construction_controller(
    system_symbol,
    agent_symbol,
    qa_pairs,
    priority=2,
    interval=60,
):
    """
    Construct the system's gate.

    This controller self-destructs after completing its task.
    """
    token = get_agent(agent_symbol)["token"]
    request = RequestMp(qa_pairs, priority, token)
    system = System(system_symbol, request, priority)

    # wait until all shipyards and marketplaces are charted & scouted
    while len(system.uncharted_markets()) + len(system.unscouted_markets()) != 0:
        await sleep(interval)
        system.refresh(refresh_graph=False)

    gate_symbol = system.gate["symbol"]
    construction = system.get_construction(gate_symbol)
    while not construction["isComplete"]:
        for material in construction["materials"]:
            units = material["required"] - material["fulfilled"]
            if units <= 0:
                continue  # next good
            good = material["tradeSymbol"]

            # currently active tasks in this system
            ship_tasks = get_active_traders(agent_symbol, system_symbol)
            available_traders = set()
            current = 0
            queued = 0
            for tasks in ship_tasks:
                ship = tasks["symbol"]
                if (
                    tasks["current"] is None
                    or tasks["queued"] is None
                    or tasks["queued"].startswith("trade ")
                ):
                    available_traders.add(ship)

                for key in ["current", "queued"]:
                    if str(tasks[key]).startswith("supply "):
                        task_split = tasks[key].split(" ")
                        if task_split[1] == good:
                            u = int(task_split[2])
                            units -= u
                            if key == "current":
                                current += u
                            else:
                                queued += u

            if units <= 0:
                continue  # remaining units are already tasked
            if DEBUG:
                logger.debug(
                    f"{len(available_traders)} ships available to supply {good} to gate {gate_symbol}"
                )
            if len(available_traders) == 0:
                break  # try again later

            # select the cheapest waypoint to purchase the goods from
            best = None, float("inf"), dict()
            for purchase_wp, md in system.markets_with(good, "sells").items():
                if md["supply"] in ["SCARCE", "LIMITED"]:
                    continue
                price = md["purchasePrice"]
                if price and price < best[1]:
                    best = purchase_wp, price, md
            purchase_wp, price, md = best
            if purchase_wp is None:
                continue  # next good
            # trade max 1 tv per task
            units = min(units, md["tradeVolume"])

            cost = 2 * price * units
            credits = get_agent_public(agent_symbol)["credits"]  # noqa
            if credits < max(1_000_000, cost):
                if DEBUG:
                    logger.debug(f"Too poor for construction work")
                break  # try again later

            # select a ship to deliver the goods
            ship, units = get_trader(available_traders, units)
            task = f"supply {good} {units} {purchase_wp} {gate_symbol}"
            queue_task(ship, task)
            queued += units
            if DEBUG:
                remaining = (
                    material["required"] - material["fulfilled"] - current - queued
                )
                logger.debug(
                    "Construction supplies: "
                    f"{remaining} remaining/"
                    f"{current} currently underway/"
                    f"{queued} queued underway/"
                    f"{material['fulfilled']} fulfilled/"
                    f"{material['required']} total {good}"
                )
            break

        await sleep(interval)
        construction = system.get_construction(gate_symbol)

    if DEBUG:
        logger.debug(f"Construction Controller {system_symbol}: task completed")
    return "self destruct"
