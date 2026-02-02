from asyncio import sleep

from psycopg import connect
from psycopg.rows import dict_row

from st2.agent import get_agent, get_agent_public
from st2.ai.utils import queue_task
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
    probe_markets=True,
    priority=2,
    verbose=False,
):
    """
    Send a probe to each SHIPYARD (and optionally MARKETPLACE).
    Buys probes if needed, using a trader if no probes are available.

    This controller self-destructs after completing its task.

    Note: if the Spymaster is in use, probe_markets should be set to False.
    """
    pname = "probes"
    token = get_agent(agent_symbol)["token"]
    request = RequestMp(qa_pairs, priority, token)
    system = System(system_symbol, request, priority)

    # ensure all shipyards are charted
    uncharted_markets = set(system.uncharted_markets())
    while uncharted_markets:
        ship = None
        tasks = _get_system_tasks(agent_symbol, system_symbol)
        for task in tasks:
            if str(task["current"]).startswith("scout"):
                uncharted_markets.discard(task["current"].split(" ")[1])
            if str(task["queued"]).startswith("scout"):
                uncharted_markets.discard(task["queued"].split(" ")[1])
            if task["pname"] == "traders" and task["queued"] is None or task["queued"].startswith("trade "):
                ship = task["ship"]
        if ship:
            uncharted_markets = set(system.uncharted_markets()) & uncharted_markets
            waypoint_symbol = uncharted_markets.pop()  # TODO: make non-random
            task = f"scout {waypoint_symbol}"
            queue_task(ship, task)
        await sleep(60)

    # non-overlapping sets of waypoints
    shipyards_selling_probes = set(system.shipyards_with("SHIP_PROBE"))
    shipyards = set(system.shipyards) - shipyards_selling_probes
    markets = set(system.markets) - set(system.shipyards)
    unprobed_shipyards_selling_probes = shipyards_selling_probes.copy()
    unprobed_shipyards = shipyards.copy()
    unprobed_markets = markets.copy()

    # load probes from DB
    shipyards_selling_probes2probes = dict()
    tasks = _get_system_tasks(agent_symbol, system_symbol)
    for task in tasks:
        if task["pname"] != "probes":
            continue
        ship = task["symbol"]
        if task["current"] is None:
            raise NotImplementedError("Probes should be assigned already")
        elif task["current"].startswith("probe "):
            wp_type, waypoint_symbol = task["current"].split(" ")[1:]
            if wp_type == "shipyard":
                if waypoint_symbol in unprobed_shipyards_selling_probes:
                    shipyards_selling_probes2probes[waypoint_symbol] = ship
                    unprobed_shipyards_selling_probes.discard(waypoint_symbol)
                else:
                    unprobed_shipyards.discard(waypoint_symbol)
            else:
                unprobed_markets.discard(waypoint_symbol)
        if task["queued"] is not None:
            raise NotImplementedError("Probes should not have queued tasks")
    if len(unprobed_shipyards) == 0 and (
        probe_markets is False or len(unprobed_markets) == 0
    ):
        if DEBUG:
            logger.debug(f"probe controller {system_symbol} exiting")
        return "self destruct"

    # assign an available ship to buy the first probe
    if len(shipyards_selling_probes2probes) == 0:
        if DEBUG:
            logger.debug(f"No probes at shipyards in {system_symbol}. Attempting to purchase one")
        ship = await _get_trader(system_symbol, agent_symbol, pname="traders")
        waypoint_symbol = unprobed_shipyards_selling_probes.pop()  # TODO: make non-random
        task = f"probe_purchase {waypoint_symbol}"
        queue_task(ship, task)
        while len(shipyards_selling_probes2probes) == 0:
            await sleep(60)
            tasks = _get_system_tasks(agent_symbol, system_symbol)
            for task in tasks:
                if task["pname"] != "probes":
                    continue
                if task["current"] == f"probe shipyard {waypoint_symbol}":
                    shipyards_selling_probes2probes[waypoint_symbol] = task["symbol"]
                    unprobed_shipyards_selling_probes.discard(waypoint_symbol)

    for waypoints_to_probe, condition in zip(
        [unprobed_shipyards_selling_probes, unprobed_shipyards, unprobed_markets],
        [True, True, probe_markets],
    ):
        while len(waypoints_to_probe) > 0 and condition:
            await _buy_and_assign_probe(
                waypoints_to_probe,
                system,
                shipyards_selling_probes2probes,
                agent_symbol,
                pname,
                request,
                priority,
                verbose,
            )

    if DEBUG:
        logger.debug(f"probe controller {system_symbol} exiting")
    return "self destruct"


def _get_system_tasks(agent_symbol, system_symbol):
    with connect(
        "dbname=st2 user=postgres", row_factory=dict_row
    ) as conn, conn.cursor() as cur:
        tasks = cur.execute(
            """
            SELECT * FROM "tasks" 
            WHERE "agentSymbol" = %s 
            AND "symbol" IN (
                SELECT "symbol" FROM "ships"
                WHERE "agentSymbol" = %s
                AND "nav" ->> 'systemSymbol' = %s
            )
            """,
            (agent_symbol, agent_symbol, system_symbol),
        ).fetchall()
    return tasks


async def _get_trader(system_symbol, agent_symbol, pname):
    while True:
        with connect(
            "dbname=st2 user=postgres", row_factory=dict_row
        ) as conn, conn.cursor() as cur:
            other_ships = cur.execute(
                """
                SELECT * FROM "tasks" 
                WHERE "agentSymbol" = %s 
                AND "pname" = %s
                AND "symbol" IN (
                    SELECT "symbol" FROM "ships"
                    WHERE "agentSymbol" = %s
                    AND "nav" ->> 'systemSymbol' = %s
                )
                """,
                (agent_symbol, pname, agent_symbol, system_symbol),
            ).fetchall()
            for task in other_ships:
                if task["queued"] is None or task["queued"].startswith("trade "):
                    return task["ship"]
            if DEBUG:
                logger.debug(f"No ships available in {system_symbol}. Sleeping")
            await sleep(60)


async def _buy_and_assign_probe(
    waypoints_to_probe,
    system,
    shipyards_selling_probes2probes,
    agent_symbol,
    pname,
    request,
    priority,
    verbose,
):
    # TODO: this is terrible. it should rerun if any condition is false, in case the market changes
    shipyard_symbol = _get_shipyard(system, shipyards_selling_probes2probes)
    shipyard_probe = Ship(shipyards_selling_probes2probes[shipyard_symbol], request, priority=priority)
    if t := shipyard_probe.nav_remaining():
        await sleep(t)
    credits = get_agent_public(agent_symbol)["credits"]
    supply = system.shipyards_with("SHIP_PROBE")[shipyard_symbol]["supply"]
    while credits < 500_000 or supply == "SCARCE":
        await sleep(60)
        credits = get_agent_public(agent_symbol)["credits"]
        supply = system.shipyards_with("SHIP_PROBE")[shipyard_symbol]["supply"]
    probe_symbol = buy_ship(
        "SHIP_PROBE", shipyard_symbol, agent_symbol, request, verbose
    )
    waypoint_symbol = waypoints_to_probe.pop()
    wp_type = "shipyard" if waypoint_symbol in system.shipyards else "market"
    task = f"probe {wp_type} {waypoint_symbol}"
    queue_task(probe_symbol, task, pname=pname)
    _cancel_external_probe_task(task, agent_symbol)


def _get_shipyard(system, shipyards_selling_probes2probes):
    best = float("inf"), None
    for shipyards_symbol, shipyards_ship in system.shipyards_with("SHIP_PROBE").items():
        if shipyards_symbol not in shipyards_selling_probes2probes:
            continue
        price = shipyards_ship.get("purchasePrice")
        if price is None:
            price = 28_000  # avg price
        if price < best[0]:
            best = price, shipyards_symbol
    shipyard_symbol = best[1]
    return shipyard_symbol


def _cancel_external_probe_task(task, agent_symbol):
    """
    Cancel probe tasks of other probe(s) at the waypoint
    """
    with connect("dbname=st2 user=postgres") as conn, conn.cursor() as cur:
        cur.execute(
            """
            UPDATE tasks
            SET "cancel" = %s
            WHERE "current" = %s
              AND "agentSymbol" != %s
            """,
            (True, task, agent_symbol),
        )
