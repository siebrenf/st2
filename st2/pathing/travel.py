import math
from asyncio import sleep

import networkx as nx

from st2.logging import logger
from st2.system import System

from .utils import FUEL_WEIGHT, TIME_WEIGHT, nav_fuel, nav_fuel_inv, nav_time


@logger.catch  # catch errors in a separate thread
async def travel(
    ship,
    destination,
    explore=True,
    verbose=True,
):
    """
    Navigate the ship to the destination waypoint.
    Examples:
      asyncio.run(travel(ship, destination))

      asyncio.run(await asyncio.gather(travel(s1, t2), travel(s2, t2)))
    """
    if ship["nav"]["waypointSymbol"] == destination:
        if t := ship.nav_remaining():
            await sleep(t)

    elif ship["frame"]["symbol"] == "FRAME_PROBE":
        ship.navigate(destination, verbose)
        await sleep(ship.nav_remaining())

    else:
        system = System(ship["nav"]["systemSymbol"], ship.request)
        fuel_stops = system.markets_with("FUEL", "sells")
        path, edges = get_path(ship, destination, fuel_stops, system)
        for i, waypoint_symbol in enumerate(path):
            if waypoint_symbol != ship["nav"]["waypointSymbol"]:
                ship.nav_patch(edges["modes"][i - 1])
                ship.navigate(waypoint_symbol, verbose)
            await sleep(ship.nav_remaining())
            if waypoint_symbol in fuel_stops:
                ship.refuel()
            if explore:
                if waypoint_symbol in system.shipyards:
                    ship.shipyard()
                if waypoint_symbol in system.markets:
                    ship.market()

    if verbose:
        logger.info(f"{ship.name()} has arrived at {destination}")


def get_path(ship, destination, fuel_stops, system):
    """
    Simple setup: fuel stops only
    """
    origin = ship["nav"]["waypointSymbol"]
    speed = ship["engine"]["speed"]
    ssg = nx.Graph()
    for mode in ["BURN", "CRUISE", "DRIFT"]:
        dist_max = nav_fuel_inv(ship["fuel"]["capacity"], mode)
        graph = nx.subgraph_view(
            system.graph,
            filter_node=lambda n: n in fuel_stops,
            filter_edge=lambda n1, n2: system.graph[n1][n2]["distance"] <= dist_max,
        )
        for n1, n2, md in graph.edges(data=True):
            if (n1, n2) in ssg.edges and "mode" in ssg[n1][n2]:
                continue
            if mode == "BURN" and md["distance"] < 1:
                continue
            md["fuel"] = nav_fuel(mode=mode, distance=md["distance"])
            md["time"] = nav_time(speed=speed, mode=mode, distance=md["distance"])
            md["score"] = md["fuel"] * FUEL_WEIGHT + md["time"] * TIME_WEIGHT
            md["mode"] = mode
            ssg.add_edge(n1, n2, **md)

    score, path = nx.bidirectional_dijkstra(ssg, origin, destination, weight="score")

    edges = {
        "modes": [],
        "fuel": [],
        "time": [],
        "dist": [],
    }
    n1 = path[0]
    for n2 in path[1:]:
        edges["modes"].append(ssg[n1][n2]["mode"])
        edges["fuel"].append(ssg[n1][n2]["fuel"])
        edges["time"].append(ssg[n1][n2]["time"])
        edges["dist"].append(math.ceil(ssg[n1][n2]["distance"]))
        n1 = n2

    return path, edges
