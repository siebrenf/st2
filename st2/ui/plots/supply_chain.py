from colorama import Fore, Style
from colorama import init as colorama_init
from psycopg import connect

from st2.ai.trade import get_tradegood
from st2.db.static import SUPPLY_CHAIN
from st2.mining import EXTRACT, EXTRACT2TRAIT, SIPHON
from st2.system import System

colorama_init()


def categorized_goods():
    # good that can be extracted/siphoned
    raw_goods = set(EXTRACT + SIPHON)
    # goods that are consumed by waypoints
    consumer_goods = set()
    # goods that are consumed by players
    player_goods = {"ANTIMATTER", "FAB_MATS", "FUEL", "SHIP_PARTS", "SHIP_PLATING"}
    ship_components = set()
    ships = set()  # all use "SHIP_PARTS", "SHIP_PLATING"

    # prefixes of all ship-related goods
    ship_components_prefixes = ("ENGINE_", "MODULE_", "MOUNT_", "REACTOR_")
    intermediates = set()
    for goods_imp in SUPPLY_CHAIN.values():
        intermediates.update(goods_imp)
    for good_exp in SUPPLY_CHAIN.keys():
        if good_exp in player_goods | raw_goods:
            continue
        if good_exp.startswith("SHIP_"):
            ships.add(good_exp)
            continue
        if good_exp.startswith(ship_components_prefixes):
            ship_components.add(good_exp)
            continue
        if good_exp not in intermediates:
            consumer_goods.add(good_exp)

    return raw_goods, player_goods, consumer_goods, ship_components


def in_system_categorized_goods(
    system, port2good2wp, raw_goods, player_goods, consumer_goods, ship_components
):

    def chained(product):
        """Recursive function to find fully connected supply chains"""
        for material in SUPPLY_CHAIN[product]:
            if material in raw_goods & set(
                port2good2wp["exchange"]
            ):  # TODO: currently need an exchange wp
                desired_raw_goods.add(material)
                continue
            if not material in port2good2wp["sell"]:
                return False
            if not chained(material):
                return False
        return True

    # goods with production supported in-system
    desired_raw_goods = set()
    complete_goods = {
        "raw_goods": set(),
        "player_goods": set(),
        "consumer_goods": set(),
        "ship_components": set(),
    }
    for good in sorted(raw_goods):
        if good in SIPHON:
            if len(system.waypoints_with(type="GAS_GIANT")):
                complete_goods["raw_goods"].add(good)
        else:
            traits = EXTRACT2TRAIT[good]
            for trait in traits:
                if len(system.waypoints_with(traits=trait)):
                    complete_goods["raw_goods"].add(good)
                    break

    used = set(port2good2wp["imports"]) | player_goods
    for key, goods in zip(
        ["player_goods", "consumer_goods", "ship_components"],
        [player_goods, consumer_goods, ship_components],
    ):
        for good in sorted(goods):
            if good in used and good in port2good2wp["sell"] and chained(good):
                complete_goods[key].add(good)
    # filter for desired raw goods
    complete_goods["raw_goods"] = complete_goods["raw_goods"] & desired_raw_goods

    return complete_goods.values()


def print_supply_chain(system_symbol):
    rpcs = categorized_goods()

    system = System(system_symbol)
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

    # in-system goods & components
    raw_goods, player_goods, consumer_goods, ship_components = (
        in_system_categorized_goods(system, port2good2wp, *rpcs)
    )

    def chained_wps(product, spaces=0, buyers=None):
        if buyers is None:
            buyers = port2good2wp["imports"].get(product, set())
        if product in raw_goods:
            sellers = port2good2wp["exchange"].get(product, set())
        else:
            sellers = port2good2wp["exports"].get(product, set())

        line = []
        for wp in buyers:
            if f"{Fore.GREEN}buyers{Style.RESET_ALL}" not in line:
                line.append(f"{Fore.GREEN}buyers{Style.RESET_ALL}")
            md = get_tradegood(wp, product)
            s = md.get("supply", "N")
            a = str(md.get("activity", "N"))
            line.append(f"{wp} {s}/{a}{Fore.YELLOW},{Style.RESET_ALL}")
        for wp in sellers:
            if f"{Fore.RED}sellers{Style.RESET_ALL}" not in line:
                line.append(f"{Fore.RED}sellers{Style.RESET_ALL}")
            md = get_tradegood(wp, product)
            s = md.get("supply", "N")
            a = str(md.get("activity", "N"))
            line.append(f"{wp} {s}/{a}{Fore.YELLOW},{Style.RESET_ALL}")
        line = " ".join(line)
        print(f"{spaces * " "}- {product} {line}")

        for material in sorted(SUPPLY_CHAIN[product]):
            if product not in raw_goods:
                chained_wps(material, spaces + 2, sellers)

    # print the supply chain for complete goods
    for good in sorted(consumer_goods | player_goods | ship_components):
        chained_wps(good)
        print()


if __name__ == "__main__":
    import os

    from st2.startup import game_server

    game_server()
    agent_symbol = os.environ["ST_AGENT_SYMBOL"]

    with connect("dbname=st2 user=postgres") as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT "headquarters" FROM agents_public
            WHERE symbol = %s
            """,
            [agent_symbol],
        )
        hq = cur.fetchone()[0]
    system_symbol = hq.rsplit("-", 1)[0]
    print_supply_chain(system_symbol)
