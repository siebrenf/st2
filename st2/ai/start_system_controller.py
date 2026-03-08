from asyncio import sleep

from st2.agent import get_agent, get_agent_public
from st2.ai.utils import get_tasks, queue_task
from st2.db.static import SUPPLY_CHAIN
from st2.logging import logger
from st2.mining import TRAIT2EXTRACT
from st2.request import RequestMp
from st2.ship import Ship, buy_ship
from st2.system import System

DEBUG = True


@logger.catch  # catch errors in a separate thread
async def ai_start_system_controller(
    system_symbol,
    agent_symbol,
    qa_pairs,
    priority=2,
    interval=60,
    verbose=False,
):
    """
    Assign drones to gather the start system's basic needs

    This controller self-destructs after completing its task.
    """
    token = get_agent(agent_symbol)["token"]
    request = RequestMp(qa_pairs, priority, token)
    system = System(system_symbol, request, priority)

    # wait until all shipyards and marketplaces are charted & scouted
    while len(system.uncharted_markets()) + len(system.unscouted_markets()) != 0:
        await sleep(interval)
        system.refresh(refresh_graph=False)

    raw2products = get_raw_and_product_goods(system)
    if DEBUG:
        products = set()
        for v in raw2products.values():
            products.update(v)
        logger.debug(
            f"Start System Controller {system_symbol}: local commodities: {sorted(products)}"
        )

    trait2raw_goods = {}
    seen = set()
    for deposit, extracts in TRAIT2EXTRACT.items():
        goods = set(extracts) & set(raw2products)
        # minimize the number of traits needed
        if goods - seen:
            if deposit in ["PRECIOUS_METAL_DEPOSITS", "RARE_METAL_DEPOSITS"]:
                goods -= (seen | {"QUARTZ_SAND", "SILICON_CRYSTALS"})
            trait2raw_goods[deposit] = goods
            seen.update(goods)
    if DEBUG:
        logger.debug(f"Start System Controller {system_symbol}: {trait2raw_goods=}")

    # for each trait, find the best extract_wp and extract_sell_wp
    trait2waypoints = {}
    traits_blacklisted = set(TRAIT2EXTRACT) - set(trait2raw_goods)
    for trait, goods in trait2raw_goods.items():
        sell_wps = None
        for good in goods:
            if sell_wps is None:
                sell_wps = set(system.markets_with(good, "buys"))
            else:
                sell_wps = sell_wps & set(system.markets_with(good, "buys"))

        best = None, None, float("inf")
        for extract_wp, md in system.waypoints_with(
            traits=trait, type=["ASTEROID", "ENGINEERED_ASTEROID"]
        ).items():
            if set(md["traits"]) & traits_blacklisted:  # noqa
                continue
            for sell_wp in sell_wps:
                dist = system.graph[extract_wp][sell_wp]["distance"]  # noqa
                if dist < best[2]:  # noqa
                    best = extract_wp, sell_wp, dist
        extract_wp, sell_wp, dist = best
        if extract_wp:
            trait2waypoints[trait] = extract_wp, sell_wp

    # select a market that exchanges siphoned goods, around a gas giant
    best = None, None, float("inf")
    for siphon_wp in system.waypoints_with(type="GAS_GIANT"):
        for sell_wp in system.markets_with("HYDROCARBON", "EXCHANGE"):
            dist = system.graph[siphon_wp][sell_wp]["distance"]  # noqa
            if dist < best[2]:
                best = siphon_wp, sell_wp, dist
    siphon_wp, sell_wp, dist = best
    if siphon_wp:
        trait2waypoints["GAS_GIANT"] = siphon_wp, sell_wp
    if DEBUG:
        logger.debug(f"Start System Controller {system_symbol}: {trait2waypoints=}")

    # remaining drones per waypoint type/trait
    remaining = {"siphon": {"GAS_GIANT": 2}, "extract": {}, "survey": {}}
    for trait in sorted(trait2waypoints):
        if trait == "GAS_GIANT":
            continue
        remaining["extract"][trait] = 4
        remaining["survey"][trait] = 1
    if DEBUG:
        logger.debug(
            f"Start System Controller {system_symbol}: drones_required={remaining}"
        )
    available = []
    for task in get_tasks(
        system_symbol=system.symbol,
        agent_symbol=agent_symbol,
        pname="drones",
    ):
        for key in ["current", "queued"]:
            if task[key]:
                action, trait = str(task[key]).split(" ")[0:2]
                remaining[action][trait] -= 1
                break
        else:
            available.append(task["symbol"])
    # assign available drones (can happen after an error)
    for ship_symbol in available:
        ship = Ship(ship_symbol, request)
        ship_wp = ship["nav"]["waypointSymbol"]
        if ship["mounts"][0]["symbol"].startswith("MOUNT_GAS_SIPHON_I"):
            # drone is a siphoner
            action_wp, sell_wp, trait = assign_drone(
                ship_wp, remaining, "siphon", trait2waypoints, system
            )
            task = f"siphon GAS_GIANT {action_wp} {sell_wp}"
            queue_task(ship["symbol"], task, pname="drones")
        elif ship["mounts"][0]["symbol"].startswith("MOUNT_MINING_LASER_I"):
            # drone is an extractor
            action_wp, sell_wp, trait = assign_drone(
                ship_wp, remaining, "extract", trait2waypoints, system
            )
            whitelist = get_whitelist(system, action_wp, trait2raw_goods)
            task = f"extract {trait} {action_wp} {sell_wp} {whitelist}"
            queue_task(ship["symbol"], task, pname="drones")
        elif ship["mounts"][0]["symbol"].startswith("MOUNT_SURVEYOR_I"):
            # drone is a surveyor
            action_wp, sell_wp, trait = assign_drone(
                ship_wp, remaining, "survey", trait2waypoints, system
            )
            whitelist = get_whitelist(system, action_wp, trait2raw_goods)
            task = f"survey {trait} {action_wp} {sell_wp} {whitelist}"
            queue_task(ship["symbol"], task, pname="drones")
        else:
            raise AssertionError("Unreachable code reached")
    if DEBUG:
        logger.debug(f"Start System Controller {system_symbol}: drones_{remaining=}")

    # purchase orders:
    #  - all siphoners
    #  - 1 extractor > 1 surveyor > remaining extractors > remaining surveyor s
    order = []
    for n in range(remaining["siphon"]["GAS_GIANT"]):
        order.append(("siphon", "GAS_GIANT"))
    for trait in remaining["extract"]:
        n = remaining["extract"][trait]
        if n:
            order.append(("extract", trait))
        m = remaining["survey"][trait]
        if m:
            order.append(("survey", trait))
        for _ in range(n - 1):
            order.append(("extract", trait))
        for _ in range(m - 1):
            order.append(("survey", trait))

    probed_shipyards = set()
    for action, trait in order:
        action_wp, sell_wp = trait2waypoints[trait]
        if action == "siphon":
            ship_type = "SHIP_SIPHON_DRONE"
            task = f"siphon GAS_GIANT {action_wp} {sell_wp}"
        elif action == "extract":
            ship_type = "SHIP_MINING_DRONE"
            whitelist = get_whitelist(system, action_wp, trait2raw_goods)
            task = f"extract {trait} {action_wp} {sell_wp} {whitelist}"
        elif action == "survey":
            ship_type = "SHIP_SURVEYOR"
            whitelist = get_whitelist(system, action_wp, trait2raw_goods)
            task = f"survey {trait} {action_wp} {sell_wp} {whitelist}"
        else:
            raise ValueError
        if DEBUG:
            logger.debug(f"Start System Controller {system_symbol}: next {task=}")

        while True:
            await sleep(interval)

            best = None, {}
            for shipyard_symbol, md in system.shipyards_with(ship_type).items():
                if md["purchasePrice"] < best[1].get("purchasePrice", float("inf")):
                    best = shipyard_symbol, md
            shipyard_symbol, md = best

            if shipyard_symbol not in probed_shipyards:
                tasks = get_tasks(
                    current=f"probe shipyard {shipyard_symbol}",
                    agent_symbol=agent_symbol,
                )
                if len(tasks) == 0:
                    continue

                t = Ship(tasks[0]["symbol"], request).nav_remaining()
                if t:
                    await sleep(t)
                probed_shipyards.add(shipyard_symbol)
                if t:
                    continue  # check the prices again

            cost = md["purchasePrice"]
            credits = get_agent_public(agent_symbol)["credits"]  # noqa
            supply = md["supply"]
            if credits < 1_000_000 + cost:
                if DEBUG:
                    logger.debug(
                        f"Start System Controller {system_symbol}: insufficient funds"
                    )
                continue
            if supply == "SCARCE":
                if DEBUG:
                    logger.debug(
                        f"Start System Controller {system_symbol}: insufficient supply"
                    )
                continue
            break  # all good!

        ship = buy_ship(ship_type, shipyard_symbol, request, agent_symbol, verbose)
        queue_task(ship, task, pname="drones")
        remaining[action][trait] -= 1
        if remaining[action][trait] == 0:
            del remaining[action][trait]
            if len(remaining[action]) == 0:
                del remaining[action]
        if DEBUG:
            logger.debug(
                f"Start System Controller {system_symbol}: drones_{remaining=}"
            )

    if DEBUG:
        logger.debug(f"Start System Controller {system_symbol}: task completed")
    return "self destruct"


def get_raw_and_product_goods(system):
    """
    Identify which tradeGoods are desired and can be produced in-system.
    Returns a dict of raw goods and their final products
    """
    # categorize each tradeGood
    raw_goods = []  # good that can be extracted/siphoned
    consumer_goods = []  # goods that are consumed by waypoints
    player_goods = []  # goods that are consumed by players
    for good_exp in SUPPLY_CHAIN.keys():
        if SUPPLY_CHAIN[good_exp] in [["EXPLOSIVES"], ["MACHINERY"]]:
            raw_goods.append(good_exp)
            continue
        if SUPPLY_CHAIN[good_exp] == ["SHIP_PLATING", "SHIP_PARTS"]:
            continue  # skip actual ships, include components below
        used_in_production = False
        for goods_imp in SUPPLY_CHAIN.values():
            if good_exp in goods_imp:
                used_in_production = True
                break
        if not used_in_production:
            consumer_goods.append(good_exp)
    for good in sorted(raw_goods):
        if good in ["ICE_WATER", "SHIP_SALVAGE"]:  # junk, ignore
            raw_goods.remove(good)
    for good in sorted(consumer_goods):
        if good in ["ANTIMATTER", "FAB_MATS", "FUEL", "SHIP_PARTS", "SHIP_PLATING"]:
            consumer_goods.remove(good)
            player_goods.append(good)
        if good.startswith(("ENGINE_", "MODULE_", "MOUNT_", "REACTOR_")):
            consumer_goods.remove(good)
            player_goods.append(good)

    # identify markets where each good can be traded
    port2goods = {"imports": set(), "exports": set(), "exchange": set()}
    for wp, md in system.markets.items():
        for key in ["imports", "exports", "exchange"]:
            for good in md[key]:
                port2goods[key].add(good)

    def update_raw2product(product, good):
        """Recursive function to find fully connected supply chains"""
        if good in raw_goods:
            if good not in raw2products:
                raw2products[good] = set()
            raw2products[good].add(product)
        elif good not in port2goods["exports"]:
            return False
        else:
            for material in SUPPLY_CHAIN[good]:
                if not update_raw2product(product, material):
                    return False
        return True

    # for each tradeGood of interest,
    # - find out if it's supply chain is present in-system
    # - and if so, record it's raw materials
    raw2products = {}
    target_goods = (set(consumer_goods) & port2goods["imports"]) | set(player_goods)
    for good in target_goods:
        update_raw2product(good, good)

    return raw2products


def assign_drone(ship_wp, remaining, key, trait2waypoints, system):
    best = None, None, None, float("inf")
    for trait, n in remaining[key].items():
        action_wp, sell_wp = trait2waypoints[trait]
        dist = 0
        if ship_wp != action_wp:
            dist = round(system.graph[ship_wp][action_wp]["distance"])
        # tiebreaker: number of required drones
        dist -= n / 100
        # assign extra drones only if not needed elsewhere
        if n == 0:
            dist += 1_000_000
        if dist < best[3]:
            best = action_wp, sell_wp, trait, dist
    action_wp, sell_wp, trait, dist = best
    remaining[key][trait] -= 1
    return action_wp, sell_wp, trait


def get_whitelist(system, action_wp, trait2raw_goods):
    """list of worthwhile goods at the waypoint"""
    whitelist = set()
    for t in set(system.waypoints[action_wp]["traits"]) & set(trait2raw_goods):
        whitelist.update(trait2raw_goods[t])
    whitelist = ",".join(sorted(whitelist))
    return whitelist
