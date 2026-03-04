import itertools
import os

import matplotlib.pyplot as plt
from psycopg import connect
from psycopg.rows import dict_row

from st2.db import get_table


def get_contract_data():
    contracts = []
    for row in get_table("contracts"):
        if not row["fulfilled"]:
            continue
        contract_id = row["id"]
        payment = sum(row["terms"]["payment"].values())
        deliver = row["terms"]["deliver"]
        goods = {}
        for d in deliver:
            good = d["tradeSymbol"]
            if good not in goods:
                goods[good] = 0
            goods[good] += d["unitsRequired"]
        with connect("dbname=st2 user=postgres") as conn, conn.cursor() as cur:
            ret = cur.execute(
                """SELECT bulk_transactions_id FROM ai_deliver_system WHERE contracts_id = %s""",
                [contract_id],
            ).fetchall()
        costs = 0
        supplies = []
        for (bulk_transactions_id,) in ret:
            with connect(
                "dbname=st2 user=postgres", row_factory=dict_row
            ) as conn, conn.cursor() as cur:
                ret2 = cur.execute(
                    """SELECT * FROM bulk_transactions WHERE id = %s""",
                    [bulk_transactions_id],
                ).fetchall()
            for bulk_transaction in ret2:
                for ta in bulk_transaction["transactions"]:
                    costs += ta["totalPrice"]
                for tg in bulk_transaction["tradegoods"]:
                    supplies.append(tg["supply"])
        profit = payment - costs
        roi = round(profit / costs, 2)
        contracts.append([roi, profit, costs, goods, supplies])
    return contracts


def plot_contract_breakdown():
    contracts = get_contract_data()

    good2color = {}
    tab20_colors = plt.get_cmap("tab20").colors
    color_cycle = itertools.cycle(tab20_colors)
    good2x = {None: 0}
    supply2x = {
        "SCARCE": -2,
        "LIMITED": -1,
        "MODERATE": 0,
        "HIGH": 1,
        "ABUNDANT": 2,
    }

    fig, axs = plt.subplots(2, 2)
    for roi, profit, costs, goods, supplies in contracts:
        x = costs
        y = profit
        good = list(goods)[0]
        g = "_".join([g[0:3] for g in good.split("_")])
        units = goods[good]
        if good not in good2color:
            good2color[good] = next(color_cycle)
        color = good2color[good]
        axs[0, 0].scatter(x=x, y=y, color=color)
        axs[0, 0].annotate(
            text=f"{g} {units}",
            xy=(x, y),
            xycoords="data",
            zorder=-1,
        )

        x = units
        axs[0, 1].scatter(x=x, y=y, color=color)
        axs[0, 1].annotate(
            text=good,
            xy=(x, y),
            xycoords="data",
            zorder=-1,
        )

        x = sum(supply2x[s] for s in supplies) / len(supplies)
        axs[1, 0].scatter(x=x, y=y, color=color)
        axs[1, 0].annotate(
            text=f"{g} {units}",
            xy=(x, y),
            xycoords="data",
            zorder=-1,
        )

        if good not in good2x:
            good2x[good] = max(good2x.values()) + 1
        x = good2x[good]
        axs[1, 1].scatter(x=x, y=y, color=color)
        axs[1, 1].annotate(
            text=units,
            xy=(x, y),
            xycoords="data",
            zorder=-1,
        )
    axs[0, 0].set_xlabel("Cost")
    axs[0, 0].set_ylabel("Profit")
    axs[0, 1].set_xlabel("Number of units")
    axs[0, 1].set_ylabel("Profit")
    axs[1, 0].set_xticks(
        ticks=list(supply2x.values()),
        labels=list(supply2x.keys()),
        rotation=45,
        ha="right",
    )
    axs[1, 0].set_xlabel("Avg supply level on purchase")
    axs[1, 0].set_ylabel("Profit")
    axs[1, 1].set_xticks(
        ticks=list(good2x.values()), labels=list(good2x.keys()), rotation=45, ha="right"
    )
    axs[1, 1].set_xlabel("TradeGood")
    axs[1, 1].set_ylabel("Profit")
    reset_window = os.environ["ST_RESET_WINDOW"]
    fig.suptitle(
        f"Contract profit breakdown during {reset_window} (n={len(contracts):_})"
    )
    return fig, axs


if __name__ == "__main__":
    from st2.startup import game_server

    game_server()
    fig, axs = plot_contract_breakdown()
    plt.show()
