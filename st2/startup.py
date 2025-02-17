import atexit
import multiprocessing as mp
import os

from dotenv import load_dotenv
from xdg import XDG_DATA_HOME

from st2.db import db_server_init, db_tables_init
from st2.logging import logger
from st2.request import Request, messenger


def game_server():
    # load environmental variables from st2/.env
    load_dotenv()
    # check that all required keys are present in the environmental variables
    for key in [
        "ST_ACCOUNT_TOKEN",
        "ST_AGENT_SYMBOL",
        "ST_RESET_WINDOW",
    ]:
        if not os.getenv(key):
            raise EnvironmentError(
                f"Missing environmental variable '{key}'. " "Did you populate st2/.env?"
            )

    # update the server reset window
    # previous windows can be set to access the historic database
    if os.environ["ST_RESET_WINDOW"] == "None":
        status = Request().get("status")
        last_reset = status["resetDate"]
        next_reset = status["serverResets"]["next"]
        session = f"{last_reset}_{next_reset[:10]}"
        os.environ["ST_RESET_WINDOW"] = session
        logger.info(
            f"SpaceTraders {status['version']} ({session}) {status['status'][13:]}!"
        )
    else:
        session = os.environ["ST_RESET_WINDOW"]
        logger.info(f"SpaceTraders ({session}) offline database loaded!")
    data_dir = os.path.join(XDG_DATA_HOME, "st2", session)
    os.environ["ST_DATA_DIR"] = data_dir

    # start the database (if needed)
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
