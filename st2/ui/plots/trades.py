import matplotlib.pyplot as plt
import numpy as np

from st2.ship._cargo import a_posterior
from st2.trade import get_base_price
from st2.trade.functions import A_VALUES, x2supply, x2y, y2x

SUPPLY2COLOR = {
    "SCARCE": "red",
    "LIMITED": "orange",
    "MODERATE": "grey",
    "HIGH": "lightblue",
    "ABUNDANT": "blue",
}


def plot_trade(log_entry):
    good = log_entry["symbol"]
    units = log_entry["units"]

    sp_obs = log_entry[f"sell_obs"]["totalPrice"]
    pp_obs = log_entry[f"purchase_obs"]["totalPrice"]
    fp_obs = log_entry["fuel_cost"]
    sp_inf = log_entry[f"sell_inf"]["totalPrice"]
    pp_inf = log_entry[f"purchase_inf"]["totalPrice"]
    if log_entry["return_on_investment"] != round(
        (sp_obs - pp_obs - fp_obs) / max(pp_obs + fp_obs, 1), 2
    ):
        print("Error: RoIs do not match")
    print(log_entry)

    fig, axs = plt.subplots(nrows=2)
    # supply_mismatch = False
    for i, action in enumerate(["purchase", "sell"]):
        base_price = get_base_price(good, action)
        tg = log_entry[f"{action}_inf"]["tradeGood"]
        tv = tg["tradeVolume"]
        s0 = tg["supply"]
        port = tg["type"]

        xs_inf = []  # based on 1 inferred value, then adjusted by observed dx values
        ys_inf = []  # based on all inferred values
        cs_inf = []  # based on all inferred values
        for t in log_entry[f"{action}_inf"]["transactions"]:
            xs_inf.append(t["x"])
            ys_inf.append(t["pricePerUnit"])
            cs_inf.append(SUPPLY2COLOR[x2supply(t["x"])])
        # trailing value (from inferred final tradeGood)
        ta = log_entry[f"{action}_inf"]["transactions"][-1]
        a_inf, score_inf = log_entry[f"{action}_obs"]["market_a"]
        x = ta["x"]
        dx = ta["units"] / tv
        x += dx if action == "sell" else -dx
        y = x2y(x, a_inf, base_price, port, action)
        xs_inf.append(x)
        ys_inf.append(y)
        cs_inf.append(SUPPLY2COLOR[x2supply(x)])

        tg = log_entry[f"{action}_obs"]["tradeGoods"][0]
        a_obs, score_obs = log_entry[f"{action}_obs"]["market_a"]
        s1 = tg["supply"]

        xs_obs = []  # based on all **inferred** values
        ys_obs = []  # based on all observed values
        cs_obs = []  # based on all observed values
        tv_obs = []
        for j, t in enumerate(log_entry[f"{action}_obs"]["transactions"]):
            tg = log_entry[f"{action}_obs"]["tradeGoods"][j]
            tv_obs.append(tg["tradeVolume"])
            x = y2x(t["pricePerUnit"], a_obs, base_price, port, action)
            xs_obs.append(x)
            ys_obs.append(t["pricePerUnit"])
            cs_obs.append(SUPPLY2COLOR[tg["supply"]])
            if t["pricePerUnit"] != tg[f"{action}Price"]:
                print(good, j, t["pricePerUnit"], tg[f"{action}Price"])
        # trailing value (from the final tradeGood)
        tg = log_entry[f"{action}_obs"]["tradeGoods"][j + 1]
        y = tg[f"{action}Price"]
        x = y2x(y, a_obs, base_price, port, action)
        xs_obs.append(x)
        ys_obs.append(y)
        cs_obs.append(SUPPLY2COLOR[tg["supply"]])

        tgs = log_entry[f"{action}_obs"]["tradeGoods"]
        tas = log_entry[f"{action}_obs"]["transactions"]
        a2, score2 = a_posterior(None, tgs, tas, action, base_price)
        print(f"{a_obs=} {score_obs=} {a2} {score2}")
        if len(set(tv_obs)) != 1:
            print("TV changed:", tv_obs)

        # if s0 != x2supply(log_entry[f"{action}_obs"]["transactions"][0]["x"]):
        #     supply_mismatch = True
        # if s1 != x2supply(log_entry[f"{action}_obs"]["transactions"][-1]["x"]):
        #     supply_mismatch = True
        # if not supply_mismatch:
        #     plt.close("all")
        #     return
        #
        # if supply_mismatch:
        #     y0 = log_entry[f"{action}_obs"]["transactions"][0]["pricePerUnit"]
        #     y1 = log_entry[f"{action}_obs"]["transactions"][-1]["pricePerUnit"]
        #     a2 = a_posterior(y0, y1, s1, units, tv, port, action, base_price)
        #
        #     # a1 = log_entry[f"{action}_obs"]['market_a']
        #     # print(a1, a2)
        #     # wp = log_entry[f"{action}_obs"]["tradeGood"]['waypointSymbol']
        #     # print(f"Updated `a` at {wp} for {good} from {a1[0]} to {a2[0]}")
        #     xs_obs2 = []
        #     for t in log_entry[f"{action}_obs"]["transactions"]:
        #         xs_obs2.append(y2x(t["pricePerUnit"], a2[0], base_price, port, action))
        #     axs[i].scatter(
        #         xs_obs2,
        #         ys_obs,
        #         c=cs_obs,
        #         zorder=3,
        #         s=22,
        #         edgecolors="black",
        #         marker="P",
        #         label=f"observed a={a2[0]}",
        #     )
        #     for j in range(0, len(xs_obs) - 1):
        #         axs[i].annotate(
        #             text="",
        #             xytext=(xs_obs2[j], ys_obs[j]),
        #             xy=(xs_obs2[j + 1], ys_obs[j + 1]),
        #             xycoords="data",
        #             arrowprops=dict(
        #                 arrowstyle="->",
        #                 linestyle=":",
        #                 connectionstyle="arc3,rad=-0.7",
        #                 color="black",
        #                 zorder=3,
        #             ),
        #         )

        xs = np.linspace(-6, 6, 12 * tv + 1, endpoint=True)
        for a in A_VALUES:
            ys = []
            cs = []
            for x in xs:
                ys.append(x2y(x, a, base_price, port, action))
                s = x2supply(x)
                cs.append(SUPPLY2COLOR[s])
            axs[i].scatter(xs, ys, c=cs, zorder=1, s=18, alpha=0.5)
            axs[i].plot(xs, ys, zorder=-2, label=f"{a=}")  #  if i == 0 else None
        axs[i].scatter(
            xs,
            [base_price for _ in range(len(xs))],
            c="grey",
            alpha=0.5,
            marker="|",
            zorder=-5,
            label=f"{tv=}",
        )
        axs[i].scatter(
            xs_inf,
            ys_inf,
            c=cs_inf,
            zorder=2,
            s=22,
            edgecolors="black",
            marker="D",
            label="inferred",
        )
        for j in range(0, len(xs_inf) - 1):
            axs[i].annotate(
                text="",
                xytext=(xs_inf[j], ys_inf[j]),
                xy=(xs_inf[j + 1], ys_inf[j + 1]),
                xycoords="data",
                arrowprops=dict(
                    arrowstyle="->",
                    linestyle="--",
                    connectionstyle="arc3,rad=0.7",
                    color="black",
                    zorder=2,
                ),
            )
        axs[i].scatter(
            xs_obs,
            ys_obs,
            c=cs_obs,
            zorder=2,
            s=22,
            edgecolors="black",
            marker="s",
            label="observed",
        )
        for j in range(0, len(xs_obs) - 1):
            axs[i].annotate(
                text="",
                xytext=(xs_obs[j], ys_obs[j]),
                xy=(xs_obs[j + 1], ys_obs[j + 1]),
                xycoords="data",
                arrowprops=dict(
                    arrowstyle="->",
                    # head_length=0.4,
                    # head_width=0.2,
                    # widthA=1.0,
                    # widthB=1.0,
                    # lengthA=0.2,
                    # lengthB=0.2,
                    # angleA=0,
                    # angleB=0,
                    # scaleA=0,
                    # scaleB=0,
                    color="black",
                    zorder=3,
                ),
            )
        axs[i].axvline(-4, zorder=-5)
        axs[i].axvline(-2, zorder=-5)
        axs[i].axvline(2, zorder=-5)
        axs[i].axvline(4, zorder=-5)
        axs[i].grid(which="major")
        axs[i].set_title(f"{action=} {port=}")
        # https://stackoverflow.com/questions/4700614/how-to-put-the-legend-outside-the-plot
        handles, labels = axs[i].get_legend_handles_labels()
        # sort both labels and handles by labels
        if handles:
            labels, handles = zip(*sorted(zip(labels, handles), key=lambda t: t[0]))
            axs[i].legend(handles, labels, loc="center left", bbox_to_anchor=(1, 0.5))
            fig.subplots_adjust(right=0.7)
    r = round(
        100 * (1 - abs((sp_inf - pp_inf) - (sp_obs - pp_obs)) / (sp_obs - pp_obs)), 2
    )
    t = log_entry["timestamp"].isoformat()[11:19]
    fig.suptitle(f"{good=} {units=} accuracy={r}% \ntime={t}")
    plt.show()


if __name__ == "__main__":
    from st2 import time
    from st2.db import get_table
    from st2.startup import game_server

    game_server()

    whitelist = ["JEWELRY"]
    for good, t_min, t_max in [
        # Bug / a / baseprice issue
        (
            "FOOD",
            time.read("2026-01-31T01:30:00.000Z"),
            time.read("2026-01-31T01:50:00.000Z"),
        ),
        # Edge case
        # ("JEWELRY", time.read("2026-01-31T01:50:00.000Z"), time.read("2026-01-31T02:10:00.000Z")),
        # Edge case
        # ("MACHINERY", time.read("2026-01-31T02:20:00.000Z"), time.read("2026-01-31T02:40:00.000Z")),
        # Edge case
        # ("MACHINERY", time.read("2026-01-31T04:00:00.000Z"), time.read("2026-01-31T06:00:00.000Z")),
        # Edge case
        # ("SHIP_PLATING", time.read("2026-01-31T05:00:00.000Z"), time.read("2026-01-31T05:30:00.000Z")),
        # Edge case
        # ("MICROPROCESSORS", time.read("2026-01-31T07:00:20.000Z"), time.read("2026-01-31T07:40:00.000Z")),
        # Bug / a / baseprice issue
        (
            "POLYNUCLEOTIDES",
            time.read("2026-01-31T07:30:20.000Z"),
            time.read("2026-01-31T07:50:00.000Z"),
        ),
    ]:
        for row in get_table("trades", as_dict=True, ascending=True):
            if row["timestamp"] < t_min:
                continue
            if row["timestamp"] > t_max:
                continue
            if row["symbol"] != good:
                continue
            plot_trade(row)

    # t_min = time.read("2026-01-31T01:30:00.000Z")
    # for row in get_table("trades", as_dict=True, ascending=True):
    #     if row["timestamp"] < t_min:
    #         continue  # new log system
    #     # if (
    #     #     row["purchase_obs"]["tradeGoods"][0]["tradeVolume"] >= row["units"]
    #     #     and row["sell_obs"]["tradeGoods"][0]["tradeVolume"] >= row["units"]
    #     # ):
    #     #     continue  # not interesting
    #     if row["symbol"] not in whitelist:
    #         continue
    #     # if len(row["purchase_obs"]["transactions"]) != len(
    #     #     row["purchase_inf"]["transactions"]
    #     # ) or len(row["sell_obs"]["transactions"]) != len(
    #     #     row["sell_inf"]["transactions"]
    #     # ):
    #     #     continue  # fixed bug: older tradeVolume used in transaction
    #     # if (
    #     #     len(row["purchase_obs"]["transactions"]) == 0
    #     #     or len(row["sell_obs"]["transactions"]) == 0
    #     # ):
    #     #     continue  # time desync bug
    #     plot_trade(row)
