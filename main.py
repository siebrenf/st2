"""
Create a number of FIFO queues in priority order (high -> low) and start the `api_handler` process.
Now, any process can make API requests using helper class `Request(qa_pairs)`.

Example:
    ```
    from st2.requests import RequestMp

    request = RequestMp(qa_pairs)
    request.get(endpoint="my/ships", priority=3, token="abc123")
    ```
"""

if __name__ == "__main__":
    # load the backend
    from st2.startup import game_server, api_server
    from st2.request import RequestMp

    game_server()
    manager, api_handler, qa_pairs = api_server()
    request = RequestMp(qa_pairs, priority=0, token=None)

    # load the player ship
    import os
    from psycopg import connect
    from st2.ship import Ship, ShipNotFoundError
    from st2.agent import register_agent

    agent_symbol = os.environ["ST_AGENT_SYMBOL"]
    try:
        ship = Ship(f"{agent_symbol}-1", request)
    except ShipNotFoundError:
        register_agent(
            request,
            priority=0,
            symbol=agent_symbol,
            faction="COSMIC",
        )
        with connect("dbname=st2 user=postgres") as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE agents
                SET role = %s
                WHERE symbol = %s
                """,
                ("player", agent_symbol),
            )
            cur.execute(
                """
                UPDATE tasks
                SET "pname" = %s
                WHERE "symbol" = %s
                """,
                ("traders", f"{agent_symbol}-1"),
            )
            cur.execute(
                """
                UPDATE tasks
                SET "pname" = %s
                WHERE "symbol" = %s
                """,
                ("probes", f"{agent_symbol}-2"),
            )
        ship = Ship(f"{agent_symbol}-1", request)
        # from st2.system import System
        #
        # system = System(ship["nav"]["systemSymbol"], request)
        # _ = system.waypoints  # make sure all waypoints are loaded intro the DB

    # start trading & probing
    with connect("dbname=st2 user=postgres") as conn, conn.cursor() as cur:
        system_symbol = ship["nav"]["systemSymbol"]
        symbol = f"trade_controller {system_symbol}"
        cur.execute(
            """
            INSERT INTO tasks ("symbol", "agentSymbol", "current", "queued", "cancel", "pname", "pid")
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT ("symbol") DO UPDATE
            SET "current" = EXCLUDED."current"
            """,
            (symbol, agent_symbol, symbol, None, False, "traders", None),
        )
        symbol = "contract_controller"
        cur.execute(
            """
            INSERT INTO tasks ("symbol", "agentSymbol", "current", "queued", "cancel", "pname", "pid")
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT ("symbol") DO UPDATE
            SET "current" = EXCLUDED."current"
            """,
            (symbol, agent_symbol, symbol, None, False, "traders", None),
        )
        symbol = f"probe_controller {system_symbol}"
        cur.execute(
            """
            INSERT INTO tasks ("symbol", "agentSymbol", "current", "queued", "cancel", "pname", "pid")
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT ("symbol") DO UPDATE
            SET "current" = EXCLUDED."current"
            """,
            (symbol, agent_symbol, symbol, None, False, "probes", None),
        )

    # start background processes
    import atexit
    import multiprocessing as mp
    from st2.ai import taskmaster
    from st2 import time

    pname = "probes"
    probe_taskmaster = mp.Process(
        target=taskmaster,
        kwargs={"pname": pname, "qa_pairs": qa_pairs},
    )

    def stop_probe_taskmaster():
        probe_taskmaster.terminate()
        probe_taskmaster.join()


    atexit.register(stop_probe_taskmaster)
    probe_taskmaster.start()

    # allow the probes to "warm up"
    time.sleep(10)

    pname = "traders"
    trade_taskmaster = mp.Process(
        target=taskmaster,
        kwargs={"pname": pname, "qa_pairs": qa_pairs},
    )


    def stop_trade_taskmaster():
        trade_taskmaster.terminate()
        trade_taskmaster.join()


    atexit.register(stop_trade_taskmaster)
    trade_taskmaster.start()




    # update databases
    from st2.spies import spymasters_apprentice
    sa = mp.Process(
        target=spymasters_apprentice,
        kwargs={
            "system_symbol": ship["nav"]["systemSymbol"],
            "request": request,
            "priority": 2,
        },
    )
    sa.start()

    # TODO: create one long priority 3 background processes
    from time import sleep
    from st2.stargazers import merchant, ambassador, astronomer, cartographer
    from st2.spies import spymaster, detective, private_eye

    def background_processes(request):
        merchant(request, priority=3)
        ambassador(request, priority=3)
        astronomer(request, priority=3)
        cartographer(request, priority=3, chart="start systems")
        cartographer(request, priority=3, chart="gate systems")
        detective(request, priority=3)
        spymaster(request, priority=3)
        while True:
            sleep(3600)
            private_eye(request, priority=3)

    bp = mp.Process(
        target=background_processes,
        kwargs={"request": request},
    )
    bp.start()