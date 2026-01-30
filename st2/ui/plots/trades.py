import matplotlib.pyplot as plt
import numpy as np

from st2.trade.functions import A_VALUES, a_posterior, x2supply, x2y, y2x

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
    roi = log_entry["return_of_investment"]

    sp_obs = log_entry[f"sell_obs"]["totalPrice"]
    pp_obs = log_entry[f"purchase_obs"]["totalPrice"]
    fp_obs = log_entry["fuel_cost"]
    roi2 = round((sp_obs - pp_obs - fp_obs) / max(pp_obs + fp_obs, 1), 2)
    sp_inf = log_entry[f"sell_inf"]["totalPrice"]
    pp_inf = log_entry[f"purchase_inf"]["totalPrice"]
    r = round((sp_inf - pp_inf) / (sp_obs - pp_obs), 4)
    if roi != roi2:
        print("Error: RoIs do not match")
    print(f"profit inferred/profit observed={r}")
    print(log_entry)

    fig, axs = plt.subplots(nrows=2)
    supply_mismatch = False
    for i, action in enumerate(["purchase", "sell"]):
        tg = log_entry[f"{action}_inf"]["tradeGood"]
        tv = tg["tradeVolume"]
        s0 = tg["supply"]
        port = tg["type"]
        base_price = log_entry[f"{action}_inf"]["basePrice"]

        xs_inf = []
        us_inf = []
        ys_inf = []
        cs_inf = []
        for t in log_entry[f"{action}_inf"]["transactions"]:
            xs_inf.append(t["x"])
            us_inf.append(t["units"])
            ys_inf.append(t["pricePerUnit"])
            cs_inf.append(SUPPLY2COLOR[x2supply(t["x"])])

        tg = log_entry[f"{action}_obs"]["tradeGood"]
        s1 = tg["supply"]
        cs_obs = [
            "white" for _ in range(len(log_entry[f"{action}_obs"]["transactions"]))
        ]
        xs_obs = []
        # us_obs = []
        ys_obs = []
        # cs_obs = []
        for t in log_entry[f"{action}_obs"]["transactions"]:
            xs_obs.append(t["x"])
            # us_obs.append(t["units"])
            ys_obs.append(t["pricePerUnit"])
            # cs_obs.append(SUPPLY2COLOR[x2supply(t["x"])])
        cs_obs[0] = SUPPLY2COLOR[s0]
        cs_obs[-1] = SUPPLY2COLOR[s1]

        if s0 != x2supply(log_entry[f"{action}_obs"]["transactions"][0]["x"]):
            supply_mismatch = True
        if s1 != x2supply(log_entry[f"{action}_obs"]["transactions"][-1]["x"]):
            supply_mismatch = True
        if not supply_mismatch:  # TODO: remove
            plt.close("all")
            return

        if supply_mismatch:
            y0 = log_entry[f"{action}_obs"]["transactions"][0]["pricePerUnit"]
            y1 = log_entry[f"{action}_obs"]["transactions"][-1]["pricePerUnit"]
            a2 = a_posterior(y0, y1, s1, units, tv, port, action, base_price)

            # a1 = log_entry[f"{action}_obs"]['market_a']
            # print(a1, a2)
            # wp = log_entry[f"{action}_obs"]["tradeGood"]['waypointSymbol']
            # print(f"Updated `a` at {wp} for {good} from {a1[0]} to {a2[0]}")
            xs_obs2 = []
            for t in log_entry[f"{action}_obs"]["transactions"]:
                xs_obs2.append(y2x(t["pricePerUnit"], a2[0], base_price, port, action))
            axs[i].scatter(
                xs_obs2,
                ys_obs,
                c=cs_obs,
                zorder=3,
                s=22,
                edgecolors="black",
                marker="P",
                label=f"observed a={a2[0]}",
            )
            for j in range(0, len(xs_obs) - 1):
                axs[i].annotate(
                    text="",
                    xytext=(xs_obs2[j], ys_obs[j]),
                    xy=(xs_obs2[j + 1], ys_obs[j + 1]),
                    xycoords="data",
                    arrowprops=dict(
                        arrowstyle="->",
                        linestyle=":",
                        connectionstyle="arc3,rad=-0.7",
                        color="black",
                        zorder=3,
                    ),
                )

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
    fig.suptitle(f"{good=} {units=} {roi=}")
    plt.show()


if __name__ == "__main__":
    from st2 import time
    from st2.db import get_table
    from st2.startup import game_server

    game_server()

    t_min = time.read("2026-01-29T09:00:00.000Z")
    for row in get_table("trades", as_dict=True, ascending=False):
        if row["timestamp"] < t_min:
            continue  # fixed bug: flipped sign
        if (
            row["purchase_obs"]["tradeGood"]["tradeVolume"] >= row["units"]
            and row["sell_obs"]["tradeGood"]["tradeVolume"] >= row["units"]
        ):
            continue  # not interesting
        if len(row["purchase_obs"]["transactions"]) != len(
            row["purchase_inf"]["transactions"]
        ) or len(row["sell_obs"]["transactions"]) != len(
            row["sell_inf"]["transactions"]
        ):
            continue  # fixed bug: older tradeVolume used in transaction
        if (
            len(row["purchase_obs"]["transactions"]) == 0
            or len(row["sell_obs"]["transactions"]) == 0
        ):
            continue  # time desync bug
        plot_trade(row)
