import os

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.optimize import curve_fit
from sklearn.metrics import r2_score

plt.rcParams["font.family"] = "monospace"
baseprices = {
    "SHIP_PARTS": 5400,
    "SHIP_PLATING": 5200,
}
s2c = {
    "SCARCE": "red",
    "LIMITED": "orange",
    "MODERATE": "grey",
    "HIGH": "lightblue",
    "ABUNDANT": "blue",
}
# # merge all files per good
# files_per_port_per_good = {
#     "EXPORT": {},
#     "IMPORT": {},
#     "EXCHANGE": {},
# }
# for version, folder in itertools.product(
#     ["2024-04-28_2024-05-19"], ["collector_import"]
# ):
#     basedir = f"/home/siebrenf/.local/share/spacepyrates/{version}/{folder}"
#     if not os.path.exists(basedir):
#         continue
#     for f in sorted(os.listdir(basedir)):
#         if str(f).startswith((".", "~")):
#             continue
#         if not f.endswith("_complete.tsv"):
#             continue
#         fname = os.path.join(basedir, f)
#         good, wp, port, _ = f.rsplit("_", 3)
#         files_per_port_per_good[port].setdefault(good, []).append(fname)

optimal_goods = {
    "SHIP_PARTS": [
        "/home/siebrenf/.local/share/spacepyrates/2024-04-28_2024-05-19/collector_import/SHIP_PARTS_X1-AY98-A2_IMPORT_complete.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-04-28_2024-05-19/collector_import/SHIP_PARTS_X1-AY98-H55_IMPORT_complete.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-04-28_2024-05-19/collector_import/SHIP_PARTS_X1-DF64-H53_IMPORT_complete.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-04-28_2024-05-19/collector_import/SHIP_PARTS_X1-GB78-H50_IMPORT_complete.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-04-28_2024-05-19/collector_import/SHIP_PARTS_X1-GK59-H53_IMPORT_complete.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-04-28_2024-05-19/collector_import/SHIP_PARTS_X1-HS48-A2_IMPORT_complete.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-04-28_2024-05-19/collector_import/SHIP_PARTS_X1-KK79-H57_IMPORT_complete.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-04-28_2024-05-19/collector_import/SHIP_PARTS_X1-KV59-H48_IMPORT_complete.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-04-28_2024-05-19/collector_import/SHIP_PARTS_X1-NH34-H50_IMPORT_complete.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-04-28_2024-05-19/collector_import/SHIP_PARTS_X1-NT25-H55_IMPORT_complete.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-04-28_2024-05-19/collector_import/SHIP_PARTS_X1-SB17-H56_IMPORT_complete.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-04-28_2024-05-19/collector_import/SHIP_PARTS_X1-TD63-H52_IMPORT_complete.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-04-28_2024-05-19/collector_import/SHIP_PARTS_X1-VJ98-A2_IMPORT_complete.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-04-28_2024-05-19/collector_import/SHIP_PARTS_X1-VK47-H53_IMPORT_complete.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-04-28_2024-05-19/collector_import/SHIP_PARTS_X1-YT74-H55_IMPORT_complete.tsv",
    ],
    "SHIP_PLATING": [
        "/home/siebrenf/.local/share/spacepyrates/2024-04-28_2024-05-19/collector_import/SHIP_PLATING_X1-AY98-H55_IMPORT_complete.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-04-28_2024-05-19/collector_import/SHIP_PLATING_X1-DF64-H53_IMPORT_complete.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-04-28_2024-05-19/collector_import/SHIP_PLATING_X1-GB78-H50_IMPORT_complete.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-04-28_2024-05-19/collector_import/SHIP_PLATING_X1-GK59-H53_IMPORT_complete.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-04-28_2024-05-19/collector_import/SHIP_PLATING_X1-HS48-A2_IMPORT_complete.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-04-28_2024-05-19/collector_import/SHIP_PLATING_X1-KK79-H57_IMPORT_complete.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-04-28_2024-05-19/collector_import/SHIP_PLATING_X1-KV59-H48_IMPORT_complete.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-04-28_2024-05-19/collector_import/SHIP_PLATING_X1-NH34-H50_IMPORT_complete.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-04-28_2024-05-19/collector_import/SHIP_PLATING_X1-NT25-H55_IMPORT_complete.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-04-28_2024-05-19/collector_import/SHIP_PLATING_X1-SB17-H56_IMPORT_complete.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-04-28_2024-05-19/collector_import/SHIP_PLATING_X1-TD63-H52_IMPORT_complete.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-04-28_2024-05-19/collector_import/SHIP_PLATING_X1-VJ98-A2_IMPORT_complete.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-04-28_2024-05-19/collector_import/SHIP_PLATING_X1-VK47-H53_IMPORT_complete.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-04-28_2024-05-19/collector_import/SHIP_PLATING_X1-YT74-H55_IMPORT_complete.tsv",
    ],
}

blacklist = [
    "SHIP_PARTS_X1-KK79-H57_IMPORT_complete.tsv",  # contaminated
]
div_by_bp = True
for good, fnames in optimal_goods.items():
    if good not in baseprices:
        continue

    fig = plt.figure(figsize=(15, 10))
    ax = fig.add_subplot(111)

    y_bp = baseprices[good]
    y_lims = [float("inf"), -float("inf")]
    for fname in fnames:
        if os.path.basename(fname) in blacklist:
            continue
        _, wp, port, _ = os.path.basename(fname).rsplit("_", 3)
        df = pd.read_table(fname)
        df = df[df["action"] == "sell"].reset_index()
        tv = df.at[0, "tradeVolume"]
        units = df.at[0, "units"]
        assert units == 1
        assert port == "IMPORT"
        # which method was used to generate this file?
        if len(df["supply"].unique()) != 5:
            print("contaminated: n supplies =", len(df["supply"].unique()), fname)
            continue  # contaminated!

        idx_min = df[df["supply"] == "HIGH"].index[0] - 1 * tv
        idx_max = idx_min + 1
        y_max = df.at[idx_min, "sellPrice"]  # note: min idx = max sell price
        y_min = df.at[idx_max, "sellPrice"]
        dy = (y_max - y_min) / 1  # slope
        # y_bp = y_min + dy*dx
        dx = (y_bp - y_min) / dy
        if dx > 1 or dx < 0:
            print("bad dx:", dx)
        idx_origin = idx_max - dx
        ax.axvline((idx_min - idx_origin) * units / tv, zorder=-5, color="pink")
        ax.axvline((idx_max - idx_origin) * units / tv, zorder=-5, color="purple")

        if div_by_bp:
            y = [i / y_bp for i in df["sellPrice"].to_list()]
            ax.axhline(y_min / y_bp, zorder=-5, color="pink")  # highest
            ax.axhline(y_max / y_bp, zorder=-5, color="purple")  # lowest
        else:
            y = df["sellPrice"].to_list()
            ax.axhline(y_min, zorder=-5, color="pink")  # highest
            ax.axhline(y_max, zorder=-5, color="purple")  # lowest

        x = []
        for i in range(len(df)):
            x.append((i - idx_origin) * units / tv)
        c = [s2c[supply] for supply in df["supply"]]
        # remove the lowest value (in case we reached the minimum price)
        y_min = min(y)
        while y_min in y:
            i = y.index(y_min)
            c.pop(i)
            x.pop(i)
            y.pop(i)

        ax.scatter(x, y, c=c, zorder=-1, s=18)
        ax.plot(x, y, zorder=-2, alpha=0.4, c="red", label=f"tv={int(tv)}")

        infer = True
        if infer:

            if div_by_bp:

                def func(x, a):
                    return 1 * (-a * 2 ** (0.3 * x) + a + 1)

            else:

                def func(x, a):
                    return y_bp * (-a * 2 ** (0.3 * x) + a + 1)

            popt, pcov = curve_fit(func, x, y, p0=[0.35], bounds=((0, 1)))  # noqa
            a = popt[0]
            y2 = func(np.array(x), a)
            r_squared = r2_score(y, y2)
            ax.plot(
                x,
                y2,
                ls="--",
                zorder=2,
                alpha=0.5,
                label=f"{a=:.02f}  r^2={round(r_squared, 4)}",
            )

        # for plotting only
        x_lims = [i for i in x if 5.5 >= i >= -7.5]
        y0 = y[x.index(max(x_lims))]
        if y0 < y_lims[0]:
            y_lims[0] = y0
        y1 = y[x.index(min(x_lims))]
        if y1 > y_lims[1]:
            y_lims[1] = y1

    plt.title(f"{good} bp={y_bp}")
    ax.axhline(y_bp, zorder=-15)
    ax.axvline(-5, zorder=-5)
    ax.axvline(-3, zorder=-5)
    ax.axvline(1, zorder=-5)
    ax.axvline(3, zorder=-5)
    ax.set_xlim(-7.5, 5.5)
    ax.set_ylim(y_lims[0] * 0.95, y_lims[1] * 1.05)
    plt.grid(which="major")
    # https://stackoverflow.com/questions/4700614/how-to-put-the-legend-outside-the-plot
    handles, labels = ax.get_legend_handles_labels()
    # sort both labels and handles by labels
    if handles:
        labels, handles = zip(*sorted(zip(labels, handles), key=lambda t: t[0]))
        ax.legend(handles, labels, loc="center left", bbox_to_anchor=(1, 0.5))
        plt.subplots_adjust(right=0.7)
    plt.show()
