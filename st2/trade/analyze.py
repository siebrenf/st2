import pandas as pd
from psycopg import connect
from psycopg.rows import dict_row

from st2.db import get_table
from st2.trade import a_prior, get_a, get_base_price, set_a
from st2.trade.base_prices import BASE_PRICES

# add values for `a` everywhere
with connect(
    "dbname=st2 user=postgres", row_factory=dict_row
) as conn, conn.cursor() as cur:
    ret = cur.execute(
        """
        SELECT DISTINCT ON ("waypointSymbol", "symbol") * FROM market_tradegoods
        ORDER BY "waypointSymbol", "symbol", "timestamp" DESC;
        """
    ).fetchall()
    for trade_good in ret:
        if BASE_PRICES.get(trade_good["symbol"]) is None:
            print(trade_good)
            continue  # TODO

        for action in ["sell", "purchase"]:
            if action == "purchase" and trade_good["type"] == "IMPORT":
                continue
            if action == "sell" and trade_good["type"] == "EXPORT":
                continue
            # action = "sell" if trade_good["type"] == "IMPORT" else "purchase"
            price = trade_good[f"{action}Price"]
            base_price = get_base_price(trade_good["symbol"], action)
            a, score = get_a(trade_good["waypointSymbol"], trade_good["symbol"])
            if score >= 10:
                print(trade_good["waypointSymbol"], trade_good["symbol"], a, score)
                a, score = a_prior(
                    price,
                    trade_good["supply"],
                    base_price,
                    trade_good["type"],
                    action,
                )
                set_a(trade_good["waypointSymbol"], trade_good["symbol"], a, score)
                print(trade_good["waypointSymbol"], trade_good["symbol"], a, score)

rows = []
for row in get_table("market_a", as_dict=True):
    rows.append(row)
df = pd.DataFrame(rows).sort_values(["waypointSymbol", "score"])
wps = sorted(df["waypointSymbol"].unique())
for wp in wps:
    df2 = df[df["waypointSymbol"] == wp]
    print(df2)


price_ranges = {}
with connect(
    "dbname=st2 user=postgres", row_factory=dict_row
) as conn, conn.cursor() as cur:
    ret = cur.execute(
        """
        SELECT DISTINCT ON ("waypointSymbol", "symbol") * FROM market_tradegoods
        ORDER BY "waypointSymbol", "symbol", "timestamp" DESC;
        """
    ).fetchall()
    for trade_good in ret:
        good = trade_good["symbol"]
        if good not in price_ranges:
            price_ranges[good] = {}
            # for supply in SUPPLY:
            #     price_ranges[good][supply] = {
            #         "sellPrice": {},
            #         "purchasePrice": {},
            #     }
            port = trade_good["type"]
            if port == "EXPORT":
                trade_good["sellPrice"] = trade_good["sellPrice"] * 2
            elif port == "IMPORT":
                trade_good["purchasePrice"] = trade_good["purchasePrice"] / 2
            else:
                trade_good["purchasePrice"] = (trade_good["purchasePrice"] / 101) * 100
                trade_good["sellPrice"] = (trade_good["sellPrice"] / 99) * 100

            supply = trade_good["supply"]
            if supply not in price_ranges[good]:
                price_ranges[good][supply] = {"purchasePrice": {}, "sellPrice": {}}
            if (
                price_ranges[good][supply]["purchasePrice"].get("min", float("inf"))
                > trade_good["purchasePrice"]
            ):
                price_ranges[good][supply]["purchasePrice"]["min"] = trade_good[
                    "purchasePrice"
                ]
            if (
                price_ranges[good][supply]["purchasePrice"].get("max", -float("inf"))
                < trade_good["purchasePrice"]
            ):
                price_ranges[good][supply]["purchasePrice"]["max"] = trade_good[
                    "purchasePrice"
                ]

            if (
                price_ranges[good][supply]["sellPrice"].get("min", float("inf"))
                > trade_good["sellPrice"]
            ):
                price_ranges[good][supply]["sellPrice"]["min"] = trade_good["sellPrice"]
            if (
                price_ranges[good][supply]["sellPrice"].get("max", -float("inf"))
                < trade_good["sellPrice"]
            ):
                price_ranges[good][supply]["sellPrice"]["max"] = trade_good["sellPrice"]

for good in sorted(price_ranges):
    if "MODERATE" in price_ranges[good]:
        print(good, price_ranges[good]["MODERATE"])
