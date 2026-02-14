import asyncio
import threading
from time import sleep
from uuid import uuid1

from psycopg import connect

from st2.ai.advisor_controller import ai_advisor_controller
from st2.ai.construction_controller import ai_construction_controller
from st2.ai.contract_controller import ai_contract_controller
from st2.ai.deliver import ai_deliver_system
from st2.ai.extract import ai_extract_start_system
from st2.ai.probe import ai_probe_purchase, ai_probe_waypoint
from st2.ai.probe_controller import ai_probe_controller
from st2.ai.scout import ai_scout_waypoint
from st2.ai.siphon import ai_siphon_start_system
from st2.ai.start_system_controller import ai_start_system_controller
from st2.ai.supply import ai_supply_system
from st2.ai.trade import ai_trade_system
from st2.ai.trade_controller import ai_trade_controller
from st2.logging import logger


def taskmaster(*args, **kwargs):
    t = TaskMaster(*args, **kwargs)
    t.run()


DEBUG = False


class TaskMaster:

    def __init__(self, pname, qa_pairs):
        self.name = pname  # only tasks with matching pname will be handled
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
        with connect("dbname=st2 user=postgres") as conn, conn.cursor() as cur:
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
                        # uuid changed: a script (re)start occurred
                        if current_task is not None:
                            # continue the previous task
                            task = self.get_task(
                                ship_symbol, agent_symbol, current_task
                            )
                            self.put(ship_symbol, task)
                            if DEBUG:
                                logger.debug(
                                    f"Starting {ship_symbol} with task '{current_task}'"
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
                        if DEBUG:
                            logger.debug(f"{ship_symbol} stopped task '{current_task}'")
                        ret = self.get(ship_symbol)
                        if ret == "self destruct":
                            cur.execute(
                                """
                                DELETE FROM tasks
                                WHERE symbol = %s
                                """,
                                (ship_symbol,),
                            )
                        elif ret:
                            logger.debug(
                                f"unknown task output for {ship_symbol}: {ret}"
                            )
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
                        task = self.get_task(ship_symbol, agent_symbol, current_task)
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
            case "advisor_controller":
                coro = ai_advisor_controller(
                    qa_pairs=self.qa_pairs,
                    verbose=True,  # TODO: remove
                )

            case "construction_controller":
                coro = ai_construction_controller(
                    system_symbol=task[1],
                    agent_symbol=agent_symbol,
                    qa_pairs=self.qa_pairs,
                )

            case "contract_controller":
                coro = ai_contract_controller(
                    agent_symbol=agent_symbol,
                    qa_pairs=self.qa_pairs,
                    verbose=True,  # TODO: remove
                )

            case "deliver":
                coro = ai_deliver_system(
                    ship_symbol=ship_symbol,
                    good=task[1],
                    units=int(task[2]),
                    purchase_wp=task[3],
                    deliver_wp=task[4],
                    qa_pairs=self.qa_pairs,
                    verbose=True,  # TODO: remove
                )

            case "extract":
                coro = ai_extract_start_system(
                    ship_symbol=ship_symbol,
                    trait=task[1],
                    extract_wp=task[2],
                    sell_wp=task[3],
                    whitelist=task[4],
                    qa_pairs=self.qa_pairs,
                    verbose=True,  # TODO: remove
                )

            case "probe":
                coro = ai_probe_waypoint(
                    ship_symbol=ship_symbol,
                    waypoint_symbol=task[2],
                    is_shipyard=task[1] == "shipyard",
                    qa_pairs=self.qa_pairs,
                )

            case "probe_controller":
                coro = ai_probe_controller(
                    system_symbol=task[1],
                    agent_symbol=agent_symbol,
                    qa_pairs=self.qa_pairs,
                    verbose=True,  # TODO: remove
                )

            case "probe_purchase":
                coro = ai_probe_purchase(
                    ship_symbol=ship_symbol,
                    waypoint_symbol=task[1],
                    qa_pairs=self.qa_pairs,
                    verbose=True,  # TODO: remove
                )

            case "scout":
                coro = ai_scout_waypoint(
                    ship_symbol=ship_symbol,
                    waypoint_symbol=task[1],
                    qa_pairs=self.qa_pairs,
                )

            case "siphon":
                coro = ai_siphon_start_system(
                    ship_symbol=ship_symbol,
                    siphon_wp=task[2],
                    sell_wp=task[3],
                    qa_pairs=self.qa_pairs,
                    verbose=True,  # TODO: remove
                )

            # too many API requests!
            # case "spymaster_controller":
            #     coro = ai_spymaster_controller(
            #         agent_symbol=agent_symbol,
            #         qa_pairs=self.qa_pairs,
            #         verbose=True,  # TODO: remove
            #     )

            case "start_system_controller":
                coro = ai_start_system_controller(
                    system_symbol=task[1],
                    agent_symbol=agent_symbol,
                    qa_pairs=self.qa_pairs,
                    verbose=True,  # TODO: remove
                )

            case "supply":
                coro = ai_supply_system(
                    ship_symbol=ship_symbol,
                    good=task[1],
                    units=int(task[2]),
                    purchase_wp=task[3],
                    supply_wp=task[4],
                    qa_pairs=self.qa_pairs,
                    verbose=True,  # TODO: remove
                )

            case "survey":
                coro = _test_coroutine(ship_symbol, 1e999)  # TODO

            case "test":
                coro = _test_coroutine(*task[1:])

            case "trade":
                coro = ai_trade_system(
                    ship_symbol=ship_symbol,
                    good=task[1],
                    units=int(task[2]),
                    purchase_wp=task[3],
                    sell_wp=task[4],
                    qa_pairs=self.qa_pairs,
                    verbose=True,  # TODO: remove
                )

            case "trade_controller":
                coro = ai_trade_controller(
                    system_symbol=task[1],
                    agent_symbol=agent_symbol,
                    qa_pairs=self.qa_pairs,
                )

            case _:
                task = " ".join(task)
                raise ValueError(f"Task not recognized: {ship_symbol=}, {task=}")
        return coro  # noqa: always loaded on time


@logger.catch  # catch errors in a separate thread
async def _test_coroutine(name, seconds=1):
    seconds = float(seconds)
    logger.debug(f"{name} will sleep for {seconds} sec.")
    await asyncio.sleep(seconds)
    logger.debug(f"{name} is done after {seconds} seconds")
    return name, seconds
