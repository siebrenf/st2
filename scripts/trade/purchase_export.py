import os

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.optimize import curve_fit
from sklearn.metrics import r2_score


def process_df(fname):
    df = pd.read_table(fname)
    columns = {
        "symbol",
        "tradeVolume",
        "type",
        "supply",
        "purchasePrice",
        "sellPrice",
        "units",
    }
    if len(set(df.columns) & columns) != 7:
        return df, None

    # only plot data with equal step size
    if len(df["units"].unique()) > 1:
        df = df[df["units"] == df["units"].min()].reset_index()

    # only plot data with minimal step size
    units = df.at[0, "units"]
    if units != 1:
        return df, None

    # only plot data with MODERATE observations
    df2 = df[df["supply"] == "MODERATE"]
    if len(df2) == 0:
        return df, None

    tv = df.at[0, "tradeVolume"]
    if len(df["tradeVolume"].unique()) != 1:
        print(f'{fname=} has more than 1 tv: {df["tradeVolume"].unique()}')
    _type = df.at[0, "type"]
    # only plot complete MODERATE observations
    if len(df2) != 4 * tv / units:
        return df, None

    # only plot complete observations
    s = df["supply"].to_list()
    first_supply = s[0]
    last_supply = s[-1]
    for supply in df["supply"].unique():
        if supply in [first_supply, last_supply]:
            continue
        df2 = df[df["supply"] == supply]
        n = len(df2)
        u = round(n * units / tv, 3)
        if supply == "MODERATE" and u != 4:
            return df, None
        elif supply in ["LIMITED", "HIGH"] and u != 2:
            return df, None

    return df, (units, tv, _type)


# versions = ["2024-04-09_2024-04-28", "2024-03-24_2024-04-07"]
# optimal_goods = {}
# for version in versions:
#     basedir = f"/home/siebrenf/.local/share/spacepyrates/{version}/market_inflation"
#     if not os.path.exists(basedir):
#         continue
#     for f in sorted(os.listdir(basedir)):
#         if f.startswith("."):
#             continue
#         fname = os.path.join(basedir, f)
#         df, keep = process_df(fname)
#         if keep:
#             units, tv, port = keep
#         else:
#             continue
#
#         # visualize specific ports
#         if port != "EXPORT":
#             continue
#
#         good = f.rsplit("_", 2)[0]
#         if good not in optimal_goods:
#             optimal_goods[good] = []
#         optimal_goods[good].append(fname)


optimal_goods = {
    "ADVANCED_CIRCUITRY": [
        "/home/siebrenf/.local/share/spacepyrates/2024-04-09_2024-04-28/market_inflation/ADVANCED_CIRCUITRY_X1-CB25-D39_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-04-09_2024-04-28/market_inflation/ADVANCED_CIRCUITRY_X1-FX85-D48_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/ADVANCED_CIRCUITRY_X1-AY66-D49_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/ADVANCED_CIRCUITRY_X1-B9-D47_EXPORT.tsv",
    ],
    "ALUMINUM_ORE": [
        "/home/siebrenf/.local/share/spacepyrates/2024-04-09_2024-04-28/market_inflation/ALUMINUM_ORE_X1-BZ96-J61_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/ALUMINUM_ORE_X1-AY66-J63_EXPORT.tsv",
    ],
    "AMMUNITION": [
        "/home/siebrenf/.local/share/spacepyrates/2024-04-09_2024-04-28/market_inflation/AMMUNITION_X1-CB25-F44_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-04-09_2024-04-28/market_inflation/AMMUNITION_X1-FX85-F52_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/AMMUNITION_X1-AC33-F47_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/AMMUNITION_X1-AF2-F47_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/AMMUNITION_X1-CQ34-F46_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/AMMUNITION_X1-CQ37-F54_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/AMMUNITION_X1-DH53-F53_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/AMMUNITION_X1-GA57-F51_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/AMMUNITION_X1-HP80-F44_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/AMMUNITION_X1-TU33-F45_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/AMMUNITION_X1-VZ39-F50_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/AMMUNITION_X1-YT60-F46_EXPORT.tsv",
    ],
    "BIOCOMPOSITES": [
        "/home/siebrenf/.local/share/spacepyrates/2024-04-09_2024-04-28/market_inflation/BIOCOMPOSITES_X1-DB41-K77_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-04-09_2024-04-28/market_inflation/BIOCOMPOSITES_X1-FX85-K90_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-04-09_2024-04-28/market_inflation/BIOCOMPOSITES_X1-KB66-K78_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/BIOCOMPOSITES_X1-AY66-K97_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/BIOCOMPOSITES_X1-B9-K87_EXPORT.tsv",
    ],
    "CLOTHING": [
        "/home/siebrenf/.local/share/spacepyrates/2024-04-09_2024-04-28/market_inflation/CLOTHING_X1-BT63-K82_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-04-09_2024-04-28/market_inflation/CLOTHING_X1-FX85-K90_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/CLOTHING_X1-AY66-K97_EXPORT.tsv",
    ],
    "COPPER_ORE": [
        "/home/siebrenf/.local/share/spacepyrates/2024-04-09_2024-04-28/market_inflation/COPPER_ORE_X1-DB37-J59_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/COPPER_ORE_X1-AY66-J63_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/COPPER_ORE_X1-B9-J61_EXPORT.tsv",
    ],
    "COPPER": [
        "/home/siebrenf/.local/share/spacepyrates/2024-04-09_2024-04-28/market_inflation/COPPER_X1-CB25-H47_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/COPPER_X1-AY66-H56_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/COPPER_X1-B9-H54_EXPORT.tsv",
    ],
    "CYBER_IMPLANTS": [
        "/home/siebrenf/.local/share/spacepyrates/2024-04-09_2024-04-28/market_inflation/CYBER_IMPLANTS_X1-DB41-A4_EXPORT.tsv"
    ],
    "EQUIPMENT": [
        "/home/siebrenf/.local/share/spacepyrates/2024-04-09_2024-04-28/market_inflation/EQUIPMENT_X1-DB37-K87_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/EQUIPMENT_X1-AY66-K97_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/EQUIPMENT_X1-B9-K87_EXPORT.tsv",
    ],
    "FAB_MATS": [
        "/home/siebrenf/.local/share/spacepyrates/2024-04-09_2024-04-28/market_inflation/FAB_MATS_X1-DB41-F48_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/FAB_MATS_X1-AY66-F54_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/FAB_MATS_X1-B9-F52_EXPORT.tsv",
    ],
    "FOOD": [
        "/home/siebrenf/.local/share/spacepyrates/2024-04-09_2024-04-28/market_inflation/FOOD_X1-FX85-K90_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/FOOD_X1-AY66-K97_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/FOOD_X1-B9-K87_EXPORT.tsv",
    ],
    "GENE_THERAPEUTICS": [
        "/home/siebrenf/.local/share/spacepyrates/2024-04-09_2024-04-28/market_inflation/GENE_THERAPEUTICS_X1-KB66-A4_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/GENE_THERAPEUTICS_X1-YK51-A4_EXPORT.tsv",
    ],
    "GOLD": [
        "/home/siebrenf/.local/share/spacepyrates/2024-04-09_2024-04-28/market_inflation/GOLD_X1-BT63-B7_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-04-09_2024-04-28/market_inflation/GOLD_X1-DB37-B7_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-04-09_2024-04-28/market_inflation/GOLD_X1-FX85-B7_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/GOLD_X1-AC33-B7_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/GOLD_X1-AF2-B7_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/GOLD_X1-CQ34-B7_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/GOLD_X1-DH53-B7_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/GOLD_X1-GA57-B7_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/GOLD_X1-GC34-B7_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/GOLD_X1-HP80-B7_EXPORT.tsv",
    ],
    "IRON_ORE": [
        "/home/siebrenf/.local/share/spacepyrates/2024-04-09_2024-04-28/market_inflation/IRON_ORE_X1-BT63-J57_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-04-09_2024-04-28/market_inflation/IRON_ORE_X1-BZ96-J61_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/IRON_ORE_X1-AY66-J63_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/IRON_ORE_X1-B9-J61_EXPORT.tsv",
    ],
    "LAB_INSTRUMENTS": [
        "/home/siebrenf/.local/share/spacepyrates/2024-04-09_2024-04-28/market_inflation/LAB_INSTRUMENTS_X1-DB41-C40_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/LAB_INSTRUMENTS_X1-AY66-C46_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/LAB_INSTRUMENTS_X1-B9-C44_EXPORT.tsv",
    ],
    "MEDICINE": [
        "/home/siebrenf/.local/share/spacepyrates/2024-04-09_2024-04-28/market_inflation/MEDICINE_X1-BZ96-D42_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/MEDICINE_X1-AY66-D48_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/MEDICINE_X1-B9-D46_EXPORT.tsv",
    ],
    "NEURAL_CHIPS": [
        "/home/siebrenf/.local/share/spacepyrates/2024-04-09_2024-04-28/market_inflation/NEURAL_CHIPS_X1-CB25-A4_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-04-09_2024-04-28/market_inflation/NEURAL_CHIPS_X1-FX85-A4_EXPORT.tsv",
    ],
    "PLATINUM": [
        "/home/siebrenf/.local/share/spacepyrates/2024-04-09_2024-04-28/market_inflation/PLATINUM_X1-BT63-B7_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-04-09_2024-04-28/market_inflation/PLATINUM_X1-DB37-B7_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-04-09_2024-04-28/market_inflation/PLATINUM_X1-FX85-B7_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-04-09_2024-04-28/market_inflation/PLATINUM_X1-KB66-B7_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/PLATINUM_X1-AY66-B7_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/PLATINUM_X1-B9-B7_EXPORT.tsv",
    ],
    "POLYNUCLEOTIDES": [
        "/home/siebrenf/.local/share/spacepyrates/2024-04-09_2024-04-28/market_inflation/POLYNUCLEOTIDES_X1-BT63-E46_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-04-09_2024-04-28/market_inflation/POLYNUCLEOTIDES_X1-BZ96-E46_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/POLYNUCLEOTIDES_X1-AY66-E51_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/POLYNUCLEOTIDES_X1-B9-E50_EXPORT.tsv",
    ],
    "PRECIOUS_STONES": [
        "/home/siebrenf/.local/share/spacepyrates/2024-04-09_2024-04-28/market_inflation/PRECIOUS_STONES_X1-BT63-J57_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-04-09_2024-04-28/market_inflation/PRECIOUS_STONES_X1-DB37-J59_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/PRECIOUS_STONES_X1-AY66-J63_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/PRECIOUS_STONES_X1-B9-J61_EXPORT.tsv",
    ],
    "SHIP_PARTS": [
        "/home/siebrenf/.local/share/spacepyrates/2024-04-09_2024-04-28/market_inflation/SHIP_PARTS_X1-BT63-D43_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-04-09_2024-04-28/market_inflation/SHIP_PARTS_X1-BZ96-D42_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-04-09_2024-04-28/market_inflation/SHIP_PARTS_X1-CB25-D38_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-04-09_2024-04-28/market_inflation/SHIP_PARTS_X1-FX85-D47_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-04-09_2024-04-28/market_inflation/SHIP_PARTS_X1-KB66-D40_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/SHIP_PARTS_X1-AY66-D48_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/SHIP_PARTS_X1-B9-D46_EXPORT.tsv",
    ],
    "SHIP_PLATING": [
        "/home/siebrenf/.local/share/spacepyrates/2024-04-09_2024-04-28/market_inflation/SHIP_PLATING_X1-BT63-D44_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-04-09_2024-04-28/market_inflation/SHIP_PLATING_X1-BZ96-D43_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-04-09_2024-04-28/market_inflation/SHIP_PLATING_X1-CB25-D39_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-04-09_2024-04-28/market_inflation/SHIP_PLATING_X1-FX85-D48_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-04-09_2024-04-28/market_inflation/SHIP_PLATING_X1-KB66-D41_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/SHIP_PLATING_X1-AY66-D49_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/SHIP_PLATING_X1-B9-D47_EXPORT.tsv",
    ],
    "SILVER": [
        "/home/siebrenf/.local/share/spacepyrates/2024-04-09_2024-04-28/market_inflation/SILVER_X1-FX85-B7_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-04-09_2024-04-28/market_inflation/SILVER_X1-KB66-B7_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/SILVER_X1-AY66-B7_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/SILVER_X1-B9-B7_EXPORT.tsv",
    ],
    "SUPERGRAINS": [
        "/home/siebrenf/.local/share/spacepyrates/2024-04-09_2024-04-28/market_inflation/SUPERGRAINS_X1-BT63-A4_EXPORT.tsv"
    ],
    "ALUMINUM": [
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/ALUMINUM_X1-AY66-H56_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/ALUMINUM_X1-B9-H54_EXPORT.tsv",
    ],
    "ANTIMATTER": [
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/ANTIMATTER_X1-VZ39-A4_EXPORT.tsv"
    ],
    "ASSAULT_RIFLES": [
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/ASSAULT_RIFLES_X1-AY66-E50_EXPORT.tsv"
    ],
    "BOTANICAL_SPECIMENS": [
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/BOTANICAL_SPECIMENS_X1-YC19-A4_EXPORT.tsv"
    ],
    "DRUGS": [
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/DRUGS_X1-AY66-J63_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/DRUGS_X1-B9-J61_EXPORT.tsv",
    ],
    "ELECTRONICS": [
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/ELECTRONICS_X1-AY66-F54_EXPORT.tsv"
    ],
    "EXOTIC_MATTER": [
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/EXOTIC_MATTER_X1-DF41-A4_EXPORT.tsv"
    ],
    "EXPLOSIVES": [
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/EXPLOSIVES_X1-AY66-F53_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/EXPLOSIVES_X1-B9-F51_EXPORT.tsv",
    ],
    "FABRICS": [
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/FABRICS_X1-AY66-E51_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/FABRICS_X1-B9-E50_EXPORT.tsv",
    ],
    "FERTILIZERS": [
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/FERTILIZERS_X1-AY66-G55_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/FERTILIZERS_X1-B9-G53_EXPORT.tsv",
    ],
    "FIREARMS": [
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/FIREARMS_X1-AC33-E45_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/FIREARMS_X1-AF2-E45_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/FIREARMS_X1-CQ34-E43_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/FIREARMS_X1-CQ37-E51_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/FIREARMS_X1-DH53-E49_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/FIREARMS_X1-GA57-E49_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/FIREARMS_X1-GC34-E43_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/FIREARMS_X1-HP80-E42_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/FIREARMS_X1-HT80-E53_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/FIREARMS_X1-P17-E44_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/FIREARMS_X1-TU33-E43_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/FIREARMS_X1-VZ39-E48_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/FIREARMS_X1-YT60-E44_EXPORT.tsv",
    ],
    "FUEL": [
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/FUEL_X1-BR33-G54_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/FUEL_X1-BS45-G47_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/FUEL_X1-D57-G53_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/FUEL_X1-UG84-G50_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/FUEL_X1-VV38-G52_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/FUEL_X1-XG58-G51_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/FUEL_X1-YH11-G53_EXPORT.tsv",
    ],
    "HOLOGRAPHICS": [
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/HOLOGRAPHICS_X1-BN38-A4_EXPORT.tsv"
    ],
    "IRON": [
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/IRON_X1-B9-H54_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/IRON_X1-DF41-H54_EXPORT.tsv",
    ],
    "JEWELRY": [
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/JEWELRY_X1-AY66-H59_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/JEWELRY_X1-B9-H57_EXPORT.tsv",
    ],
    "MACHINERY": [
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/MACHINERY_X1-AY66-E51_EXPORT.tsv"
    ],
    "MICROPROCESSORS": [
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/MICROPROCESSORS_X1-AY66-A3_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/MICROPROCESSORS_X1-B9-A3_EXPORT.tsv",
    ],
    "MOOD_REGULATORS": [
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/MOOD_REGULATORS_X1-AY66-A4_EXPORT.tsv"
    ],
    "NANOBOTS": [
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/NANOBOTS_X1-FD50-A4_EXPORT.tsv"
    ],
    "NOVEL_LIFEFORMS": [
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/NOVEL_LIFEFORMS_X1-CD60-A4_EXPORT.tsv"
    ],
    "PLASTICS": [
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/PLASTICS_X1-AY66-G55_EXPORT.tsv",
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/PLASTICS_X1-B9-G53_EXPORT.tsv",
    ],
    "VIRAL_AGENTS": [
        "/home/siebrenf/.local/share/spacepyrates/2024-03-24_2024-04-07/market_inflation/VIRAL_AGENTS_X1-B9-A4_EXPORT.tsv"
    ],
}

div_by_bp = True
a_vals = {}
# estimates: at these values, all purchases have their supply level in the correct bin.
baseprices = {
    "AMMUNITION": 1400,  # seems exact
    "BIOCOMPOSITES": 4800,
    "FOOD": 1794,
    "FIREARMS": 3200,
}
# from st2.trading.base_prices import BASE_PRICES as baseprices
s2c = {
    "SCARCE": "red",
    "LIMITED": "orange",
    "MODERATE": "grey",
    "HIGH": "lightblue",
    "ABUNDANT": "blue",
}
t2m = {"EXPORT": "^", "EXCHANGE": ".", "IMPORT": "v"}
for good, files in optimal_goods.items():
    if good not in ["AMMUNITION", "BIOCOMPOSITES", "FOOD", "FIREARMS"]:
        continue
    if len(files) <= 1:
        continue

    # plot goods for which we can identify x0 and y0
    fig = plt.figure(figsize=(15, 10))
    ax = fig.add_subplot(111)

    # tradeGood information was added to each transaction AFTER the purchase
    y_bp = baseprices[good]
    y_lims = [float("inf"), -float("inf")]
    for fname in files:
        f = os.path.basename(fname)
        df, keep = process_df(fname)
        if keep:
            units, tv, port = keep
        else:
            continue

        assert units == 1
        idx_min = df[df["supply"] == "MODERATE"].index[0] + 3 * tv
        idx_max = idx_min + 1
        y_min = df.at[idx_min, "purchasePrice"]
        y_max = df.at[idx_max, "purchasePrice"]
        dy = (y_max - y_min) / 1  # slope
        # y_bp = y_min + dy*dx
        dx = 0
        if y_bp != y_min and dy != 0:
            dx = (y_bp - y_min) / dy
        if dx > 1 or dx < 0:
            print("bad dx:", dx)
        idx_bp = idx_min + dx
        ax.axvline((idx_min - idx_bp) * units / tv - 1, zorder=-5, color="pink")
        ax.axvline((idx_max - idx_bp) * units / tv - 1, zorder=-5, color="purple")

        if div_by_bp:
            y = [i / y_bp for i in df["purchasePrice"]]
            ax.axhline(y_min / y_bp, zorder=-5, color="pink")  # highest
            ax.axhline(y_max / y_bp, zorder=-5, color="purple")  # lowest
        else:
            y = df["purchasePrice"].to_list()
            ax.axhline(y_min, zorder=-5, color="pink")  # highest
            ax.axhline(y_max, zorder=-5, color="purple")  # lowest
        x = []
        for i in range(len(df)):
            x.append((i - idx_bp) * units / tv + 1)
        x = [-i for i in x]
        c = [s2c[supply] for supply in df["supply"]]

        ax.scatter(x, y, c=c, s=18, zorder=5)
        ax.plot(x, y, zorder=-2, alpha=0.4, c="green", label=f"tv={int(tv)}")
        if not div_by_bp:
            ax.axhline(y_bp, zorder=-15)

        infer = True
        if infer:

            if div_by_bp:

                def func(x, a):
                    x = x + 1
                    return 1 * (a * 2 ** (-0.3 * x) - a + 1)

            else:

                def func(x, a):
                    x = x + 1
                    return y_bp * (a * 2 ** (-0.3 * x) - a + 1)

            popt, pcov = curve_fit(func, x, y, p0=[0.35], bounds=((0, 1)))  # noqa
            a = popt[0]
            a2 = round(a * 20) / 20  # round to nearest 0.05
            if a2 not in a_vals:
                a_vals[a2] = 0
            a_vals[a2] += 1
            y2 = func(np.array(x), a)  # [-i for i in x]
            r_squared = r2_score(y, y2)
            ax.plot(
                x,
                y2,
                ls="--",
                zorder=-1,
                alpha=0.5,
                label=f"{a=:.02f} r^2={round(r_squared, 4)}",
            )

        # for plotting only
        x_lims = [i for i in x if 7.5 >= i >= -5.5]
        y0 = y[x.index(max(x_lims))]
        if y0 < y_lims[0]:
            y_lims[0] = y0
        y1 = y[x.index(min(x_lims))]
        if y1 > y_lims[1]:
            y_lims[1] = y1

    plt.title(f"{good} bp={y_bp}")
    ax.set_xlim(-5.5, 7.5)
    ax.set_ylim(y_lims[0] * 0.95, y_lims[1] * 1.05)
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

# x = []
# y = []
# for k in sorted(a_vals):
#     x.append(k)
#     y.append(a_vals[k])
#     print(k, a_vals[k])
# plt.bar(x, y)
# plt.show()

# output:
# 0.25 1
# 0.3 7
# 0.35 32
# 0.4 51
# 0.45 28
# 0.5 11
# 0.55 5
