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
        wp = fname.split("_")[1]
        # df.at[0, "supply"] = "SCARCE", df.at[-1, "supply"] = "ABUNDANT"
        df = df[df["action"] == "sell"].reset_index()
        tv = df.at[0, "tradeVolume"]
        port = df.at[0, "type"]
        units = df.at[0, "units"]
        assert port == "EXCHANGE"
        assert len(df["units"].unique()) == 1

        # exc_modifier = max(2, round(y_bp/100))
        yp = df["purchasePrice"].to_list()
        ys = df["sellPrice"].to_list()
        c = [s2c[supply] for supply in df["supply"]]
        x_raw = [i * units for i in range(len(df))]
        i_mod = df[df["supply"] == "MODERATE"].index[0]
        idx_origin = i_mod + 2 * tv / units
        # xs = [((i - x_raw[i_mod]) / tv) - 0.5 * units / tv - 1 for i in x_raw]
        # xp = [((i - x_raw[i_mod]) / tv) - 0.5 * units / tv - 3 for i in x_raw]

        x = []
        for i in range(len(df)):
            x.append((i - idx_origin) * units / tv)

        # remove the lowest value (such as the minimum value)
        y_min = min(yp)
        while y_min in yp:
            i = yp.index(y_min)
            # xs.pop(i)
            # xp.pop(i)
            c.pop(i)
            yp.pop(i)
            ys.pop(i)
            x.pop(i)
        y_min = min(ys)
        while y_min in ys:
            i = ys.index(y_min)
            # xs.pop(i)
            # xp.pop(i)
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

            def func_purchase(x, a):
                return y_bp * (-a / 1000 * (x - 1) ** 3 + 1) + max(2, round(y_bp / 100))

            popt, pcov = curve_fit(
                func_purchase, x, yp, p0=[0.35], bounds=((0, 1))
            )  # noqa
            a = popt[0]  # round(popt[0] * 20) / 20  # round to nearest 0.05
            yp2 = [round(i) for i in func_purchase(np.array(x), a)]
            r_squared = r2_score(yp, yp2)
            ax.plot(
                x,
                yp2,  # [i / bp for i in y2],
                ls="--",
                zorder=10,
                label=f"{a=:.02f}  r^2={round(r_squared, 4)} {wp=}",
            )

            def func_sell(x, a):
                return y_bp * (-a / 1000 * (x + 1) ** 3 + 1) - max(2, round(y_bp / 100))

            popt, pcov = curve_fit(func_sell, x, ys, p0=[0.35], bounds=((0, 1)))  # noqa
            a = popt[0]
            ys2 = [round(i) for i in func_sell(np.array(x), a)]
            r_squared = r2_score(ys, ys2)
            ax.plot(
                x,
                ys2,  # [i / bp for i in y2],
                ls="--",
                zorder=10,
                label=f"{a=:.02f}  r^2={round(r_squared, 4)} {wp=}",
            )

            # def func(x, a):
            #     x = x - 2
            #     x = x - 1  # sell
            #     a = a / 100
            #     b = a / 2
            #     c = a / 12.5
            #     # return a * x**3 + b * x**2 + c * x + d
            #     # return a*bp * x ** 3 + b*bp * x ** 2 + c*bp * x + d*bp
            #     return y_bp * (c * x**3 + b * x**2 + a * x + 1)
            #
            # popt, pcov = curve_fit(func, xs, ys)  # noqa
            # a = round(popt[0] * 20) / 20  # round to nearest 0.05
            # # print(round(100*popt[1]/popt[0], 3), round(0.01*popt[0]/popt[1], 3), popt)
            # ys2 = [round(i) for i in func(np.array(xs), a)]  # noqa
            # r2s = r2_score(ys, ys2)
            # ys2 = func(x2, a)
            # ax.plot(
            #     x2,
            #     ys2,  # [i / bp for i in y2],
            #     ls="--",
            #     alpha=0.25,
            #     label=f"{a=:.02f} r^2={round(r2s, 2)}",
            # )
            # break

    # ax.axvline(-1, zorder=-5, ls="--", c="green")  # origin purchases
    # ax.axvline(1, zorder=-5, ls="--", c="red")  # origin sales
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


# good = "placeholder"
# title = "placeholder"
# method = "placeholder"
# first = True
# ax = None
# s2c = {
#     "SCARCE": "red",
#     "LIMITED": "orange",
#     "MODERATE": "grey",
#     "HIGH": "lightblue",
#     "ABUNDANT": "blue",
# }
# # merge all files per good
# files_per_port_per_good = {
#     "EXPORT": {},
#     "IMPORT": {},
#     "EXCHANGE": {},
# }
# # for version, folder in itertools.product(
# #     ["2024-04-28_2024-05-19"],
# #     ["collector_3", "collector_2", "collector_1", "collector"],
# # ):
# #     basedir = f"/home/siebrenf/.local/share/spacepyrates/{version}/{folder}"
# #     if not os.path.exists(basedir):
# #         continue
# #     for f in sorted(os.listdir(basedir)):
# #         if str(f).startswith((".", "~")):
# #             continue
# #         if not f.endswith("_complete.tsv"):
# #             continue
# #         fname = os.path.join(basedir, f)
# #         g, wp, port, _ = f.rsplit("_", 3)
# #         files_per_port_per_good[port].setdefault(g, []).append(fname)
#
# files_per_port_per_good["EXCHANGE"] = {'ALUMINUM_ORE': ['/home/siebrenf/.local/share/spacepyrates/2024-04-28_2024-05-19/collector_3/ALUMINUM_ORE_X1-GB78-B7_EXCHANGE_complete.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-04-28_2024-05-19/collector_1/ALUMINUM_ORE_X1-KP20-B7_EXCHANGE_complete.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-04-28_2024-05-19/collector_1/ALUMINUM_ORE_X1-NH60-B7_EXCHANGE_complete.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-04-28_2024-05-19/collector_1/ALUMINUM_ORE_X1-PR17-B7_EXCHANGE_complete.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-04-28_2024-05-19/collector_1/ALUMINUM_ORE_X1-YX96-B7_EXCHANGE_complete.tsv'], 'AMMONIA_ICE': ['/home/siebrenf/.local/share/spacepyrates/2024-04-28_2024-05-19/collector_3/AMMONIA_ICE_X1-AY98-H56_EXCHANGE_complete.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-04-28_2024-05-19/collector_3/AMMONIA_ICE_X1-GB78-H51_EXCHANGE_complete.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-04-28_2024-05-19/collector_3/AMMONIA_ICE_X1-GK59-B7_EXCHANGE_complete.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-04-28_2024-05-19/collector_3/AMMONIA_ICE_X1-KK79-B7_EXCHANGE_complete.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-04-28_2024-05-19/collector_3/AMMONIA_ICE_X1-KV59-B7_EXCHANGE_complete.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-04-28_2024-05-19/collector_3/AMMONIA_ICE_X1-NH34-B7_EXCHANGE_complete.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-04-28_2024-05-19/collector_3/AMMONIA_ICE_X1-NT25-B7_EXCHANGE_complete.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-04-28_2024-05-19/collector_1/AMMONIA_ICE_X1-FY38-H61_EXCHANGE_complete.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-04-28_2024-05-19/collector_1/AMMONIA_ICE_X1-HC90-H56_EXCHANGE_complete.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-04-28_2024-05-19/collector_1/AMMONIA_ICE_X1-XG56-H55_EXCHANGE_complete.tsv'], 'ANTIMATTER': ['/home/siebrenf/.local/share/spacepyrates/2024-04-28_2024-05-19/collector_3/ANTIMATTER_X1-NH34-I53_EXCHANGE_complete.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-04-28_2024-05-19/collector_3/ANTIMATTER_X1-NT25-I58_EXCHANGE_complete.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-04-28_2024-05-19/collector_1/ANTIMATTER_X1-FY38-I63_EXCHANGE_complete.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-04-28_2024-05-19/collector_1/ANTIMATTER_X1-PR17-I52_EXCHANGE_complete.tsv'], 'DIAMONDS': ['/home/siebrenf/.local/share/spacepyrates/2024-04-28_2024-05-19/collector_3/DIAMONDS_X1-AY98-B7_EXCHANGE_complete.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-04-28_2024-05-19/collector_3/DIAMONDS_X1-KV59-B7_EXCHANGE_complete.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-04-28_2024-05-19/collector_1/DIAMONDS_X1-FY38-B7_EXCHANGE_complete.tsv'], 'HYDROCARBON': ['/home/siebrenf/.local/share/spacepyrates/2024-04-28_2024-05-19/collector_3/HYDROCARBON_X1-NH34-C39_EXCHANGE_complete.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-04-28_2024-05-19/collector_3/HYDROCARBON_X1-SB17-C44_EXCHANGE_complete.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-04-28_2024-05-19/collector_1/HYDROCARBON_X1-HC90-C45_EXCHANGE_complete.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-04-28_2024-05-19/collector_1/HYDROCARBON_X1-KP20-C39_EXCHANGE_complete.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-04-28_2024-05-19/collector_1/HYDROCARBON_X1-QF3-C41_EXCHANGE_complete.tsv'], 'ICE_WATER': ['/home/siebrenf/.local/share/spacepyrates/2024-04-28_2024-05-19/collector_3/ICE_WATER_X1-HS48-H60_EXCHANGE_complete.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-04-28_2024-05-19/collector_1/ICE_WATER_X1-FY38-B7_EXCHANGE_complete.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-04-28_2024-05-19/collector_1/ICE_WATER_X1-PR17-H50_EXCHANGE_complete.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-04-28_2024-05-19/collector_1/ICE_WATER_X1-VV84-H54_EXCHANGE_complete.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-04-28_2024-05-19/collector_1/ICE_WATER_X1-XG56-H55_EXCHANGE_complete.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-04-28_2024-05-19/collector_1/ICE_WATER_X1-YX96-H59_EXCHANGE_complete.tsv'], 'IRON_ORE': ['/home/siebrenf/.local/share/spacepyrates/2024-04-28_2024-05-19/collector_3/IRON_ORE_X1-AY98-B7_EXCHANGE_complete.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-04-28_2024-05-19/collector_1/IRON_ORE_X1-PR17-B7_EXCHANGE_complete.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-04-28_2024-05-19/collector_1/IRON_ORE_X1-QF3-B7_EXCHANGE_complete.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-04-28_2024-05-19/collector_1/IRON_ORE_X1-XG56-B7_EXCHANGE_complete.tsv'], 'LIQUID_HYDROGEN': ['/home/siebrenf/.local/share/spacepyrates/2024-04-28_2024-05-19/collector_3/LIQUID_HYDROGEN_X1-AY98-C43_EXCHANGE_complete.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-04-28_2024-05-19/collector_3/LIQUID_HYDROGEN_X1-GB78-C38_EXCHANGE_complete.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-04-28_2024-05-19/collector_1/LIQUID_HYDROGEN_X1-QF3-C41_EXCHANGE_complete.tsv'], 'LIQUID_NITROGEN': ['/home/siebrenf/.local/share/spacepyrates/2024-04-28_2024-05-19/collector_3/LIQUID_NITROGEN_X1-GK59-C42_EXCHANGE_complete.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-04-28_2024-05-19/collector_1/LIQUID_NITROGEN_X1-FY38-C48_EXCHANGE_complete.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-04-28_2024-05-19/collector_1/LIQUID_NITROGEN_X1-U25-C42_EXCHANGE_complete.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-04-28_2024-05-19/collector_1/LIQUID_NITROGEN_X1-YP14-C43_EXCHANGE_complete.tsv'], 'MERITIUM_ORE': ['/home/siebrenf/.local/share/spacepyrates/2024-04-28_2024-05-19/collector_3/MERITIUM_ORE_X1-NT25-B7_EXCHANGE_complete.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-04-28_2024-05-19/collector_1/MERITIUM_ORE_X1-SX11-B7_EXCHANGE_complete.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-04-28_2024-05-19/collector_1/MERITIUM_ORE_X1-YX96-B7_EXCHANGE_complete.tsv'], 'PRECIOUS_STONES': ['/home/siebrenf/.local/share/spacepyrates/2024-04-28_2024-05-19/collector_3/PRECIOUS_STONES_X1-HS48-B7_EXCHANGE_complete.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-04-28_2024-05-19/collector_3/PRECIOUS_STONES_X1-KV59-B7_EXCHANGE_complete.tsv'], 'QUARTZ_SAND': ['/home/siebrenf/.local/share/spacepyrates/2024-04-28_2024-05-19/collector_3/QUARTZ_SAND_X1-AY98-B7_EXCHANGE_complete.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-04-28_2024-05-19/collector_3/QUARTZ_SAND_X1-DF64-H54_EXCHANGE_complete.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-04-28_2024-05-19/collector_3/QUARTZ_SAND_X1-GK59-B7_EXCHANGE_complete.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-04-28_2024-05-19/collector_3/QUARTZ_SAND_X1-HS48-H60_EXCHANGE_complete.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-04-28_2024-05-19/collector_3/QUARTZ_SAND_X1-KV59-B7_EXCHANGE_complete.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-04-28_2024-05-19/collector_1/QUARTZ_SAND_X1-PR17-H50_EXCHANGE_complete.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-04-28_2024-05-19/collector_1/QUARTZ_SAND_X1-XG56-H55_EXCHANGE_complete.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-04-28_2024-05-19/collector_1/QUARTZ_SAND_X1-YP14-H57_EXCHANGE_complete.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-04-28_2024-05-19/collector_1/QUARTZ_SAND_X1-YX96-B7_EXCHANGE_complete.tsv'], 'SILICON_CRYSTALS': ['/home/siebrenf/.local/share/spacepyrates/2024-04-28_2024-05-19/collector_3/SILICON_CRYSTALS_X1-GK59-B7_EXCHANGE_complete.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-04-28_2024-05-19/collector_3/SILICON_CRYSTALS_X1-SB17-H57_EXCHANGE_complete.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-04-28_2024-05-19/collector_1/SILICON_CRYSTALS_X1-FY38-B7_EXCHANGE_complete.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-04-28_2024-05-19/collector_1/SILICON_CRYSTALS_X1-HC90-B7_EXCHANGE_complete.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-04-28_2024-05-19/collector_1/SILICON_CRYSTALS_X1-KP20-B7_EXCHANGE_complete.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-04-28_2024-05-19/collector_1/SILICON_CRYSTALS_X1-PR17-H50_EXCHANGE_complete.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-04-28_2024-05-19/collector_1/SILICON_CRYSTALS_X1-XG56-H55_EXCHANGE_complete.tsv'], 'URANITE_ORE': ['/home/siebrenf/.local/share/spacepyrates/2024-04-28_2024-05-19/collector_3/URANITE_ORE_X1-DF64-B7_EXCHANGE_complete.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-04-28_2024-05-19/collector_1/URANITE_ORE_X1-HC90-B7_EXCHANGE_complete.tsv'], 'COPPER_ORE': ['/home/siebrenf/.local/share/spacepyrates/2024-04-28_2024-05-19/collector_1/COPPER_ORE_X1-HC90-B7_EXCHANGE_complete.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-04-28_2024-05-19/collector_1/COPPER_ORE_X1-YP14-B7_EXCHANGE_complete.tsv']}
#
# pd.set_option('display.max_columns', None)
# pd.set_option('display.max_rows', None)
# for good, fnames in files_per_port_per_good["EXCHANGE"].items():
#
#     for fname in fnames:
#         df = pd.read_table(fname)
#         print(good, "tv=", df.at[0, "tradeVolume"], fname)
#         print(df[["supply", "purchasePrice", "sellPrice", "units", "action"]])
#         print()
#         # break
#     break
