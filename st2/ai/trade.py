from st2 import time
from st2.logging import logger
from st2.pathing.travel import travel
from st2.ship import Ship


@logger.catch  # catch errors in a separate thread
async def ai_trade_system(
    ship_symbol, good, units, buy_wp, sell_wp, qa_pairs, priority=1, verbose=False
):
    if verbose:
        logger.info(
            f"{ship_symbol} will trade {units} {good} between {buy_wp} and {sell_wp}"
        )

    ship = Ship(ship_symbol, qa_pairs, priority)
    # jettison unrelated cargo
    purchase_units = units
    for g, u in ship.cargo_yield():
        if g == good:
            purchase_units -= u
        else:
            ship.jettison(g, u, verbose)

    fp = 0
    pp = 0
    t0 = time.now()
    if purchase_units > 0:
        fp += await travel(ship, buy_wp, explore=True, verbose=verbose)
        pp = ship.buy(good, purchase_units, verbose)
    fp += await travel(ship, sell_wp, explore=True, verbose=verbose)
    sp = ship.sell(good, units, verbose)

    if verbose:
        travel_time = (time.now() - t0).seconds
        total_profit = sp - pp - fp
        return_of_interest = round(sp / (pp + fp), 2)
        logger.info(
            f"{ship.name()} traded {units} {good} for {total_profit:_} ({travel_time=}, {return_of_interest=})"
        )
