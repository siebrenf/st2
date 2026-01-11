def refuel(self, units=None, from_cargo=False):
    """Refuel your ship by buying fuel from the local market.
    1 unit of FUEL on the market adds 100 units fuel to the ship."""
    if self["fuel"]["current"] == self["fuel"]["capacity"]:
        return 0

    self.dock()

    payload = {"fromCargo": from_cargo}
    if units:
        payload["units"] = units
    data = self.request.post(f'my/ships/{self["symbol"]}/refuel', data=payload)["data"]
    self._update(data)

    price = data.get("transaction", {}).get("totalPrice", 0)
    return price
