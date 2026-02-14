from psycopg import connect

from st2.ai.trade import get_tradegood
from st2.db.static import SUPPLY_CHAIN
from st2.system import System


def plot_supply_chain(system_symbol):
    # good that can be extracted/siphoned
    raw_goods = []
    # goods that are consumed by waypoints
    consumer_goods = []
    for good_exp in SUPPLY_CHAIN.keys():
        if SUPPLY_CHAIN[good_exp] in [["EXPLOSIVES"], ["MACHINERY"]]:
            raw_goods.append(good_exp)
        # # ships & ship components
        # if good_exp.startswith(("ENGINE_", "MODULE_", "MOUNT_", "REACTOR_", "SHIP_")):
        #     continue
        # # ship/gate consumables
        # if good_exp in ["ANTIMATTER", "FAB_MATS", "FUEL"]:
        #     continue
        used_in_production = False
        for goods_imp in SUPPLY_CHAIN.values():
            if good_exp in goods_imp:
                used_in_production = True
                break
        if not used_in_production:
            consumer_goods.append(good_exp)
    # production tiers (the number of markets between raw goods and the product)
    tiers = {}
    for good in raw_goods:
        tiers[good] = 0
    while len(SUPPLY_CHAIN) > len(tiers):
        for good_exp, goods_imp in SUPPLY_CHAIN.items():
            if good_exp in tiers:
                continue
            if len(goods_imp) == len(set(goods_imp) & set(tiers)):
                best = 0
                for good_imp in goods_imp:
                    best = max(best, tiers[good_imp])
                tiers[good_exp] = best + 1

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

    def chained_wps(product, buyers=None):
        if buyers is None:
            buyers = port2good2wp["imports"].get(product, set())
        if product in raw_goods:
            sellers = port2good2wp["exchange"].get(product, set())
            # port = "exchange"  # drones can sell extracted/siphoned goods here
        else:
            sellers = port2good2wp["exports"].get(product, set())
            # port = "export"
        # spaces = (max(tiers.values()) - tiers[product]) * "  "
        # print(f"{spaces}- {product} {buyers=} {sellers=} ({port=})")

        line = []
        for wp in buyers:
            if "buyers" not in line:
                line.append("buyers")
            md = get_tradegood(wp, product)
            s = md.get("supply", "N")
            a = str(md.get("activity", "N"))
            line.append(f"{wp} {s}/{a}")
        for wp in sellers:
            if "sellers" not in line:
                line.append("sellers")
            md = get_tradegood(wp, product)
            s = md.get("supply", "N")
            a = str(md.get("activity", "N"))
            line.append(f"{wp} {s}/{a}")
        line = " ".join(line)
        spaces = (max(tiers.values()) - tiers[product]) * "  "
        print(f"{spaces}- {product} {line}")

        for material in SUPPLY_CHAIN[product]:
            if product not in raw_goods:
                chained_wps(material, sellers)

    # print the supply chain for complete consumer goods
    for good in sorted(
        complete_consumer_goods
        | {"ANTIMATTER", "FAB_MATS", "FUEL", "SHIP_PARTS", "SHIP_PLATING"}
    ):
        chained_wps(good)
        print()

    print(sorted(complete_raw_goods))


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
    plot_supply_chain(system_symbol)
