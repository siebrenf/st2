from psycopg import connect
from psycopg.types.json import Jsonb

from st2 import time
from st2.logging import logger


def survey(self, verbose=True):
    self.orbit()

    data = self.request.post(f'my/ships/{self["symbol"]}/survey')["data"]
    self._update(data)
    with connect("dbname=st2 user=postgres") as conn, conn.cursor() as cur:
        for s in data["surveys"]:
            cur.execute(
                """
                INSERT INTO surveys
                ("signature", "symbol", "deposits", "expiration", "size")
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    s["signature"],
                    s["symbol"],
                    Jsonb(s["deposits"]),
                    time.read(s["expiration"]),
                    s["size"],
                ),
            )

    if verbose:
        for s in data["surveys"]:
            logger.info(
                f'{self.name()} surveyed {s["signature"]} ({s["size"][0]}): '
                f'{sorted(d["symbol"] for d in s["deposits"])}'
            )
    return data["surveys"]


# def catch_extract_destabilized_error(func):
#     @wraps(func)
#     def wrapper(*args, **kwargs):
#         try:
#             return func(*args, **kwargs)
#         except GameError as e:
#             code = int(re.search(r"'code': (\d{4}),", str(e)).group(1))
#             if code in {
#                 4253: "waypoint destabilized",
#             }:
#                 m = re.search(r"api.spacetraders.io/v2/my/ships/(.*)/extract", str(e))
#                 ship = m.group(1)
#                 m = re.search(
#                     r"Error data: {'waypointSymbol': '(.*)', 'modifiers': (.*)}", str(e)
#                 )
#                 waypoint = m.group(1)
#                 modifiers = m.group(2)
#                 error = f"modifiers: {modifiers}, error: {str(e)}"
#                 log_errors(ship, waypoint, "extract", error)
#
#                 raise ExtractDestabilizedError(e)
#             raise e  # other errors
#
#     return wrapper
#
#
# @catch_extract_destabilized_error
def extract(self, survey=None, verbose=True):
    self.orbit()

    if survey:
        if not isinstance(survey["expiration"], str):
            survey["expiration"] = time.write(survey["expiration"])
        ret = self.request.post(
            f'my/ships/{self["symbol"]}/extract/survey', data=survey
        )
        if "data" not in ret:
            # survey expired/exhausted
            if verbose:
                ex = "expired" if survey["expiration"] < time.write() else "exhausted"
                logger.info(f'Survey {survey["signature"]} has {ex}')
            return None
        data = ret["data"]
    else:
        data = self.request.post(f'my/ships/{self["symbol"]}/extract')["data"]
    self._update(data)

    with connect("dbname=st2 user=postgres") as conn, conn.cursor() as cur:
        # log data["modifiers"]
        for m in data["modifiers"]:
            cur.execute(
                """
                INSERT INTO modifiers
                ("symbol", "name", "description")
                VALUES (%s, %s, %s)
                ON CONFLICT ("symbol") DO NOTHING
                """,
                (
                    m["symbol"],
                    m["name"],
                    m["description"],
                ),
            )

        # log data["extraction"]
        survey_signature = None if not survey else survey["signature"]
        cargo_full = self["cargo"]["units"] == self["cargo"]["capacity"]
        mount = [
            m["symbol"]
            for m in self["mounts"]
            if m["symbol"].startswith("MOUNT_MINING_LASER_")
        ][0]
        cur.execute(
            """
            INSERT INTO extraction
            ("symbol", "units", "survey_signature", "cargo_full", "mount", 
            "frame", "frame_condition", "frame_integrity", 
            "reactor", "reactor_condition", "reactor_integrity", 
            "engine", "engine_condition", "engine_integrity")
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                data["extraction"]["yield"]["symbol"],
                data["extraction"]["yield"]["units"],
                survey_signature,
                cargo_full,
                mount,
                self["frame"]["symbol"],
                self["frame"]["condition"],
                self["frame"]["integrity"],
                self["reactor"]["symbol"],
                self["reactor"]["condition"],
                self["reactor"]["integrity"],
                self["engine"]["symbol"],
                self["engine"]["condition"],
                self["engine"]["integrity"],
            ),
        )

    if verbose:
        for event in data["events"]:
            component = event["component"].lower()
            condition = self[component]["condition"]
            logger.warning(f"{self.name()} {component} at {round(condition*100)}%")
    return data["extraction"]["yield"]


def siphon(self, verbose=True):
    self.orbit()

    data = self.request.post(f'my/ships/{self["symbol"]}/siphon')["data"]
    self._update(data)

    mount = [
        m["symbol"]
        for m in self["mounts"]
        if m["symbol"].startswith("MOUNT_GAS_SIPHON_")
    ][0]
    cargo_full = self["cargo"]["units"] == self["cargo"]["capacity"]
    with connect("dbname=st2 user=postgres") as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO extraction
                ("symbol", "units", "survey_signature", "cargo_full", "mount", 
                "frame", "frame_condition", "frame_integrity", 
                "reactor", "reactor_condition", "reactor_integrity", 
                "engine", "engine_condition", "engine_integrity")
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    data["siphon"]["yield"]["symbol"],
                    data["siphon"]["yield"]["units"],
                    None,
                    cargo_full,
                    mount,
                    self["frame"]["symbol"],
                    self["frame"]["condition"],
                    self["frame"]["integrity"],
                    self["reactor"]["symbol"],
                    self["reactor"]["condition"],
                    self["reactor"]["integrity"],
                    self["engine"]["symbol"],
                    self["engine"]["condition"],
                    self["engine"]["integrity"],
                ),
            )

    if verbose:
        for event in data["events"]:
            component = event["component"].lower()
            condition = self[component]["condition"]
            logger.warning(f"{self.name()} {component} at {round(condition*100)}%")
    return data["siphon"]["yield"]


# def scan(self, target, log=True):
#     options = ("systems", "waypoints", "ships")
#     if target not in options:
#         raise ValueError(f"scan {options=}")
#     self.orbit()
#
#     data = request.post(f'my/ships/{self["symbol"]}/scan/{target}', self["agent"])[
#         "data"
#     ]
#     self._update_cache(data, "cooldown")
#     if log:
#         log_cooldown(self, f"scan_{target}")
#     return data[target]
