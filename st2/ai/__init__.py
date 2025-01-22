import asyncio
import threading
from time import sleep
from uuid import uuid1

from psycopg import connect

from st2.ai.probe import ai_probe_waypoint
from st2.ai.system import ai_seed_system
from st2.logging import logger


def taskmaster(*args, **kwargs):
    t = TaskMaster(*args, **kwargs)
    t.run()


DEBUG = False


class TaskMaster:

    def __init__(self, pname, qa_pairs):
        self.name = pname
        self.pid = uuid1()
        self.qa_pairs = qa_pairs
        self._tasks = {}
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_event_loop, daemon=False)
        self._thread.start()
        self._loaded = set()

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
        if (
            ship in self._tasks
            and self._tasks[ship].done()
            and self._tasks[ship].exception() is None
        ):
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
        with connect("dbname=st2 user=postgres") as conn:
            with conn.cursor() as cur:
                while True:
                    cur.execute(
                        """
                        SELECT *
                        FROM tasks
                        WHERE pname = %s
                        """,
                        (self.name,),
                    )
                    for (
                        ship_symbol,
                        agent_symbol,
                        current_task,
                        queued_task,
                        cancel_task,
                        pname,
                        pid,
                    ) in cur.fetchall():
                        commit = False
                        if pid != self.pid:
                            # uuid changed: a script restart occurred
                            if current_task is not None:
                                # continue the previous task
                                task = self.get_task(
                                    ship_symbol, agent_symbol, current_task
                                )
                                self.put(ship_symbol, task)
                                if DEBUG:
                                    logger.debug(
                                        f"Restarting {ship_symbol} with task '{current_task}'"
                                    )
                            pid = self.pid
                            cur.execute(
                                """
                                UPDATE tasks
                                SET pid = %s
                                WHERE symbol = %s
                                """,
                                (pid, ship_symbol),
                            )
                            commit = True

                        if self.done(ship_symbol):
                            ret = self.get(ship_symbol)
                            if ret:
                                print(ret)  # TODO: do we need the coroutine result?
                            current_task = None
                            cur.execute(
                                """
                                UPDATE tasks
                                SET current = %s
                                WHERE symbol = %s
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
                                SET current = %s,
                                    cancel = %s
                                WHERE symbol = %s
                                """,
                                (current_task, cancel_task, ship_symbol),
                            )
                            commit = True

                        if current_task is None and queued_task is not None:
                            current_task = queued_task
                            queued_task = None
                            task = self.get_task(
                                ship_symbol, agent_symbol, current_task
                            )
                            self.put(ship_symbol, task)
                            cur.execute(
                                """
                                UPDATE tasks
                                SET current = %s,
                                    queued = %s
                                WHERE symbol = %s
                                """,
                                (current_task, queued_task, ship_symbol),
                            )
                            commit = True

                        if commit:
                            conn.commit()

                    sleep(0.1)  # TODO: remove?

    def get_task(self, ship_symbol, agent_symbol, task):
        task = task.split(" ")
        match task[0]:
            case "test":
                coro = _test_coroutine(*task[1:])

            case "probe":
                # if "ai_probe_waypoint" not in self._loaded:
                #     self._loaded.add("ai_probe_waypoint")
                #     from st2.ai.probe import ai_probe_waypoint
                #     sleep(1)
                is_shipyard = task[1] == "shipyard"
                coro = ai_probe_waypoint(  # noqa: always loaded on time
                    ship_symbol=ship_symbol,
                    waypoint_symbol=task[2],
                    is_shipyard=is_shipyard,
                    qa_pairs=self.qa_pairs,
                    verbose=False,
                )

            case "seed":
                # if "ai_seed_system" not in self._loaded:
                #     self._loaded.add("ai_seed_system")
                #     from st2.ai.system import ai_seed_system
                #     sleep(1)
                pname = task[1]
                priority = None
                coro = ai_seed_system(  # noqa: always loaded on time
                    ship_symbol=ship_symbol,
                    pname=pname,
                    qa_pairs=self.qa_pairs,
                    priority=priority,
                    verbose=True,  # TODO: remove
                )

            case _:
                raise ValueError(f"Task not recognized: {ship_symbol=}, {task=}")
        return coro


async def _test_coroutine(name, seconds=1):
    print(f"{name} will sleep for {seconds} sec.")
    await asyncio.sleep(seconds)
    print(f"{name} is done after {seconds} seconds")
    return name, seconds
