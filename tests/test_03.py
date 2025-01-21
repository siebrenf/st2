import multiprocessing as mp
from uuid import uuid1

from psycopg import connect

from st2.ai import taskmaster
from st2.startup import api_server, db_server, game_server


def test_taskmaster():
    game_server()  # TODO: move to separate test
    db_server()
    manager, api_handler, qa_pairs = api_server()

    pname = "test_process"
    pid = uuid1()
    test_process = mp.Process(
        target=taskmaster,
        kwargs={"pname": pname, "pid": pid, "qa_pairs": qa_pairs},
    )
    test_process.start()

    with connect("dbname=st2 user=postgres") as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO tasks (symbol, agentSymbol, current, queued, cancel, pname, pid) 
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (symbol) DO NOTHING
            """,
            ("ship-1", "a123", None, "test name1", False, pname, None),
        )
        conn.commit()

        # TODO: create dummy file and test for existence?

        cur.execute(
            "DELETE FROM tasks WHERE symbol = %s",
            ("ship-1",),
        )
        conn.commit()

    test_process.terminate()
    test_process.join()
