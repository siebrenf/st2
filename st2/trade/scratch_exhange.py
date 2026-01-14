import os

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.optimize import curve_fit
from sklearn.metrics import r2_score

s2c = {
    "SCARCE": "red",
    "LIMITED": "orange",
    "MODERATE": "grey",
    "HIGH": "lightblue",
    "ABUNDANT": "blue",
}
baseprices = {
    "FUEL": 70,
    "DIAMONDS": 90,
    "PRECIOUS_STONES": 75,
}
g2fs = {
    "FUEL": [
        "FUEL_X1-CA66-J58_complete.tsv",
        "FUEL_X1-CA80-J60_complete.tsv",
        "FUEL_X1-DP44-I51_complete.tsv",
        "FUEL_X1-HR26-J55_complete.tsv",
        "FUEL_X1-NC74-J58_complete.tsv",
    ],
    "DIAMONDS": [
        "DIAMONDS_X1-BH81-B7_complete.tsv",
        "DIAMONDS_X1-CA66-B7_complete.tsv",
        "DIAMONDS_X1-DP44-B7_complete.tsv",
    ],
    "PRECIOUS_STONES": [
        "PRECIOUS_STONES_X1-CA66-B7_complete.tsv",
        "PRECIOUS_STONES_X1-BH81-B7_complete.tsv",
        "PRECIOUS_STONES_X1-CA80-B7_complete.tsv",
    ],
}
basedir = os.path.join(
    "/home/siebrenf/.local/share/spacepyrates/2024-04-09_2024-04-28/market_exchange"
)
x2 = np.linspace(-12, 10, 180 * (abs(-12) + abs(10)))
for good, fnames in g2fs.items():

    fig = plt.figure(figsize=(15, 10))
    ax = fig.add_subplot(111)
    y_bp = baseprices[good]
    for fname in fnames:
        df = pd.read_table(os.path.join(basedir, fname))
        wp = fname.split("_")[1][3:]
        # df.at[0, "supply"] = "SCARCE", df.at[-1, "supply"] = "ABUNDANT"
        df = df[df["action"] == "sell"].reset_index()
        tv = df.at[0, "tradeVolume"]
        port = df.at[0, "type"]
        units = df.at[0, "units"]
        assert port == "EXCHANGE"
        assert len(df["units"].unique()) == 1

        yp = df["purchasePrice"].to_list()
        ys = df["sellPrice"].to_list()
        c = [s2c[supply] for supply in df["supply"]]
        x_raw = [i * units for i in range(len(df))]
        i_mod = df[df["supply"] == "MODERATE"].index[0]
        idx_origin = i_mod + 2 * tv / units

        x = []
        for i in range(len(df)):
            x.append((i - idx_origin) * units / tv)

        # remove the lowest value (such as the minimum value)
        y_min = min(yp)
        while y_min in yp:
            i = yp.index(y_min)
            c.pop(i)
            yp.pop(i)
            ys.pop(i)
            x.pop(i)
        y_min = min(ys)
        while y_min in ys:
            i = ys.index(y_min)
            c.pop(i)
            yp.pop(i)
            ys.pop(i)
            x.pop(i)

        ax.scatter(x, yp, c=c, zorder=1, s=18, alpha=0.5)
        ax.plot(x, yp, zorder=-2, c="green", label="purchase")
        ax.axhline(y_bp, zorder=-15)
        ax.scatter(x, ys, c=c, zorder=1, s=18, alpha=0.5)
        ax.plot(x, ys, zorder=-2, c="red", label="sell")

        infer = True
        if infer:

            # def func_purchase(x, a):
            #     return y_bp * (-a / 1000 * (x - 1) ** 3 + 1) + max(2, round(y_bp / 100))
            #
            # popt, pcov = curve_fit(
            #     func_purchase, x, yp, p0=[0.35], bounds=((0, 1))
            # )  # noqa
            # a = popt[0]  # round(popt[0] * 20) / 20  # round to nearest 0.05
            # yp2 = [round(i) for i in func_purchase(np.array(x), a)]

            def func_purchase(x, a, dx=0):
                x = x - 1 + dx
                return y_bp * (-a / 1000 * x**3 + 1) + max(2, round(y_bp / 100))

            popt, pcov = curve_fit(  # noqa
                func_purchase, x, yp, p0=[0.35, 0], bounds=((0, -1), (1, 1))
            )
            a, dx = popt
            a = round(a * 20) / 20  # round to nearest 0.05
            yp2 = [round(i) for i in func_purchase(np.array(x), a, dx)]
            r_squared = r2_score(yp, yp2)
            ax.plot(
                x,
                yp2,  # [i / bp for i in y2],
                ls="--",
                zorder=10,
                label=f"{a=:.02f}  r^2={round(r_squared, 4)} {wp=}",
            )

            # def func_sell(x, a):
            #     return y_bp * (-a / 1000 * (x + 1) ** 3 + 1) - max(2, round(y_bp / 100))
            #
            # popt, pcov = curve_fit(func_sell, x, ys, p0=[0.35], bounds=((0, 1)))  # noqa
            # a = popt[0]
            # ys2 = [round(i) for i in func_sell(np.array(x), a)]

            def func_sell(x, a, dx=0):
                x = x + 1 + dx
                return y_bp * (-a / 1000 * x**3 + 1) - max(2, round(y_bp / 100))

            popt, pcov = curve_fit(  # noqa
                func_sell, x, ys, p0=[0.35, 0], bounds=((0, -1), (1, 1))
            )
            a, dx = popt
            a = round(a * 20) / 20  # round to nearest 0.05
            ys2 = [round(i) for i in func_sell(np.array(x), a, dx)]
            r_squared = r2_score(ys, ys2)
            ax.plot(
                x,
                ys2,  # [i / bp for i in y2],
                ls="--",
                zorder=10,
                label=f"{a=:.02f}  r^2={round(r_squared, 4)} {wp=}",
            )

    # ax.axvline(1, zorder=-5, ls="--", c="green")  # origin purchases
    # ax.axvline(-1, zorder=-5, ls="--", c="red")  # origin sales
    ax.axvline(-4, zorder=-5)
    ax.axvline(-2, zorder=-5)
    ax.axvline(2, zorder=-5)
    ax.axvline(4, zorder=-5)
    plt.grid(which="major")
    # https://stackoverflow.com/questions/4700614/how-to-put-the-legend-outside-the-plot
    handles, labels = ax.get_legend_handles_labels()
    # sort both labels and handles by labels
    if handles:
        labels, handles = zip(*sorted(zip(labels, handles), key=lambda t: t[0]))
        ax.legend(handles, labels, loc="center left", bbox_to_anchor=(1, 0.5))
        plt.subplots_adjust(right=0.7)
    plt.show()
