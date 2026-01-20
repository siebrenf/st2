from psycopg import connect

from st2.logging import logger

DEBUG = True


def queue_task(ship, task, pname=None, estimated_profit=None):
    query = """UPDATE tasks SET "queued" = %s"""
    params = [task]
    if pname:
        query += """, "pname" = %s"""
        params.append(pname)
    query += """ WHERE "symbol" = %s"""
    params.append(ship)
    with connect("dbname=st2 user=postgres") as conn, conn.cursor() as cur:
        cur.execute(query, params)
    if DEBUG:
        msg = f"Queueing {task=} to {ship}"
        if estimated_profit:
            msg += f" for {estimated_profit=:_}"
        logger.debug(msg)


def cancel_task(ship, reason=None, task=None):
    with connect("dbname=st2 user=postgres") as conn, conn.cursor() as cur:
        cur.execute(
            """
            UPDATE tasks
            SET "cancel" = %s
            WHERE "symbol" = %s
            """,
            (True, ship),
        )
    if DEBUG:
        msg = "Cancelled " + (f"{task=}" if task else "task") + f" for {ship}"
        if reason:
            msg += f" {reason=}"
        logger.debug(msg)


def dequeue_task(ship, reason=None, task=None):
    with connect("dbname=st2 user=postgres") as conn, conn.cursor() as cur:
        cur.execute(
            """
            UPDATE tasks
            SET "queued" = %s
            WHERE "symbol" = %s
            """,
            (None, ship),
        )
    if DEBUG:
        msg = "Dequeued " + (f"{task=}" if task else "task") + f" for {ship}"
        if reason:
            msg += f" {reason=}"
        logger.debug(msg)
