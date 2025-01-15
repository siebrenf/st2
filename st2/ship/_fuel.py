from spacepyrates.caching import cache
from spacepyrates.request import request


def refuel(self, units=None, from_cargo=False):
    """Refuel your ship by buying fuel from the local market.
    1 units of FUEL on the market adds 100 units fuel to the ship."""
    # if self._in_transit(verbose):
    #     return
    # if self._no_trait("MARKETPLACE", verbose=verbose):
    #     return
    # if self._no_good("FUEL", verbose=verbose):
    #     return
    # if self["fuel"]["current"] == self["fuel"]["capacity"]:
    #     return
    self.dock()

    payload = {"fromCargo": from_cargo}
    if units:
        payload["units"] = units
    data = request.post(f'my/ships/{self["symbol"]}/refuel', self["agent"], payload)[
        "data"
    ]
    self._update_cache(data, "fuel")
    cache.set(("credits", request.agent), data["agent"]["credits"])
    return data["transaction"]["totalPrice"]
