from st2.logging import logger


def survey(self, verbose=True):
    self.orbit()

    data = self.request.post(f'my/ships/{self["symbol"]}/survey')["data"]
    self._update(data, ["cooldown"])
    # TODO: log data["surveys"]
    # TODO: create table/module surveys

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
def extract(self, verbose=True):
    self.orbit()

    data = self.request.post(f'my/ships/{self["symbol"]}/extract')["data"]
    # if survey is None:
    #     data = self.request.post(f'my/ships/{self["symbol"]}/extract')["data"]
    #     action = "extract"
    # else:
    #     ret = self.request.post(f'my/ships/{self["symbol"]}/extract/survey', data=survey)
    #     if "data" not in ret:
    #         # remove outdated survey from the cache
    #         surveys.remove(survey)
    #         if verbose:
    #             ex = "expired" if survey["expiration"] < time.write() else "exhausted"
    #             logger.info(f'Survey {survey["signature"]} has {ex}')
    #         return None
    #     data = ret["data"]
    #     action = "extract_survey"
    self._update(data, ["cargo", "cooldown"])

    # TODO: ability to use surveys
    # TODO: log data["extraction"] + tool and use of survey
    # TODO: log data["events"]
    # TODO: create table extracts
    # TODO: create table events

    if verbose:
        for event in data["events"]:
            component = event["component"].lower()
            condition = self[component]["condition"]
            logger.warning(f"{self.name()} {component} at {round(condition*100)}%")
    return data["extraction"]["yield"]


def siphon(self, verbose=True):
    self.orbit()

    data = self.request.post(f'my/ships/{self["symbol"]}/siphon')["data"]
    self._update(data, ["cargo", "cooldown"])

    # TODO: log data["siphon"] + tool
    # TODO: log data["events"]

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
