from psycopg import connect
from psycopg.rows import dict_row

from st2.db.static import SUPPLY_CHAIN
from st2.system import System
from st2.ui.plots.supply_chain import categorized_goods


def plot_supply_history(good, system_symbol):
    system = System(system_symbol)
    raw_goods = categorized_goods()[0]

    def chained(product, x=0, y=0):
        if product in raw_goods:
            buyers = system.markets_with(product, "exchange")
        else:
            buyers = system.markets_with(product, "imports")
        for y_mod, buyer in enumerate(buyers):
            with connect(
                "dbname=st2 user=postgres", row_factory=dict_row
            ) as conn, conn.cursor() as cur:
                ret = cur.execute(
                    """
                    SELECT * FROM market_tradegoods
                    WHERE "waypointSymbol" = %s
                    AND "symbol" = %s
                    ORDER BY timestamp ASC
                    """,
                    [buyer, product],
                ).fetchall()
            xs = []
            ys = []
            cs = []
            for row in ret:
                xs.append(row["timestamp"])
                ys.append(row["purchasePrice"])
                cs.append("green")
            data[(x, y + y_mod)] = (product, buyer, xs, ys, cs)

        for material in sorted(SUPPLY_CHAIN[product]):
            if product not in raw_goods:
                chained(
                    material, x + 1, y
                )  # TODO: multiple materials cause overlapping y

    data = {}
    chained(good)
    for k, v in data.items():
        print(k)
        for v2 in v:
            if isinstance(v2, list):
                print(v2[:10])
            else:
                print(v2)
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
    good = "CLOTHING"
    plot_supply_history(good, system_symbol)
