import multiprocessing as mp

from psycopg import connect
from psycopg.rows import dict_row

from st2 import time
from st2.ai import taskmaster
from st2.request import RequestMp
from st2.ship import Ship
from st2.startup import api_server, db_server, game_server
from tests.test_04 import get_test_agent


def test_ai_probe_waypoint():
    game_server()
    db_server()
    manager, api_handler, qa_pairs = api_server()
    request = RequestMp(qa_pairs)

    pname = "test_process"
    test_process = mp.Process(
        target=taskmaster,
        kwargs={"pname": pname, "qa_pairs": qa_pairs},
    )
    test_process.start()

    agent_symbol = get_test_agent(request)
    probe = f"{agent_symbol}-2"
    ship = Ship(probe, qa_pairs, 0)
    waypoint = ship["nav"]["waypointSymbol"]

    t0 = time.now()
    with connect("dbname=st2 user=postgres", row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE tasks
                SET current = %s,
                    pname = %s
                WHERE symbol = %s
                """,
                [f"probe shipyard {waypoint}", pname, probe],
            )
            conn.commit()

            time.sleep(1)

            cur.execute(
                """
                SELECT * 
                FROM market_tradegoods
                WHERE "waypointSymbol" = %s
                ORDER BY "timestamp" DESC
                """,
                [waypoint],
            )
            tg = cur.fetchone()

    test_process.terminate()
    test_process.join()
    with connect("dbname=st2 user=postgres") as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE tasks
                SET current = %s,
                    pname = %s,
                    pid = %s
                WHERE symbol = %s
                """,
                [None, None, None, probe],
            )

    assert tg is not None
    assert tg["timestamp"] > t0, tg
