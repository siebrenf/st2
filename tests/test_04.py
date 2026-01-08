import pytest
from psycopg import connect
from psycopg.rows import dict_row

from st2.agent import register_agent
from st2.exceptions import GameError
from st2.logging import logger
from st2.request import RequestMp
from st2.ship import Ship
from st2.startup import api_server, game_server


def get_test_agent(request):
    faction = "COSMIC"
    prefix = "UNITTEST"
    min_credits = 10_000
    with connect(
        "dbname=st2 user=postgres", row_factory=dict_row
    ) as conn, conn.cursor() as cur:
        # Get the latest test agent in the database
        cur.execute(
            """
            SELECT * FROM agents_public
            WHERE symbol ~ %s
            ORDER BY CAST(SUBSTRING(symbol FROM %s) AS INTEGER) DESC
            LIMIT 1
            """,
            [f"^{prefix}[0-9]+$", f"{prefix}([0-9]+)"],
        )
        agent = cur.fetchone()

        # Register a new test agent if not in the database or broke
        n = int(agent["symbol"][8:]) if agent else 0
        while agent is None or agent["credits"] < min_credits:
            agent_symbol = f"{prefix}{n:003}"
            try:
                register_agent(request, 0, agent_symbol, faction)
            except Exception as e:
                logger.debug(
                    f"{str(type(e)).split("'")[1]} from register_agent() in get_test_agent(): {e}"
                )
                n += 1
                continue

            cur.execute(
                """
                SELECT * FROM agents_public
                WHERE symbol = %s
                """,
                (agent_symbol,),
            )
            agent = cur.fetchone()

    agent_symbol = f"{prefix}{n:003}"
    assert agent["symbol"] == agent_symbol, agent
    assert agent["startingFaction"] == faction, agent
    return agent_symbol


def test_integration():
    game_server()
    manager, api_handler, qa_pairs = api_server()
    request = RequestMp(qa_pairs)

    agent_symbol = get_test_agent(request)

    # Check agent related databases
    with connect("dbname=st2 user=postgres", row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT * FROM agents_public
                WHERE symbol = %s
                """,
                (agent_symbol,),
            )
            agent_public = cur.fetchone()
            assert sorted(agent_public) == sorted(
                [
                    "accountId",
                    "symbol",
                    "headquarters",
                    "credits",
                    "startingFaction",
                    "shipCount",
                    "timestamp",
                ]
            )
            assert agent_public["symbol"] == agent_symbol

            cur.execute(
                """
                SELECT * FROM contracts
                WHERE "agentSymbol" = %s
                """,
                (agent_symbol,),
            )
            contract = cur.fetchone()
            assert sorted(contract) == sorted(
                [
                    "id",
                    "agentSymbol",
                    "factionSymbol",
                    "type",
                    "terms",
                    "accepted",
                    "fulfilled",
                    "deadlineToAccept",
                ]
            )

            cur.execute(
                """
                SELECT * FROM ships
                WHERE "symbol" = %s
                """,
                (agent_symbol + "-1",),
            )
            ship = cur.fetchone()
            assert sorted(ship) == sorted(
                [
                    "symbol",
                    "agentSymbol",
                    "nav",
                    "crew",
                    "fuel",
                    "cooldown",
                    "frame",
                    "reactor",
                    "engine",
                    "modules",
                    "mounts",
                    "registration",
                    "cargo",
                ]
            )
            assert ship["symbol"].startswith(agent_symbol)
            assert ship["frame"]["symbol"] == "FRAME_FRIGATE"

            cur.execute(
                """
                SELECT * FROM ships
                WHERE "symbol" = %s
                """,
                (agent_symbol + "-2",),
            )
            ship = cur.fetchone()
            assert sorted(ship) == sorted(
                [
                    "symbol",
                    "agentSymbol",
                    "nav",
                    "crew",
                    "fuel",
                    "cooldown",
                    "frame",
                    "reactor",
                    "engine",
                    "modules",
                    "mounts",
                    "registration",
                    "cargo",
                ]
            )
            assert ship["symbol"].startswith(agent_symbol)
            assert ship["frame"]["symbol"] == "FRAME_PROBE"

    # Instantiate a Ship
    probe = Ship(agent_symbol + "-2", request)

    # basic API commands
    probe.orbit()
    assert probe["nav"]["status"] == "IN_ORBIT"
    probe.orbit()
    assert probe["nav"]["status"] == "IN_ORBIT"
    probe.dock()
    assert probe["nav"]["status"] == "DOCKED"

    # impossible API command
    with pytest.raises(GameError) as e:
        probe.chart()
    assert "Waypoint already charted" in str(e)

    # complex API commands
    shipyard = probe.shipyard()
    assert sorted(shipyard) == sorted(
        ["symbol", "shipTypes", "transactions", "ships", "modificationsFee"]
    )
    assert {"type": "SHIP_MINING_DRONE"} in shipyard["shipTypes"]

    market = probe.market()
    assert sorted(market) == sorted(
        ["symbol", "imports", "exports", "exchange", "transactions", "tradeGoods"]
    )

    ship = Ship(f"{agent_symbol}-1", request)
    ship.nav_patch("CRUISE")
    assert ship["nav"]["flightMode"] == "CRUISE"
    ship.nav_patch("BURN")
    assert ship["nav"]["flightMode"] == "BURN"

    price = ship.buy("FUEL", 2)
    assert price > 1, price
    ship.jettison("FUEL", 1, verbose=True)
    price = ship.sell("FUEL", 1)
    assert price > 1, price

    # Check ship related databases
    with connect("dbname=st2 user=postgres", row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT * FROM market_transactions
                WHERE "shipSymbol" = %s
                ORDER BY "timestamp" DESC
                LIMIT 1
                """,
                (agent_symbol + "-1",),
            )
            transaction = cur.fetchone()
    assert transaction["waypointSymbol"] == ship["nav"]["waypointSymbol"]
    assert transaction["tradeSymbol"] == "FUEL"
    assert transaction["type"] == "SELL"
    assert transaction["units"] == 1
