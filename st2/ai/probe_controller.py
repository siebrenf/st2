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
    probe_markets=False,
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

    (
        probes2shipyards_selling_probes,
        probes_wo_task,
        unprobed_shipyards,
        unprobed_markets,
        unprobed_shipyards_selling_probes,
    ) = _get_probes_and_unprobed_waypoints(system, agent_symbol, pname)
    if len(unprobed_shipyards) == 0 and (
        probe_markets is False or len(unprobed_markets) == 0
    ):
        if DEBUG:
            logger.debug(f"probe controller {system_symbol} exiting")
        return "self destruct"

    # assign probes without task
    while len(probes_wo_task) > 0:
        ship = probes_wo_task.pop()
        wp_type = "shipyard"
        if unprobed_shipyards_selling_probes:
            waypoint_symbol = unprobed_shipyards_selling_probes.pop()
            probes2shipyards_selling_probes[ship] = waypoint_symbol
            unprobed_shipyards.discard(waypoint_symbol)
        elif unprobed_shipyards:
            waypoint_symbol = unprobed_shipyards.pop()
        elif unprobed_markets and probe_markets:
            wp_type = "market"
            waypoint_symbol = unprobed_markets.pop()
        else:
            break
        task = f"probe {wp_type} {waypoint_symbol}"
        queue_task(ship, task, pname=pname)
        _cancel_external_probe_task(task, agent_symbol)

    # assign an available ship to buy the first probe
    if len(probes2shipyards_selling_probes) == 0:
        ship = await _get_trader(system_symbol, agent_symbol, pname="traders")
        waypoint_symbol = unprobed_shipyards_selling_probes.pop()
        task = f"probe_purchase {waypoint_symbol}"
        queue_task(ship, task, pname="traders")
        while len(probes2shipyards_selling_probes) == 0:
            await sleep(60)
            (
                probes2shipyards_selling_probes,
                probes_wo_task,
                unprobed_shipyards,
                unprobed_markets,
                unprobed_shipyards_selling_probes,
            ) = _get_probes_and_unprobed_waypoints(system, agent_symbol, pname)

    for waypoints_to_probe, condition in zip(
        [unprobed_shipyards_selling_probes, unprobed_shipyards, unprobed_markets],
        [True, True, probe_markets],
    ):
        while len(waypoints_to_probe) > 0 and condition:
            await _buy_and_assign_probe(
                waypoints_to_probe,
                system,
                probes2shipyards_selling_probes,
                unprobed_shipyards_selling_probes,
                unprobed_shipyards,
                unprobed_markets,
                agent_symbol,
                pname,
                request,
                priority,
                verbose,
            )

    if DEBUG:
        logger.debug(f"probe controller {system_symbol} exiting")
    return "self destruct"


async def _buy_and_assign_probe(
    waypoints_to_probe,
    system,
    probes2shipyards_selling_probes,
    unprobed_shipyards_selling_probes,
    unprobed_shipyards,
    unprobed_markets,
    agent_symbol,
    pname,
    request,
    priority,
    verbose,
):
    shipyard_symbol = _get_shipyard(system, unprobed_shipyards_selling_probes)
    shipyard_probe = [
        k for k, v in probes2shipyards_selling_probes.items() if v == shipyard_symbol
    ][0]
    shipyard_probe = Ship(shipyard_probe, request, priority=priority)
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
    unprobed_shipyards_selling_probes.discard(waypoint_symbol)
    unprobed_shipyards.discard(waypoint_symbol)
    unprobed_markets.discard(waypoint_symbol)


def _get_shipyard(system, unprobed_shipyards_selling_probes):
    best = float("inf"), None
    for shipyards_symbol, shipyards_ship in system.shipyards_with("SHIP_PROBE").items():
        if shipyards_symbol in unprobed_shipyards_selling_probes:
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


def _get_probes_and_unprobed_waypoints(
    system,
    agent_symbol,
    pname,
):
    unprobed_shipyards = set(system.shipyards)
    if len(unprobed_shipyards) == 0:
        raise NotImplementedError(f"System {system.symbol} does not have shipyards!")
    unprobed_shipyards_selling_probes = set(system.shipyards_with("SHIP_PROBE"))
    if len(unprobed_shipyards_selling_probes) == 0:
        raise NotImplementedError(f"System {system.symbol} does not sell probes!")
    unprobed_markets = set(system.markets) - unprobed_shipyards
    with connect(
        "dbname=st2 user=postgres", row_factory=dict_row
    ) as conn, conn.cursor() as cur:
        assigned_ships = cur.execute(
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
            (agent_symbol, pname, agent_symbol, system.symbol),
        ).fetchall()

    probes2shipyards_selling_probes = {}
    probes_wo_task = set()
    for task in assigned_ships:
        ship = task["symbol"]
        if task["current"] is None:
            probes_wo_task.add(ship)
        elif task["current"].startswith("probe "):
            wp_type, waypoint_symbol = task["current"].split(" ")[1:]
            if wp_type == "shipyard":
                unprobed_shipyards.discard(waypoint_symbol)
                if waypoint_symbol in unprobed_shipyards_selling_probes:
                    probes2shipyards_selling_probes[ship] = waypoint_symbol
                    unprobed_shipyards_selling_probes.discard(waypoint_symbol)
            elif wp_type == "market":
                unprobed_markets.discard(waypoint_symbol)
            else:
                raise ValueError
    return (
        probes2shipyards_selling_probes,
        probes_wo_task,
        unprobed_shipyards,
        unprobed_markets,
        unprobed_shipyards_selling_probes,
    )


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
