from psycopg import connect
from psycopg.rows import dict_row

from st2.logging import logger

DEBUG = True


def ai_reset_controller():
    """
    Execute this function on script restart **before** starting the taskmasters,
    in order to clear all time-sensitive tasks.
    """
    tasks_to_clear = ["trade", "supply", "deliver"]
    reason = "script reset"
    with connect(
        "dbname=st2 user=postgres", row_factory=dict_row
    ) as conn, conn.cursor() as cur:
        for (
            ship_symbol,
            agent_symbol,
            current_task,
            queued_task,
            cancel_task,
            pname,
            pid,
        ) in cur.execute("""SELECT * FROM tasks""").fetchall():
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
                                f"Cleared current {task=} for {ship_symbol} {reason=}"
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
                            f"Cleared queued {task=} for {ship_symbol} {reason=}"
                        )


def _ship_cargo(ship_symbol, cur):
    ship = cur.execute(
        """
        SELECT cargo FROM "ships" 
        WHERE "symbol" = %s 
        """,
        (ship_symbol,),
    ).fetchone()
    return [tg["symbol"] for tg in ship["cargo"]["inventory"]]
