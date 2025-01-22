from asyncio import sleep

from psycopg import connect

from st2.exceptions import GameError
from st2.logging import logger
from st2.pathing.travel import travel
from st2.pathing.utils import nav_score
from st2.ship import Ship, buy_ship
from st2.system import System


@logger.catch  # catch errors in a separate thread
async def ai_seed_system(
    ship_symbol,
    pname,
    qa_pairs,
    priority=3,
    verbose=False,
):
    """
    Assumption: any pre-existing probes meant for probing should have
    their task set to probe prior to starting this function.
    """
    ship = Ship(ship_symbol, qa_pairs, priority)
    ship.refresh()
    system_symbol = ship["nav"]["systemSymbol"]
    system = System(system_symbol, ship.request)
    shipyards = {wp: None for wp in system.shipyards_with("SHIP_PROBE")}
    markets = {wp: None for wp in system.markets if wp not in shipyards}
    if len(shipyards) == 0:
        raise NotImplementedError(f"System {system_symbol} does not sell probes!")
    if None not in list(markets.values()) + list(shipyards.values()):
        return stop_task(ship_symbol)

    if verbose:
        logger.info(f"{ship.name()} begun seeding system {system_symbol}")

    with connect("dbname=st2 user=postgres") as conn:
        with conn.cursor() as cur:
            # load probe overview
            cur.execute(
                """
                SELECT *
                FROM tasks
                WHERE "agentSymbol" = %s
                  AND "current" LIKE %s
                ORDER BY "symbol"
                """,
                [ship["agentSymbol"], f"probe % {system_symbol}-%"],
            )
            for probe_symbol, _, current, _, _, _, _ in cur.fetchall():
                task, waypoint_type, waypoint_symbol = current.split(" ")
                if waypoint_symbol in shipyards:
                    shipyards[waypoint_symbol] = probe_symbol
                else:
                    markets[waypoint_symbol] = probe_symbol

    # seed each shipyard
    wp_type = "shipyard"
    waypoints = [wp for (wp, probe) in shipyards.items() if probe is None]
    for waypoint_symbol in system.shortest_passing_path(
        waypoints, start=ship["nav"]["waypointSymbol"]
    ):
        if waypoint_symbol not in waypoints:
            continue
        # purchase & assign a probe at each shipyard
        await travel(ship, waypoint_symbol, verbose=verbose)
        probe_symbol = ship.buy_ship("SHIP_PROBE", verbose)
        task = f"probe {wp_type} {waypoint_symbol}"
        with connect("dbname=st2 user=postgres") as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE tasks
                    SET current = %s,
                        pname = %s
                    WHERE "symbol" = %s
                    """,
                    [task, pname, probe_symbol],
                )
        shipyards[waypoint_symbol] = probe_symbol

    # wait until all probes arrived to the shipyards
    for probe_symbol in shipyards.values():
        probe = Ship(probe_symbol, qa_pairs, priority)
        if t := probe.nav_remaining():
            await sleep(t)

    # seed each market
    wp_type = "market"
    waypoints = [wp for (wp, probe) in markets.items() if probe is None]
    for waypoint_symbol in waypoints:
        # select the shipyard to purchase a probe from
        shipyard_symbol = select_shipyard(waypoint_symbol, system)

        # purchase & assign a probe
        try:
            probe_symbol = buy_ship(
                ship_type="SHIP_PROBE",
                waypoint_symbol=shipyard_symbol,
                agent_symbol=ship["agentSymbol"],
                request=ship.request,
                verbose=verbose,
            )
        except GameError as e:
            if "Agent has insufficient funds." in str(e):
                return stop_task(ship_symbol)
            raise e
        ship.shipyard()
        task = f"probe {wp_type} {waypoint_symbol}"
        with connect("dbname=st2 user=postgres") as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE tasks
                    SET current = %s,
                        pname = %s
                    WHERE "symbol" = %s
                    """,
                    [task, pname, probe_symbol],
                )
        markets[waypoint_symbol] = probe_symbol

    # done
    if verbose:
        logger.info(f"{ship.name()} completed seeding system {system_symbol}!")
    stop_task(ship_symbol)


def select_shipyard(waypoint_symbol, system):
    """
    Select the shipyard to buy a probe from, based on distance and price.
    """
    best = float("inf"), None
    for shipyards_symbol, shipyards_ship in system.shipyards_with("SHIP_PROBE").items():
        price = shipyards_ship["purchasePrice"]
        if price is None:
            price = 28_000  # avg price
        distance = system.graph[shipyards_symbol][waypoint_symbol]["distance"]
        score = nav_score(distance, 3, reactor="REACTOR_SOLAR_I") + price
        if score < best[0]:
            best = score, shipyards_symbol
    shipyard_symbol = best[1]
    return shipyard_symbol


def stop_task(ship_symbol):
    """
    Remove this current task from the task table.
    """
    with connect("dbname=st2 user=postgres") as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE tasks
                SET current = %s
                WHERE "symbol" = %s
                """,
                [None, ship_symbol],
            )
