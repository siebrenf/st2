import multiprocessing as mp

from psycopg import connect

from st2 import time
from st2.ai import taskmaster
from st2.db import get_table, get_tables
from st2.startup import api_server, game_server


def test_game_server():
    game_server()

    tables = get_tables()
    assert "ships" in tables

    header = next(get_table("agents"))
    assert header == ["symbol", "token", "role", "faction", "other"]


def test_taskmaster():
    game_server()
    manager, api_handler, qa_pairs = api_server()

    pname = "test_process"
    test_process = mp.Process(
        target=taskmaster,
        kwargs={"pname": pname, "qa_pairs": qa_pairs},
    )
    test_process.start()

    task_start = ("ship-1", "a123", None, "test process 1", False, pname, None)
    with connect("dbname=st2 user=postgres") as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO tasks ("symbol", "agentSymbol", "current", "queued", "cancel", "pname", "pid")
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            task_start,
        )
        conn.commit()

        time.sleep(0.75)

        task_midway = cur.execute(
            """SELECT * FROM tasks WHERE symbol = %s""", ("ship-1",)
        ).fetchone()

        time.sleep(1.25)

        task_end = cur.execute(
            """SELECT * FROM tasks WHERE symbol = %s""", ("ship-1",)
        ).fetchone()

        cur.execute(
            "DELETE FROM tasks WHERE symbol = %s",
            ("ship-1",),
        )

    test_process.terminate()
    test_process.join()

    # task is queued
    assert task_start[:-1] == (
        "ship-1",
        "a123",
        None,
        "test process 1",
        False,
        pname,
    ), task_start

    # task is current
    assert task_midway[:-1] == (
        "ship-1",
        "a123",
        "test process 1",
        None,
        False,
        pname,
    ), task_midway

    # task is done
    assert task_end[:-1] == ("ship-1", "a123", None, None, False, pname), task_end
