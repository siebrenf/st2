from spacepyrates.caching import cache
from spacepyrates.logging import logger
from spacepyrates.request import request


def chart(self, verbose=True):
    """Command a ship to chart the waypoint at its current location."""
    # if self._in_transit(verbose):
    #     return
    # if self._no_trait("UNCHARTED", verbose=verbose):
    #     return

    data = request.post(f'my/ships/{self["symbol"]}/chart', self["agent"])["data"]
    # clear from cache so it's updated upon use
    key = ("system_waypoints", self["nav"]["systemSymbol"], None)
    _ = cache.pop(key)

    if verbose:
        wp = self["nav"]["waypointSymbol"]
        traits = ", ".join(sorted(t["symbol"] for t in data["traits"]))
        logger.info(f"{self.name()} charted {wp}. Traits: {traits}")

    return data
