def refuel(self, units=None, from_cargo=False):
    """Refuel your ship by buying fuel from the local market.
    1 unit of FUEL on the market adds 100 units fuel to the ship."""
    self.dock()

    payload = {"fromCargo": from_cargo}
    if units:
        payload["units"] = units
    data = self.request.post(
        f'my/ships/{self["symbol"]}/refuel', self["agent"], data=payload
    )["data"]
    self._update(data, ["fuel"])

    # TODO: log data["agent"]
    # TODO: log data["transaction"]
