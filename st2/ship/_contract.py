from st2.logging import logger
from psycopog import connect
from psycopg.types.json import Jsonb


def contract(self, log=True):
    """Request a new contract. Ship must be present at a faction controlled waypoint"""
    # if self._in_transit(verbose):
    #     return
    self.dock()
    data = self.request.post(f'my/ships/{self["symbol"]}/negotiate/contract')["data"]["contract"]
    data["agent"] = self["agent"]
    cache.set(("contract", request.agent), data["id"])

    if log:
        log_contract(data)
    return data


def deliver(self, symbol, units, contract, verbose=True):
    # if self._no_cargo(symbol, units, verbose=verbose):
    #     return
    # if self._in_transit(verbose):
    #     return
    # contract = contract_get(contract)
    # if self._no_delivery(contract, verbose):
    #     return
    self.dock()

    payload = {"shipSymbol": self["symbol"], "tradeSymbol": symbol, "units": units}
    data = request.post(
        f'my/contracts/{contract["id"]}/deliver', self["agent"], payload
    )["data"]

    # update ship
    self._update_cache(data, "cargo")

    # update contract
    contract["terms"] = data["contract"]["terms"]
    contract["fulfilled"] = data["contract"]["fulfilled"]
    wp = self["nav"]["waypointSymbol"]
    contract.delivery_data[wp][symbol]["units"] -= units
    if verbose:
        logger.info(f"{self.name()} delivered {units} {symbol} at {wp}")


# def _no_delivery(self, contract, verbose=True):
#     contract = contract_get(contract)
#     destinations = [d["destinationSymbol"] for d in contract["terms"]["deliver"]]
#     stop = self["nav"]["waypointSymbol"] not in destinations
#     if stop and verbose:
#         logger.error("Nothing to deliver at this waypoint!")
#     return stop
