from psycopg import connect
from psycopg.rows import dict_row
from st2.system import System


def plot_supply_chain(system_symbol):
    # # system tradeGoods
    # sellers = {}
    # buyers = {}
    # with connect(
    #     "dbname=st2 user=postgres", row_factory=dict_row
    # ) as conn, conn.cursor() as cur:
    #     ret = cur.execute(
    #         """
    #         SELECT DISTINCT ON ("waypointSymbol", "symbol") * FROM market_tradegoods
    #         WHERE "systemSymbol" = %s
    #         ORDER BY "waypointSymbol", "symbol", "timestamp" DESC;
    #         """,
    #         (system_symbol,),
    #     ).fetchall()
    # for row in ret:
    #     good = row["symbol"]
    #     if good not in buyers:
    #         buyers[good] = []
    #     buyers[good].append(row)
    #     if good not in sellers:
    #         sellers[good] = []
    #     sellers[good].append(row)

    raw_goods = [
        "ALUMINUM_ORE",
        "AMMONIA_ICE",
        "COPPER_ORE",
        "DIAMONDS" 
        "GOLD_ORE",
        "HYDROCARBON",
        "ICE_WATER",
        "IRON_ORE",
        "MERITIUM_ORE",
        "PLATINUM_ORE",
        "PRECIOUS_STONES",
        "QUARTZ_SAND",
        "SILICON_CRYSTALS",
        "SILVER_ORE",
        "URANITE_ORE",
    ]
    system = System(system_symbol)

    sold = set()  # exported + exchanged
    bought = set()  # imported
    for wp, md in system.markets:
        sold.update(md["exports"])
        sold.update(md["exchange"])
        bought.update(md["imports"])

    # supply chain elements present in this system
    exp2imp = {}
    with connect("dbname=st2 user=postgres") as conn, conn.cursor() as cur:
        ret = cur.execute("""SELECT * FROM supply_chain""").fetchall()
    for row in ret:
        good_exp, goods_imp = row
        if good_exp in raw_goods:
            continue
        if good_exp not in bought:
            continue  # good not imported in this system
        if len(goods_imp) != set(goods_imp) & sold:
            continue  # good not manufactured in this system
        exp2imp[good_exp] = goods_imp

    tiers = {}
    for good in raw_goods:
        tiers[good] = 0
    while len(exp2imp) > len(tiers):
        for good_exp, goods_imp in exp2imp.items():
            if good_exp in tiers:
                continue
            if len(goods_imp) == set(goods_imp) & set(tiers):
                best = 0
                for good_imp in goods_imp:
                    best = max(best, tiers[good_imp])
                tiers[good_exp] = best + 1
        print(tiers)  # TODO: rm

    # supply_chain = {"exports": {}, "imports": {}}
    # for wp, md in system.markets:
    #     for good_exp in wp["exports"]:
    #         if good_exp not in supply_chain:
    #             supply_chain["exports"][good_exp] = []
    #         supply_chain["exports"][good_exp].append(wp)
    #         for good_imp in exp2imp[good_exp]:
    #             if good_imp not in md["imports"] + md["exchange"]:
    #                 print(f"{good_imp} not bought at {wp}???")
    #             if good_imp not in supply_chain:
    #                 supply_chain["imports"][good_imp] = []
    #             supply_chain["imports"][good_exp].append(wp)
    #
    # supply_chain = {}
    # for good in raw_goods:
    #     for good_exp, goods_imp in exp2imp.items():
    #         if good in goods_imp and good in sellers:
    #
    #
    #     complete = True
    #     for good_imp in exp2imp[good_exp]:
    #         if good_imp not in sellers:
    #             complete = False
    #             break  # broken supply chain
    #     if


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
