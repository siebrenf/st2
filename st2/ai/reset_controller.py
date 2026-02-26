import os

from psycopg import connect

from st2.logging import logger

DEBUG = True


def ai_reset_controller():
    """
    Execute this function on script restart **before** starting the taskmasters,
    in order to clear all time-sensitive tasks.
    """
    active_agents = [os.environ["ST_AGENT_SYMBOL"], None]
    tasks_to_clear = ["trade", "supply", "deliver"]
    reason = "script reset"
    with connect("dbname=st2 user=postgres") as conn, conn.cursor() as cur:
        for (
            ship_symbol,
            agent_symbol,
            current_task,
            queued_task,
            cancel_task,
            pname,
            pid,
        ) in cur.execute("""SELECT * FROM tasks""").fetchall():
            if agent_symbol not in active_agents:
                if pname == "probes" and not ship_symbol.startswith("probe_controller"):
                    continue  # probes may continue
                # destroy controller tasks, terminate ship tasks
                if "_controller" in ship_symbol:
                    if DEBUG:
                        reason = f"inactive agent {agent_symbol}"
                        logger.debug(
                            f"Reset Controller: Destroying {ship_symbol} {reason=}"
                        )
                    cur.execute(
                        """
                        DELETE FROM tasks
                        WHERE symbol = %s
                        """,
                        (ship_symbol,),
                    )
                else:
                    if (current_task or queued_task) and DEBUG:
                        reason = f"inactive agent {agent_symbol}"
                        logger.debug(
                            f"Reset Controller: Cleared the tasks of {ship_symbol} {reason=}"
                        )
                    current_task = None
                    queued_task = None
                    cancel_task = False
                    cur.execute(
                        """
                        UPDATE tasks
                        SET current = %s,
                            queued = %s,
                            cancel = %s
                        WHERE symbol = %s
                        """,
                        (current_task, queued_task, cancel_task, ship_symbol),
                    )

            if cancel_task:
                current_task = None
                cancel_task = False
                cur.execute(
                    """
                    UPDATE tasks
                    SET current = %s,
                        cancel = %s
                    WHERE symbol = %s
                    """,
                    (current_task, cancel_task, ship_symbol),
                )

            if current_task:
                args = current_task.split(" ")
                if args[0] in tasks_to_clear:
                    good = args[1]
                    if good not in _ship_cargo(ship_symbol, cur):
                        current_task = None
                        cur.execute(
                            """
                            UPDATE tasks
                            SET current = %s
                            WHERE symbol = %s
                            """,
                            (current_task, ship_symbol),
                        )
                        if DEBUG:
                            task = " ".join(args)
                            logger.debug(
                                f"Reset Controller: cleared current {task=} for {ship_symbol} {reason=}"
                            )

            if queued_task:
                args = queued_task.split(" ")
                if args[0] in tasks_to_clear:
                    queued_task = None
                    cur.execute(
                        """
                        UPDATE tasks
                        SET queued = %s
                        WHERE symbol = %s
                        """,
                        (queued_task, ship_symbol),
                    )
                    if DEBUG:
                        task = " ".join(args)
                        logger.debug(
                            f"Reset Controller: Cleared queued {task=} for {ship_symbol} {reason=}"
                        )


def _ship_cargo(ship_symbol, cur):
    ship = cur.execute(
        """
        SELECT cargo FROM "ships" 
        WHERE "symbol" = %s 
        """,
        (ship_symbol,),
    ).fetchone()
    return [tg["symbol"] for tg in ship[0]["inventory"]]
