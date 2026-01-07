from st2.logging import logger
from st2.pathing.travel import travel
from st2.ship import Ship


@logger.catch  # catch errors in a separate thread
async def ai_scout_waypoint(
    ship_symbol, waypoint_symbol, qa_pairs, priority=1, verbose=False
):
    if verbose:
        logger.info(f"{ship_symbol} will scout {waypoint_symbol}")
    ship = Ship(ship_symbol, qa_pairs, priority)
    await travel(ship, waypoint_symbol, explore=True, verbose=False)
