from asyncio import sleep

from psycopg import connect

from st2.agent import get_agent, get_agent_public
from st2.ai.utils import get_tasks, queue_task
from st2.db.static import SUPPLY_CHAIN
from st2.logging import logger
from st2.request import RequestMp
from st2.ship import Ship, buy_ship
from st2.system import System

DEBUG = True
TRAIT2EXTRACT = {
    "COMMON_METAL_DEPOSITS": [
        "ALUMINUM_ORE",
        "COPPER_ORE",
        "ICE_WATER",
        "IRON_ORE",
        "QUARTZ_SAND",
        "SILICON_CRYSTALS",
    ],
    "MINERAL_DEPOSITS": [
        "AMMONIA_ICE",
        "DIAMONDS",
        "ICE_WATER",
        "IRON_ORE",
        "PRECIOUS_STONES",
        "QUARTZ_SAND",
        "SILICON_CRYSTALS",
    ],
    "PRECIOUS_METAL_DEPOSITS": [
        "ALUMINUM_ORE",
        "COPPER_ORE",
        "GOLD_ORE",
        "ICE_WATER",
        "PLATINUM_ORE",
        "QUARTZ_SAND",
        "SILICON_CRYSTALS",
        "SILVER_ORE",
    ],
    "RARE_METAL_DEPOSITS": [
        "ALUMINUM_ORE",
        "COPPER_ORE",
        "GOLD_ORE",
        "ICE_WATER",
        "MERITIUM_ORE",
        "PLATINUM_ORE",
        "QUARTZ_SAND",
        "SILICON_CRYSTALS",
        "URANITE_ORE",
    ],
}
EXTRACT2TRAIT = {}
for tr, es in TRAIT2EXTRACT.items():
    for e in es:
        EXTRACT2TRAIT.setdefault(e, []).append(tr)
del tr, es, e


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
    # TODO:
    #  - ICE_WATER is truly useless
    #  - QUARTZ_SAND is only used for FAB_MATS
    token = get_agent(agent_symbol)["token"]
    request = RequestMp(qa_pairs, priority, token)
    system = System(system_symbol, request, priority)

    # wait until all shipyards and marketplaces are charted & scouted
    while len(system.uncharted_markets()) + len(system.unscouted_markets()) != 0:
        await sleep(interval)
        system.refresh(refresh_graph=False)

    # get all required traits & derived raw goods to feed the start system
    complete_consumer_goods, complete_raw_goods = get_raw_and_final_consumer_goods(
        system
    )
    traits2goods = {}
    deposits = {
        "COMMON_METAL_DEPOSITS",
        "MINERAL_DEPOSITS",
        "PRECIOUS_METAL_DEPOSITS",
        "RARE_METAL_DEPOSITS",
    }
    for good in complete_raw_goods:
        if good in ["HYDROCARBON", "LIQUID_HYDROGEN", "LIQUID_NITROGEN"]:
            continue  # siphoned goods, always present for FUEL production
        for deposit in sorted(deposits):
            if deposit in EXTRACT2TRAIT[good]:
                if deposit not in traits2goods:
                    traits2goods[deposit] = set()
                traits2goods[deposit].add(good)
                break

    # for each trait, find the best extract_wp and extract_sell_wp
    trait2waypoints = {}
    for trait in sorted(traits2goods):
        rest = deposits - {trait}
        best = None, None, float("inf")

        extract_sell_wps = None
        for good in traits2goods[trait]:
            if extract_sell_wps is None:
                extract_sell_wps = set(system.markets_with(good, "buys"))
            else:
                extract_sell_wps = extract_sell_wps & set(
                    system.markets_with(good, "buys")
                )

        for extract_wp in system.waypoints_with(
            traits=trait, type=["ASTEROID", "ENGINEERED_ASTEROID"]
        ):
            # TODO: exclude extract_wps out of range
            # penalize unwanted products
            penalty = 200 * len(
                set(system.waypoints[extract_wp]["traits"]) & rest  # noqa
            )
            for extract_sell_wp in extract_sell_wps:
                dist = (
                    system.graph[extract_wp][extract_sell_wp]["distance"]  # noqa
                    + penalty
                )
                if dist < best[2]:
                    best = extract_wp, extract_sell_wp, dist
        extract_wp, extract_sell_wp, dist = best
        if extract_wp:
            trait2waypoints[trait] = extract_wp, extract_sell_wp

    # select a market that exchanges siphoned goods, around a gas giant
    #  tiebreaker: distance to center
    type2waypoints = {}
    best = None, None, float("inf")
    center_wp = system.central_waypoint()
    for siphon_sell_wp in system.markets_with("HYDROCARBON", "EXCHANGE"):
        siphon_wp = system.waypoints[siphon_sell_wp].get("orbits")  # noqa
        if system.waypoints.get(siphon_wp, {}).get("type") == "GAS_GIANT":
            dist = system.graph[center_wp][siphon_wp]["distance"]  # noqa
            if dist < best[2]:
                best = siphon_wp, siphon_sell_wp, dist
    siphon_wp, siphon_sell_wp, dist = best
    type2waypoints["GAS_GIANT"] = siphon_wp, siphon_sell_wp

    target = {"siphon": {"GAS_GIANT": 2}, "extract": {}, "survey": {}}
    for trait in sorted(trait2waypoints):
        target["extract"][trait] = 2
        target["survey"][trait] = 1

    remaining = target.copy()
    for task in get_tasks(
        system_symbol=system.symbol,
        agent_symbol=agent_symbol,
        pname="drones",
    ):
        for key in ["current", "queued"]:
            t = str(task[key]).split(" ")
            if t[0] == "siphon":
                remaining["siphon"]["GAS_GIANT"] -= 1
            if t[0] in ["extract", "survey"]:
                action, extract_wp = t[0:2]
                for trait, (e_wp, es_wp) in trait2waypoints.items():
                    if extract_wp == e_wp:
                        remaining[action][trait] -= 1
    if DEBUG:
        logger.debug(f"Start System Controller {system_symbol}: {remaining=}")

    # TODO: alternate mining/surveying drones
    probed_shipyards = set()
    for action, v in remaining.items():
        for trait, n_ships in v.items():
            if action == "siphon":
                ship_type = "SHIP_SIPHON_DRONE"
                siphon_wp, siphon_sell_wp = type2waypoints["GAS_GIANT"]
                task = f"siphon {siphon_wp} {siphon_sell_wp}"
            elif action == "extract":
                ship_type = "SHIP_MINING_DRONE"
                extract_wp, extract_sell_wp = trait2waypoints[trait]
                task = f"extract {extract_wp} {extract_sell_wp}"
            elif action == "survey":
                ship_type = "SHIP_SURVEYOR"
                extract_wp, extract_sell_wp = trait2waypoints[trait]
                task = f"survey {extract_wp}"
            else:
                raise ValueError

            for _ in range(n_ships):
                while True:
                    await sleep(interval)

                    best = None, {}
                    for shipyard_symbol, md in system.shipyards_with(ship_type).items():
                        if md["purchasePrice"] < best[1].get(
                            "purchasePrice", float("inf")
                        ):
                            best = shipyard_symbol, md
                    shipyard_symbol, md = best

                    if shipyard_symbol not in probed_shipyards:
                        tasks = get_tasks(
                            current=f"probe shipyard {shipyard_symbol}",
                            agent_symbol=agent_symbol,
                        )
                        if tasks is None:
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

                ship = buy_ship(
                    ship_type, shipyard_symbol, agent_symbol, request, verbose
                )
                with connect("dbname=st2 user=postgres") as conn, conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE tasks
                        SET "pname" = %s
                        WHERE "symbol" = %s
                        """,
                        ("drones", ship),
                    )
                queue_task(ship, task)
                remaining[action][trait] -= 1
                if DEBUG:
                    logger.debug(
                        f"Start System Controller {system_symbol}: {remaining=}"
                    )

    if DEBUG:
        logger.debug(f"Start System Controller {system_symbol}: task completed")
    return "self destruct"


def get_raw_and_final_consumer_goods(system):
    # good that can be extracted/siphoned
    raw_goods = []
    # goods that are consumed by waypoints
    consumer_goods = []
    for good_exp in SUPPLY_CHAIN.keys():
        if SUPPLY_CHAIN[good_exp] in [["EXPLOSIVES"], ["MACHINERY"]]:
            raw_goods.append(good_exp)
        used_in_production = False
        for goods_imp in SUPPLY_CHAIN.values():
            if good_exp in goods_imp:
                used_in_production = True
                break
        if not used_in_production:
            consumer_goods.append(good_exp)

    port2good2wp = {"imports": {}, "exports": {}, "exchange": {}, "sell": {}}
    for wp, md in system.markets.items():
        for key in ["imports", "exports", "exchange"]:
            for good in md[key]:
                if good not in port2good2wp[key]:
                    port2good2wp[key][good] = set()
                port2good2wp[key][good].add(wp)
                if key == "imports":
                    continue
                if good not in port2good2wp["sell"]:
                    port2good2wp["sell"][good] = set()
                port2good2wp["sell"][good].add(wp)

    def chained(product):
        """Recursive function to find fully connected supply chains"""
        for material in SUPPLY_CHAIN[product]:
            if material in raw_goods:
                complete_raw_goods.add(material)
                continue
            if not material in port2good2wp["sell"]:
                return False
            if not chained(material):
                return False
        return True

    # consumer goods with production supported in-system
    complete_consumer_goods = set()
    complete_raw_goods = set()
    for good in consumer_goods:
        if (
            (
                good in port2good2wp["imports"]
                or good
                in ["ANTIMATTER", "FAB_MATS", "FUEL", "SHIP_PARTS", "SHIP_PLATING"]
            )
            and good in port2good2wp["sell"]
            and chained(good)
        ):
            complete_consumer_goods.add(good)
    return complete_consumer_goods, complete_raw_goods
