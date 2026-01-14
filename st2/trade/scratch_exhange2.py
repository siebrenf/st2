import os

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.optimize import curve_fit
from sklearn.metrics import r2_score

from st2.trade.base_prices import BASE_PRICES as baseprices

x2 = np.linspace(-6, 5, 240)
s2c = {
    "SCARCE": "red",
    "LIMITED": "orange",
    "MODERATE": "grey",
    "HIGH": "lightblue",
    "ABUNDANT": "blue",
}
# g2fs = {}
# for version in ["2024-03-24_2024-04-07", "2024-04-09_2024-04-28"]:
#     basebasedir = os.path.expanduser(f"~/.local/share/spacepyrates/{version}")
#     for subdir in ["market_inflation", "market_sales"]:
#         basedir = os.path.join(basebasedir, subdir)
#         if not os.path.exists(basedir):
#             # print(f"Skipping {basedir}")
#             continue
#         for f in sorted(os.listdir(basedir)):
#             if not f.endswith("_complete.tsv") and "EXCHANGE" not in f:
#                 if "complete" in f:
#                     print(f"Skipping {f}")
#                 continue
#             good = f.rsplit("_", 2)[0]
#             fname = os.path.join(basedir, f)
#             if good not in g2fs:
#                 g2fs[good] = []
#             g2fs[good].append(fname)
# g2fs = {'ALUMINUM_ORE': ['/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/ALUMINUM_ORE_X1-B9-B7_EXCHANGE.tsv'], 'AMMONIA_ICE': ['/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/AMMONIA_ICE_X1-AY66-B7_EXCHANGE.tsv'], 'ANTIMATTER': ['/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/ANTIMATTER_X1-AC33-I54_EXCHANGE.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/ANTIMATTER_X1-AF2-I54_EXCHANGE.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/ANTIMATTER_X1-CQ34-I53_EXCHANGE.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/ANTIMATTER_X1-CQ37-I62_EXCHANGE.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/ANTIMATTER_X1-DH53-I61_EXCHANGE.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/ANTIMATTER_X1-GA57-I59_EXCHANGE.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/ANTIMATTER_X1-GC34-I57_EXCHANGE.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/ANTIMATTER_X1-HP80-I51_EXCHANGE.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/ANTIMATTER_X1-HT80-I63_EXCHANGE.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/ANTIMATTER_X1-P17-I55_EXCHANGE.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/ANTIMATTER_X1-TU33-I55_EXCHANGE.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/ANTIMATTER_X1-YT60-I54_EXCHANGE.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-04-09_2024-04-28/market_sales/ANTIMATTER_X1-BT63-I54_complete.tsv'], 'DIAMONDS': ['/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/DIAMONDS_X1-YC19-B7_EXCHANGE.tsv'], 'FUEL': ['/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/FUEL_X1-B9-A1_EXCHANGE.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/FUEL_X1-BF17-A1_EXCHANGE.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/FUEL_X1-BG6-A1_EXCHANGE.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/FUEL_X1-BN46-A1_EXCHANGE.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/FUEL_X1-BS93-A1_EXCHANGE.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/FUEL_X1-CA87-A1_EXCHANGE.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/FUEL_X1-CZ47-A1_EXCHANGE.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/FUEL_X1-DC55-A1_EXCHANGE.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/FUEL_X1-DP42-A1_EXCHANGE.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/FUEL_X1-DP43-A1_EXCHANGE.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/FUEL_X1-NM62-A1_EXCHANGE.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/FUEL_X1-VM19-A1_EXCHANGE.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/FUEL_X1-XK91-A1_EXCHANGE.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/FUEL_X1-YQ68-A1_EXCHANGE.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/FUEL_X1-ZU9-A1_EXCHANGE.tsv'], 'HYDROCARBON': ['/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/HYDROCARBON_X1-QS18-C37_EXCHANGE.tsv'], 'ICE_WATER': ['/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/ICE_WATER_X1-AC33-H52_EXCHANGE.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/ICE_WATER_X1-AF2-H52_EXCHANGE.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/ICE_WATER_X1-B9-H56_EXCHANGE.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/ICE_WATER_X1-BG6-H51_EXCHANGE.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/ICE_WATER_X1-BN46-H58_EXCHANGE.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/ICE_WATER_X1-BR33-H57_EXCHANGE.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/ICE_WATER_X1-BS45-H50_EXCHANGE.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/ICE_WATER_X1-CQ34-H51_EXCHANGE.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/ICE_WATER_X1-CQ37-B7_EXCHANGE.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/ICE_WATER_X1-CZ47-H50_EXCHANGE.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/ICE_WATER_X1-D57-H56_EXCHANGE.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/ICE_WATER_X1-DB40-H52_EXCHANGE.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/ICE_WATER_X1-DC55-H48_EXCHANGE.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/ICE_WATER_X1-DP42-H55_EXCHANGE.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/ICE_WATER_X1-DR64-H53_EXCHANGE.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/ICE_WATER_X1-JK24-H65_EXCHANGE.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/ICE_WATER_X1-JS3-H50_EXCHANGE.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/ICE_WATER_X1-KH23-H50_EXCHANGE.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/ICE_WATER_X1-NM62-H61_EXCHANGE.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/ICE_WATER_X1-QR29-H60_EXCHANGE.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/ICE_WATER_X1-RU7-H60_EXCHANGE.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/ICE_WATER_X1-TZ46-H54_EXCHANGE.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/ICE_WATER_X1-UG84-H54_EXCHANGE.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/ICE_WATER_X1-VV38-H56_EXCHANGE.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/ICE_WATER_X1-XG58-H56_EXCHANGE.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/ICE_WATER_X1-YH11-H57_EXCHANGE.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/ICE_WATER_X1-YQ68-H49_EXCHANGE.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-04-09_2024-04-28/market_inflation/ICE_WATER_X1-CB25-H49_EXCHANGE.tsv'], 'LIQUID_HYDROGEN': ['/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/LIQUID_HYDROGEN_X1-QS18-C37_EXCHANGE.tsv'], 'LIQUID_NITROGEN': ['/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/LIQUID_NITROGEN_X1-FQ15-C41_EXCHANGE.tsv'], 'MERITIUM_ORE': ['/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/MERITIUM_ORE_X1-BR63-B7_EXCHANGE.tsv'], 'QUARTZ_SAND': ['/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/QUARTZ_SAND_X1-AV7-H52_EXCHANGE.tsv'], 'SILICON_CRYSTALS': ['/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/SILICON_CRYSTALS_X1-BN38-B7_EXCHANGE.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-04-09_2024-04-28/market_inflation/SILICON_CRYSTALS_X1-DB37-B7_EXCHANGE.tsv'], 'URANITE_ORE': ['/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/URANITE_ORE_X1-FQ15-B7_EXCHANGE.tsv'], 'ADVANCED_CIRCUITRY': ['/home/siebrenf/.local/share/spacepyrates/2024-04-09_2024-04-28/market_sales/ADVANCED_CIRCUITRY_X1-BT63-D44_complete.tsv', '/home/siebrenf/.local/share/spacepyrates/2024-04-09_2024-04-28/market_sales/ADVANCED_CIRCUITRY_X1-DB41-D43_complete.tsv'], 'AMMUNITION': ['/home/siebrenf/.local/share/spacepyrates/2024-04-09_2024-04-28/market_sales/AMMUNITION_X1-BT63-F47_complete.tsv'], 'ASSAULT_RIFLES': ['/home/siebrenf/.local/share/spacepyrates/2024-04-09_2024-04-28/market_sales/ASSAULT_RIFLES_X1-FX85-E49_complete.tsv'], 'BIOCOMPOSITES': ['/home/siebrenf/.local/share/spacepyrates/2024-04-09_2024-04-28/market_sales/BIOCOMPOSITES_X1-BT63-K82_complete.tsv'], 'CYBER_IMPLANTS': ['/home/siebrenf/.local/share/spacepyrates/2024-04-09_2024-04-28/market_sales/CYBER_IMPLANTS_X1-DB41-A4_complete.tsv'], 'DRUGS': ['/home/siebrenf/.local/share/spacepyrates/2024-04-09_2024-04-28/market_sales/DRUGS_X1-FX85-J64_complete.tsv'], 'ELECTRONICS': ['/home/siebrenf/.local/share/spacepyrates/2024-04-09_2024-04-28/market_sales/ELECTRONICS_X1-FX85-F53_complete.tsv'], 'EQUIPMENT': ['/home/siebrenf/.local/share/spacepyrates/2024-04-09_2024-04-28/market_sales/EQUIPMENT_X1-BT63-K82_complete.tsv'], 'EXPLOSIVES': ['/home/siebrenf/.local/share/spacepyrates/2024-04-09_2024-04-28/market_sales/EXPLOSIVES_X1-BT63-F47_complete.tsv'], 'FABRICS': ['/home/siebrenf/.local/share/spacepyrates/2024-04-09_2024-04-28/market_sales/FABRICS_X1-FX85-E50_complete.tsv'], 'FAB_MATS': ['/home/siebrenf/.local/share/spacepyrates/2024-04-09_2024-04-28/market_sales/FAB_MATS_X1-BT63-F48_complete.tsv'], 'FIREARMS': ['/home/siebrenf/.local/share/spacepyrates/2024-04-09_2024-04-28/market_sales/FIREARMS_X1-DB41-E44_complete.tsv'], 'IRON_ORE': ['/home/siebrenf/.local/share/spacepyrates/2024-04-09_2024-04-28/market_sales/IRON_ORE_X1-FX85-J64_complete.tsv'], 'JEWELRY': ['/home/siebrenf/.local/share/spacepyrates/2024-04-09_2024-04-28/market_sales/JEWELRY_X1-FX85-H60_complete.tsv'], 'LAB_INSTRUMENTS': ['/home/siebrenf/.local/share/spacepyrates/2024-04-09_2024-04-28/market_sales/LAB_INSTRUMENTS_X1-DB41-C40_complete.tsv'], 'MACHINERY': ['/home/siebrenf/.local/share/spacepyrates/2024-04-09_2024-04-28/market_sales/MACHINERY_X1-FX85-E50_complete.tsv'], 'MEDICINE': ['/home/siebrenf/.local/share/spacepyrates/2024-04-09_2024-04-28/market_sales/MEDICINE_X1-FX85-D47_complete.tsv'], 'MICROPROCESSORS': ['/home/siebrenf/.local/share/spacepyrates/2024-04-09_2024-04-28/market_sales/MICROPROCESSORS_X1-FX85-A3_complete.tsv'], 'NANOBOTS': ['/home/siebrenf/.local/share/spacepyrates/2024-04-09_2024-04-28/market_sales/NANOBOTS_X1-VF28-A4_complete.tsv'], 'NEURAL_CHIPS': ['/home/siebrenf/.local/share/spacepyrates/2024-04-09_2024-04-28/market_sales/NEURAL_CHIPS_X1-FX85-A4_complete.tsv'], 'POLYNUCLEOTIDES': ['/home/siebrenf/.local/share/spacepyrates/2024-04-09_2024-04-28/market_sales/POLYNUCLEOTIDES_X1-FX85-E50_complete.tsv'], 'SHIP_PARTS': ['/home/siebrenf/.local/share/spacepyrates/2024-04-09_2024-04-28/market_sales/SHIP_PARTS_X1-FX85-D47_complete.tsv'], 'SHIP_PLATING': ['/home/siebrenf/.local/share/spacepyrates/2024-04-09_2024-04-28/market_sales/SHIP_PLATING_X1-BT63-D44_complete.tsv'], 'SUPERGRAINS': ['/home/siebrenf/.local/share/spacepyrates/2024-04-09_2024-04-28/market_sales/SUPERGRAINS_X1-BT63-A4_complete.tsv']}
# g2fs2 = {}
# for good, fnames in g2fs.items():
#     y_bp = baseprices[good]
#     if y_bp < 100:
#         continue
#     for fname in fnames:
#         df = pd.read_table(fname)
#         if len(df[df["units"] == 1]) == 0:
#             continue
#         if "action" in df.columns:
#             df = df[df["action"] == "buy"].reset_index()
#         port = df.at[0, "type"]
#         if port != "EXCHANGE":
#             continue
#         if "MODERATE" not in df["supply"].unique():
#             continue
#         if good not in g2fs2:
#             g2fs2[good] = []
#         g2fs2[good].append(fname)
g2fs2 = {
    "ANTIMATTER": [
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/ANTIMATTER_X1-AF2-I54_EXCHANGE.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/ANTIMATTER_X1-CQ34-I53_EXCHANGE.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/ANTIMATTER_X1-CQ37-I62_EXCHANGE.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/ANTIMATTER_X1-DH53-I61_EXCHANGE.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/ANTIMATTER_X1-GC34-I57_EXCHANGE.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/ANTIMATTER_X1-HP80-I51_EXCHANGE.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/ANTIMATTER_X1-P17-I55_EXCHANGE.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/ANTIMATTER_X1-YT60-I54_EXCHANGE.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-04-09_2024-04-28/market_sales/ANTIMATTER_X1-BT63-I54_complete.tsv",
    ],
    "MERITIUM_ORE": [
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/MERITIUM_ORE_X1-BR63-B7_EXCHANGE.tsv"
    ],
    "URANITE_ORE": [
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/URANITE_ORE_X1-FQ15-B7_EXCHANGE.tsv"
    ],
}
for good, fnames in g2fs2.items():
    fig = plt.figure(figsize=(15, 10))
    ax = fig.add_subplot(111)

    y_bp = baseprices[good]
    for fname in fnames:
        df = pd.read_table(fname)
        wp = fname.split("_")[-2][3:]
        # df.at[0, "supply"] = "SCARCE", df.at[-1, "supply"] = "ABUNDANT"
        df = df[df["units"] == 1].iloc[::-1].reset_index()
        if "action" in df.columns:
            df = df[df["action"] == "buy"].reset_index()
        port = df.at[0, "type"]
        tv = int(df.at[0, "tradeVolume"])
        units = df.at[0, "units"]

        # i_high_0 = i_high_1 = None
        # if "HIGH" in df["supply"].unique():
        #     i_high_0 = df[df["supply"] == "HIGH"].index[0]
        #     i_high_1 = df[df["supply"] == "HIGH"].index[-1]
        # else:
        #     continue
        #     # print("HIGH", i_high_0, i_high_1)
        # i_mod_0 = df[df["supply"] == "MODERATE"].index[0]
        # i_mod_1 = df[df["supply"] == "MODERATE"].index[-1]
        # # print("MOD", i_mod_0, i_mod_1)
        # i_lim_0 = i_lim_1 = None
        # if "LIMITED" in df["supply"].unique():
        #     i_lim_0 = df[df["supply"] == "LIMITED"].index[0]
        #     i_lim_1 = df[df["supply"] == "LIMITED"].index[-1]
        # else:
        #     continue
        # #     print("LIM", i_lim_0, i_lim_1)
        # # print()

        origin = df[df["supply"] == "MODERATE"].index[0] + 2 * tv / units
        yp = df["purchasePrice"].to_list()
        ys = df["sellPrice"].to_list()
        x = []
        for i in range(len(df)):
            x.append((i - origin) * (units / tv))
        c = [s2c[supply] for supply in df["supply"]]
        # y_min = min(yp)
        # while y_min in yp:
        #     i = yp.index(y_min)
        #     c.pop(i)
        #     yp.pop(i)
        #     ys.pop(i)
        #     x.pop(i)
        # y_min = min(ys)
        # while y_min in ys:
        #     i = ys.index(y_min)
        #     c.pop(i)
        #     yp.pop(i)
        #     ys.pop(i)
        #     x.pop(i)
        ax.scatter(x, yp, c=c, zorder=-1, s=18, alpha=0.25)
        ax.plot(x, yp, zorder=-2, c="green", label="purchase")
        ax.axhline(y_bp, zorder=-15)
        ax.scatter(x, ys, c=c, zorder=-1, s=18, alpha=0.25)
        ax.plot(x, ys, zorder=-2, c="red", label="sell")

        infer = True
        if infer:
            # def func_purchase(x, a, b):
            #     return y_bp * (-a / 1000 * (x-1)**3 - b/100*x**2 + 1) + max(2, round(y_bp/100))

            # def func_purchase(x, a, b):
            #     return y_bp * (-a / 1000 * (x-1)**3 + b/100*x + 1) + max(2, round(y_bp/100))

            def func_purchase(x, a, dx=0):
                x = x - 1 + dx
                # return y_bp * (-a / 1000 * x ** 3 - b / 1000 * x**2 - c / 1000 * x + 1) + max(2, round(y_bp / 100))
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
                label=f"{a=:.02f} {dx=} r^2={round(r_squared, 4)} {wp=}",
            )

            # def func_sell(x, a):
            #     return y_bp * (-a / 1000 * (x+1)**3 + 1) - max(2, round(y_bp/100))

            def func_sell(x, a, dx=0):
                x = x + 1 + dx
                # return y_bp * (-a / 1000 * x ** 3 - b / 1000 * x**2 - c / 1000 * x + 1) - max(2, round(y_bp / 100))
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
                label=f"{a=:.02f} {dx=} r^2={round(r_squared, 4)} {wp=}",
            )

    plt.title(f"{good} bp={y_bp}")
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
