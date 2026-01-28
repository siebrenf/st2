import matplotlib.pyplot as plt
import numpy as np

from st2.trade.functions import A_VALUES, x2supply, x2y

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
    fig, axs = plt.subplots(nrows=2)
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
        # cs_obs = ["white" for _ in range(len(log_entry[f"{action}_obs"]["transactions"]))]
        xs_obs = []
        us_obs = []
        ys_obs = []
        cs_obs = []
        for t in log_entry[f"{action}_obs"]["transactions"]:
            xs_obs.append(t["x"])
            us_obs.append(t["units"])
            ys_obs.append(t["pricePerUnit"])
            cs_obs.append(SUPPLY2COLOR[x2supply(t["x"])])
        cs_obs[0] = SUPPLY2COLOR[s0]
        cs_obs[-1] = SUPPLY2COLOR[s1]

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
        for j in range(1, len(xs_inf)):
            axs[i].arrow(
                xs_inf[j - 1],
                ys_inf[j - 1],
                xs_inf[j] - xs_inf[j - 1],
                ys_inf[j] - ys_inf[j - 1],
                joinstyle="miter",
                fill=False,
                zorder=2,
                width=0.001,
                length_includes_head=True,
                head_width=0.15,
                head_length=50.0,
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
        for j in range(1, len(xs_obs)):
            axs[i].arrow(
                xs_obs[j - 1],
                ys_obs[j - 1],
                xs_obs[j] - xs_obs[j - 1],
                ys_obs[j] - ys_obs[j - 1],
                joinstyle="miter",
                fill=False,
                zorder=2,
                width=0.001,
                length_includes_head=True,
                head_width=0.15,
                head_length=50.0,
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
    from st2.db import get_table
    from st2.startup import game_server

    game_server()

    for row in get_table("trades", as_dict=True):
        if (
            len(row["purchase_obs"]["transactions"]) == 0
            or len(row["sell_obs"]["transactions"]) == 0
        ):
            continue  # time desync bug
        if (
            row["purchase_obs"]["tradeGood"]["tradeVolume"] >= row["units"]
            and row["sell_obs"]["tradeGood"]["tradeVolume"] >= row["units"]
        ):
            continue  # not interesting
        plot_trade(row)
