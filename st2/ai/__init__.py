import asyncio
import threading
from time import sleep

import psycopg


def taskmaster(name, uuid):
    t = TaskMaster(name, uuid)
    t.run()


class TaskMaster:

    def __init__(self, name, uuid):
        self.name = name
        self.uuid = uuid
        self._tasks = {}
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_event_loop, daemon=False)
        self._thread.start()

    def _run_event_loop(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def cancel(self, ship):
        """Cancel a task"""
        if ship not in self._tasks:
            return
        future = self._tasks.pop(ship)  # allow future to be garbage collected
        self._loop.call_soon_threadsafe(future.cancel)
        timeout = 1  # sec
        while not future.done():
            sleep(0.001)  # allow future to cancel

            timeout -= 0.001
            if timeout <= 0:
                del future
                break

    def done(self, ship):
        if ship in self._tasks and self._tasks[ship].done():
            return True
        return False

    def get(self, ship):
        """Retrieve a task"""
        future = self._tasks.pop(ship)
        return future.result()

    def put(self, ship, coroutine):
        """Submit a task to be awaited"""
        future = asyncio.run_coroutine_threadsafe(coroutine, self._loop)
        self._tasks[ship] = future

    def terminate(self):
        """Cancel all tasks & terminate the loop & thread. Irreversibly."""
        for future in self._tasks.values():
            self._loop.call_soon_threadsafe(future.cancel)
        while not all(future.done() for future in self._tasks.values()):
            sleep(0.001)  # allow all futures to cancel
        self._tasks = {}  # allow all futures to be garbage collected
        if self._loop.is_closed():
            return
        self._loop.call_soon_threadsafe(self._loop.stop)
        while self._loop.is_running():
            sleep(0.1)  # allow the loop to stop
        self._loop.close()
        self._thread.join()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.terminate()

    def __del__(self):
        self.terminate()

    def run(self):
        with psycopg.connect(f"dbname=st2 user=postgres") as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT *
                FROM tasks
                WHERE pname = %s
                """,
                (self.name,),
            )
            for task in cur.fetchall():
                commit = False
                (
                    ship_symbol,
                    agent_symbol,
                    current_task,
                    queued_task,
                    cancel_task,
                    pname,
                    pid,
                ) = task
                if pid != self.uuid:
                    # uuid changed: a script restart occurred
                    if current_task is not None:
                        # continue the previous task
                        task = self.get_task(ship_symbol, current_task)
                        self.put(ship_symbol, task)
                    pid = self.uuid
                    cur.execute(
                        """
                        UPDATE tasks
                        SET (
                            pid = %s
                        )
                        WHERE ship = %s
                        """,
                        (pid, ship_symbol),
                    )
                    commit = True

                if self.done(ship_symbol):
                    ret = self.get(ship_symbol)
                    print(ret)  # TODO: do we need the coroutine result?
                    current_task = None
                    cur.execute(
                        """
                        UPDATE tasks
                        SET (
                            current = %s
                        )
                        WHERE ship = %s
                        """,
                        (current_task, ship_symbol),
                    )
                    commit = True

                if cancel_task:
                    self.cancel(ship_symbol)
                    current_task = None
                    cancel_task = False
                    cur.execute(
                        """
                        UPDATE tasks
                        SET (
                            current = %s,
                            cancel = %s,
                        )
                        WHERE ship = %s
                        """,
                        (current_task, cancel_task, ship_symbol),
                    )
                    commit = True

                if current_task is None and queued_task is not None:
                    current_task = queued_task
                    queued_task = None
                    task = self.get_task(ship_symbol, current_task)
                    self.put(ship_symbol, task)
                    cur.execute(
                        """
                        UPDATE tasks
                        SET (
                            current = %s,
                            queued = %s,
                        )
                        WHERE ship = %s
                        """,
                        (current_task, queued_task, ship_symbol),
                    )
                    commit = True

                if commit:
                    conn.commit()

    @staticmethod
    def get_task(ship_symbol, task):
        task = task.split(" ")
        if task[0] == "probe":
            coro = ai_probe_waypoint(
                ship=ship_symbol,
                waypoint=task[1],
            )
        else:
            raise ValueError(f"task not recognized: {ship_symbol} {task}")
        return coro
