import atexit
import multiprocessing as mp
import os

from xdg import XDG_DATA_HOME

from st2 import time
from st2.caching import cache
from st2.db import db_server_init, db_tables_init
from st2.request import Request, messenger


def game_server():
    """check if and when the game server resets"""
    if cache.get("next_reset"):
        return

    # server reset status unknown/uncertain
    status = Request().get("status")
    last_reset = status["resetDate"]
    next_reset = status["serverResets"]["next"]
    next_reset = next_reset.replace("2024", "2025")  # TODO: remove
    if last_reset == cache.get("last_reset"):
        return

    # server reset occurred
    cache.clear()
    cache.set("last_reset", last_reset)
    cache.set("next_reset", next_reset, expire=time.remaining(next_reset))

    # server reset specific variables
    data_dir = os.path.join(XDG_DATA_HOME, "st2", f"{last_reset}_{next_reset[:10]}")
    log_dir = os.path.join(data_dir, "logs")
    os.makedirs(log_dir, exist_ok=True)
    cache.set("data_dir", data_dir)
    cache.set("log_dir", log_dir)


# class Singleton(type):
#     _instances = {}
#
#     def __call__(cls, *args, **kwargs):
#         if cls not in cls._instances:
#             cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
#         # else:
#         #     cls._instances[cls].__init__(*args, **kwargs)
#         return cls._instances[cls]
#
#
# class GlobalVariables(metaclass=Singleton):
#     def __int__(self):
#         self.data_dir = os.path.join(
#             XDG_DATA_HOME,
#             "st2",
#             f'{cache.get("last_reset")}_{cache.get("next_reset").split("T")[0]}',
#         )
#         self.log_dir = os.path.join(self.data_dir, "logs")
#         os.makedirs(self.log_dir, exist_ok=True)
#         cache.set("data_dir", self.data_dir)
#         cache.set("log_dir", self.log_dir)


def db_server():
    db_server_init()
    db_tables_init()


def api_server():
    manager = mp.Manager()
    qa_pairs = (
        (manager.Queue(), manager.dict()),  # high prio (e.g. high quality trades)
        (manager.Queue(), manager.dict()),  # mid prio (e.g. normal trades & exploring)
        (manager.Queue(), manager.dict()),  # low prio (e.g. probing markets)
        (manager.Queue(), manager.dict()),  # no prio (e.g. building the sector map)
    )
    api_handler = mp.Process(
        target=messenger,
        kwargs={
            "qa_pairs": qa_pairs,
        },
    )
    api_handler.start()

    def stop_api_server():
        # This prevents the BrokenPipeError
        #  because the script is garbage collected while running infinitely
        api_handler.terminate()
        api_handler.join()

    # stop the api server when we stop
    atexit.register(stop_api_server)

    return manager, api_handler, qa_pairs


# game_server()
# sql_server()
# manager, api_handler, qa_pairs = api_server()
