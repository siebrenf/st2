import re
from functools import wraps

from spacepyrates import surveys, time
from spacepyrates.caching import cache
from spacepyrates.data.gathering import (
    log_cooldown,
    log_errors,
    log_extract,
    log_survey,
)
from spacepyrates.exceptions import ExtractDestabilizedError, GameError
from spacepyrates.logging import logger
from spacepyrates.request import request

# def mount(self):
#     """update mount data with an API call"""
#     self.refresh()
#     return self["mounts"]


def mount_install(self, mount, verbose=True):
    # if self._no_cargo(mount, verbose=verbose):
    #     return
    # if self._in_transit(verbose):
    #     return
    # if self._no_trait("SHIPYARD", verbose=verbose):
    #     return
    self.dock()

    payload = {"symbol": mount}
    data = request.post(
        f'my/ships/{self["symbol"]}/mounts/install', self["agent"], payload
    )["data"]
    self["mounts"] = data["mounts"]
    self["cargo"] = data["cargo"]
    cache.set(("credits", request.agent), data["agent"]["credits"])
    if verbose:
        logger.info(f"Installed {mount} on {self.name()}")


def mount_remove(self, mount, verbose=True):
    # if self._no_capacity(1, verbose):
    #     return
    # if self._in_transit(verbose):
    #     return
    # if self._no_trait("SHIPYARD", verbose=verbose):
    #     return
    self.dock()

    payload = {"symbol": mount}
    data = request.post(
        f'my/ships/{self["symbol"]}/mounts/remove', self["agent"], payload
    )["data"]
    self["mounts"] = data["mounts"]
    self["cargo"] = data["cargo"]
    cache.set(("credits", request.agent), data["agent"]["credits"])
    if verbose:
        logger.info(f"Uninstalled {mount} on {self.name()}")


def survey(self, verbose=True, log=True):
    # if self._in_transit(verbose):
    #     return
    # if self._no_mount("MOUNT_SURVEYOR", verbose):
    #     return
    # if self._on_cooldown(verbose):
    #     return
    self.orbit()

    data = request.post(f'my/ships/{self["symbol"]}/survey', self["agent"])["data"]
    self["cooldown"] = data["cooldown"]
    # cache the new survey(s)
    surveys.add(data["surveys"])

    if verbose:
        for s in data["surveys"]:
            logger.info(
                f'{self.name()} surveyed {s["signature"]} ({s["size"][0]}): '
                f'{sorted(d["symbol"] for d in s["deposits"])}'
            )
    if log:
        log_survey(self, data)
        log_cooldown(self, "survey")
    return data["surveys"]


# def _no_mount(self, mount, verbose=True):
#     mounts = [m["symbol"] for m in self["mounts"]]
#     if not any(m.startswith(mount) for m in mounts):
#         if verbose:
#             logger.error(f"No {mount} installed on {self.name()}")
#         return True
#     return False


def catch_extract_destabilized_error(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except GameError as e:
            code = int(re.search(r"'code': (\d{4}),", str(e)).group(1))
            if code in {
                4253: "waypoint destabilized",
            }:
                m = re.search(r"api.spacetraders.io/v2/my/ships/(.*)/extract", str(e))
                ship = m.group(1)
                m = re.search(
                    r"Error data: {'waypointSymbol': '(.*)', 'modifiers': (.*)}", str(e)
                )
                waypoint = m.group(1)
                modifiers = m.group(2)
                error = f"modifiers: {modifiers}, error: {str(e)}"
                log_errors(ship, waypoint, "extract", error)

                raise ExtractDestabilizedError(e)
            raise e  # other errors

    return wrapper


@catch_extract_destabilized_error
def extract(self, survey=None, verbose=True, log=True):
    # if self._in_transit(verbose):
    #     return None, None
    # if self._no_mount("MOUNT_MINING_LASER", verbose):
    #     return None, None
    # if self._on_cooldown(verbose):
    #     return None, None
    self.orbit()

    if survey is None:
        data = request.post(f'my/ships/{self["symbol"]}/extract', self["agent"])["data"]
        action = "extract"
    else:
        ret = request.post(
            f'my/ships/{self["symbol"]}/extract/survey', self["agent"], survey
        )
        if "data" not in ret:
            # remove outdated survey from the cache
            surveys.remove(survey)
            if verbose:
                ex = "expired" if survey["expiration"] < time.write() else "exhausted"
                logger.info(f'Survey {survey["signature"]} has {ex}')
            return None
        data = ret["data"]
        action = "extract_survey"
    self._update_cache(data, ["cargo", "cooldown"])

    if verbose:
        for event in data["events"]:
            component = event["component"].lower()
            condition = self[component]["condition"]
            logger.warning(f"{self.name()} {component} at {round(condition*100)}%")

    if log:
        log_extract(self, data, "extraction", survey)
        # log_event(self, "extract", data["events"])
        log_cooldown(self, action)
    return data["extraction"]["yield"]


def siphon(self, verbose=True, log=True):
    # if self._in_transit(verbose):
    #     return
    # if self._no_mount("MOUNT_GAS_SIPHON", verbose):
    #     return
    # if self._on_cooldown(verbose):
    #     return
    self.orbit()

    data = request.post(f'my/ships/{self["symbol"]}/siphon', self["agent"])["data"]
    self._update_cache(data, ["cargo", "cooldown"])

    if verbose:
        for event in data["events"]:
            component = event["component"].lower()
            condition = self[component]["condition"]
            logger.warning(f"{self.name()} {component} at {round(condition*100)}%")

    if log:
        log_extract(self, data, "siphon")
        # log_event(self, "extract", data["events"])
        log_cooldown(self, "siphon")
    return data["siphon"]["yield"]


def scan(self, target, log=True):
    options = ("systems", "waypoints", "ships")
    if target not in options:
        raise ValueError(f"scan {options=}")
    #     if verbose:
    #         logger.error(f"Scan action not in {options}")
    #     return
    # if self._in_transit(verbose):
    #     return
    # if self._no_mount("MOUNT_SENSOR_ARRAY", verbose):
    #     return
    # if self._on_cooldown(verbose):
    #     return
    self.orbit()

    data = request.post(f'my/ships/{self["symbol"]}/scan/{target}', self["agent"])[
        "data"
    ]
    self._update_cache(data, "cooldown")
    if log:
        log_cooldown(self, f"scan_{target}")
    return data[target]


# def action_cooldown(self, action):
#     """return the cooldown induced by the action"""
#     cd = ac(self, action)
#     return cd
