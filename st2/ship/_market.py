from spacepyrates import time
from spacepyrates.caching import cache
from spacepyrates.data.gathering import log_trade
from spacepyrates.logging import logger
from spacepyrates.request import request


def market(self, log=True):
    """get all marketplace details"""
    # if self._in_transit(verbose):
    #     return
    # if self._no_trait("MARKETPLACE", verbose=verbose):
    #     return

    data = request.get(
        f'systems/{self["nav"]["systemSymbol"]}/waypoints/{self["nav"]["waypointSymbol"]}/market',
        self["agent"],
    )["data"]
    # TODO: test & remove when the WSL2 time desync is fixed
    n = 0
    while "tradeGoods" not in data:
        time.sleep(1)
        data = request.get(
            f'systems/{self["nav"]["systemSymbol"]}/waypoints/{self["nav"]["waypointSymbol"]}/market',
            self["agent"],
        )["data"]
        n += 1
        logger.debug(f"ship.market() failed ({n} sec)")
    data["time"] = time.write()

    key = ("market", self["nav"]["waypointSymbol"], None)
    cache.set(key=key, value=data)  # live prices, for get_price()
    if log:
        log_trade(data)
    return data
