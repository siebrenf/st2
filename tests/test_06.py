from st2.pathing.travel import get_path
from st2.request import RequestMp
from st2.ship import Ship
from st2.startup import api_server, db_server, game_server
from st2.system import System
from tests.test_04 import get_test_agent


def test_get_path():
    game_server()
    db_server()
    manager, api_handler, qa_pairs = api_server()
    request = RequestMp(qa_pairs)

    agent_symbol = get_test_agent(request)
    ship_symbol = f"{agent_symbol}-1"
    ship = Ship(ship_symbol, qa_pairs, 0)
    system = System(ship["nav"]["systemSymbol"], ship.request)
    fuel_stops = system.markets_with("FUEL", "sells")

    origin = ship["nav"]["waypointSymbol"]
    for destination in fuel_stops:
        path, edges = get_path(ship, destination, fuel_stops, system)
        assert path[0] == origin
        assert path[-1] == destination
        if edges["fuel"]:
            assert len(path) > 1
            assert max(edges["fuel"]) <= ship["fuel"]["capacity"]
        else:
            assert len(path) == 1
        assert len(path) == len(edges["modes"]) + 1
