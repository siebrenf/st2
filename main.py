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
    request = RequestMp(qa_pairs, priority=1, token=None)

    # load the player ship
    import os
    from psycopg import connect
    from st2.ship import Ship, ShipNotFoundError
    from st2.agent import register_agent
    from st2.system import System

    agent_symbol = os.environ["ST_AGENT_SYMBOL"]
    try:
        ship = Ship(f"{agent_symbol}-1", request)
        system = System(ship["nav"]["systemSymbol"], request)
    except ShipNotFoundError:
        register_agent(
            request,
            priority=1,
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
        # scout the first two markets
        ship = Ship(f"{agent_symbol}-1", request)
        ship.market()
        Ship(f"{agent_symbol}-2", request).market()
        # log gate construction status (and the system's waypoints)
        system = System(ship["nav"]["systemSymbol"], request)
        gate = system.gate["symbol"]
        _ = system.get_construction(gate)
        # send the probe to a shipyard with additional probes
        waypoint_symbol = (
                set(system.shipyards_with("SHIP_PROBE")) &
                set(system.shipyards_with('SHIP_LIGHT_SHUTTLE'))
        ).pop()
        task = f"probe shipyard {waypoint_symbol}"
        with connect("dbname=st2 user=postgres") as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE tasks
                SET "current" = %s, 
                    "pname" = %s
                WHERE "symbol" = %s
                """,
                (task, "probes", f"{agent_symbol}-2"),
            )

    # start trading & probing
    with connect("dbname=st2 user=postgres") as conn, conn.cursor() as cur:
        system_symbol = ship["nav"]["systemSymbol"]
        symbol = f"trade_controller {system_symbol}"
        cur.execute(
            """
            INSERT INTO tasks ("symbol", "agentSymbol", "current", "queued", "cancel", "pname", "pid")
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT ("symbol") DO UPDATE
            SET "current" = EXCLUDED."current",
            "agentSymbol" = EXCLUDED."agentSymbol"
            """,
            (symbol, agent_symbol, symbol, None, False, "traders", None),
        )
        symbol = f"contract_controller {agent_symbol}"
        cur.execute(
            """
            INSERT INTO tasks ("symbol", "agentSymbol", "current", "queued", "cancel", "pname", "pid")
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT ("symbol") DO UPDATE
            SET "current" = EXCLUDED."current"
            """,
            (symbol, agent_symbol, symbol, None, False, "traders", None),
        )
        symbol = f"construction_controller {system_symbol}"
        cur.execute(
            """
            INSERT INTO tasks ("symbol", "agentSymbol", "current", "queued", "cancel", "pname", "pid")
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT ("symbol") DO UPDATE
            SET "current" = EXCLUDED."current",
            "agentSymbol" = EXCLUDED."agentSymbol"
            """,
            (symbol, agent_symbol, symbol, None, False, "traders", None),
        )
        # too many API requests!
        # symbol = "spymaster_controller"
        # cur.execute(
        #     """
        #     INSERT INTO tasks ("symbol", "agentSymbol", "current", "queued", "cancel", "pname", "pid")
        #     VALUES (%s, %s, %s, %s, %s, %s, %s)
        #     ON CONFLICT ("symbol") DO UPDATE
        #     SET "current" = EXCLUDED."current"
        #     """,
        #     (symbol, agent_symbol, symbol, None, False, "probes", None),
        # )
        symbol = "advisor_controller"
        cur.execute(
            """
            INSERT INTO tasks ("symbol", "agentSymbol", "current", "queued", "cancel", "pname", "pid")
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT ("symbol") DO UPDATE
            SET "current" = EXCLUDED."current"
            """,
            (symbol, None, symbol, None, False, "probes", None),
        )
        symbol = f"probe_controller {system_symbol}"
        cur.execute(
            """
            INSERT INTO tasks ("symbol", "agentSymbol", "current", "queued", "cancel", "pname", "pid")
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT ("symbol") DO UPDATE
            SET "current" = EXCLUDED."current",
            "agentSymbol" = EXCLUDED."agentSymbol"
            """,
            (symbol, agent_symbol, symbol, None, False, "probes", None),
        )
        symbol = f"start_system_controller {system_symbol}"
        cur.execute(
            """
            INSERT INTO tasks ("symbol", "agentSymbol", "current", "queued", "cancel", "pname", "pid")
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT ("symbol") DO UPDATE
            SET "current" = EXCLUDED."current",
            "agentSymbol" = EXCLUDED."agentSymbol"
            """,
            (symbol, agent_symbol, symbol, None, False, "drones", None),
        )

    # start background processes
    import atexit
    import multiprocessing as mp
    from st2.ai import taskmaster
    from st2.ai.reset_controller import ai_reset_controller
    from st2 import time

    # clear all previous time-sensitive tasks
    ai_reset_controller()

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

    time.sleep(15)

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

    pname = "drones"
    drone_taskmaster = mp.Process(
        target=taskmaster,
        kwargs={"pname": pname, "qa_pairs": qa_pairs},
    )


    def stop_drone_taskmaster():
        drone_taskmaster.terminate()
        drone_taskmaster.join()


    atexit.register(stop_drone_taskmaster)
    drone_taskmaster.start()

    # run forever
    time.sleep(1e9)
