import os
import sys

import pandas as pd
from bokeh.layouts import column, row
from bokeh.models import Select, Slider
from bokeh.plotting import curdoc, figure
from psycopg import connect

pkg = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.extend([pkg])
from st2.startup import db_server

db_server()

# count the extraction-related traits in each system
params = []
asteroids = ""
for deposit in [
    "MINERAL_DEPOSITS",
    "COMMON_METAL_DEPOSITS",
    "PRECIOUS_METAL_DEPOSITS",
    "RARE_METAL_DEPOSITS",
]:
    name = deposit.rsplit("_", 1)[0].lower()
    cmd = f"COUNT(CASE WHEN type = ANY(%s) AND trait = '{deposit}' THEN 1 END) AS {name}s, "
    asteroids += cmd
    params.append(["ASTEROID", "ASTEROID_FIELD", "ENGINEERED_ASTEROID"])

# list faction & traits per system
query = f"""
        SELECT 
            s.*, 
            w.*
        FROM systems AS s
        LEFT JOIN (
            SELECT 
                "systemSymbol",
                STRING_AGG(DISTINCT faction, ', ') AS faction,
                COUNT(CASE WHEN trait = 'MARKETPLACE' THEN 1 END) AS marketplaces,
                COUNT(CASE WHEN trait = 'SHIPYARD' THEN 1 END) AS shipyards,
                COUNT(CASE WHEN trait = 'UNCHARTED' THEN 1 END) AS uncharted,
                COUNT(CASE WHEN type = 'JUMP_GATE' THEN 1 END) AS jump_gates,
                {asteroids}
                COUNT(CASE WHEN type = 'GAS_GIANT' THEN 1 END) AS gas_giants
            FROM 
                waypoints,
                UNNEST(traits) AS trait
            GROUP BY 
                "systemSymbol"
        ) AS w
        ON s.symbol = w."systemSymbol"
        ORDER BY 
            "systemSymbol"
        """
with connect("dbname=st2 user=postgres") as conn:
    with conn.cursor() as cur:
        cur.execute(query, params)
        ret = cur.fetchall()
# convert to a pandas dataframe for quick (re)grouping later
df = pd.DataFrame(
    ret,
    columns=[
        "symbol",
        "type",
        "x",
        "y",
        "_",
        "faction",
        "marketplaces",
        "shipyards",
        "uncharted",
        "jump_gates",
        "minerals",
        "common_metals",
        "rare_metals",
        "precious_metals",
        "gas_giants",
    ],
)
df.set_index("symbol", inplace=True)
df.drop(columns="_", inplace=True)
for col in [
    "type",
    "faction",
]:
    col_str = df[col].astype("str")
    categories = sorted(col_str.unique())
    if "None" in categories:
        categories.remove("None")
        categories.append("None")
    df[col] = pd.Categorical(col_str, categories=categories, ordered=True)

# add additional columns with plotting data
type2size = {
    "BLACK_HOLE": 3,
    "BLUE_STAR": 4,
    "HYPERGIANT": 5,
    "NEBULA": 6,
    "NEUTRON_STAR": 4.2,
    "ORANGE_STAR": 4.1,
    "RED_STAR": 3.8,
    "UNSTABLE": 4.3,
    "WHITE_DWARF": 3.5,
    "YOUNG_STAR": 3.9,
}
df["sizes"] = df["type"].cat.rename_categories(type2size)

# data = np.transpose(ret)
# # bokeh legend_group doesn't like None
# data[5, :] = data[5, :].astype(str)
#
# # for n in range(len(data)):
# #     d = [d for d in data[n, :] if d]
# #     print(f"col_{n}: {d[:5]}, vals={len(d)}, len={len(data[n, :])}")
#
# type2size = {
#     "BLACK_HOLE": 3,
#     "BLUE_STAR": 4,
#     "HYPERGIANT": 5,
#     "NEBULA": 6,
#     "NEUTRON_STAR": 4.2,
#     "ORANGE_STAR": 4.1,
#     "RED_STAR": 3.8,
#     "UNSTABLE": 4.3,
#     "WHITE_DWARF": 3.5,
#     "YOUNG_STAR": 3.9,
# }
# vectorized_map = np.vectorize(lambda x: type2size[x])
# sizes = vectorized_map(data[1, :])
#
# source = ColumnDataSource(
#     {
#         "symbol": data[0, :],
#         "type": data[1, :],
#         "x": data[2, :],
#         "y": data[3, :],
#         # data[4, :]: systems of charted waypoints
#         "faction": data[5, :],
#         "marketplaces": data[6, :],
#         "shipyards": data[7, :],
#         "uncharted": data[8, :],
#         "jump_gates": data[9, :],
#         "minerals": data[10, :],
#         "common_metals": data[11, :],
#         "rare_metals": data[12, :],
#         "precious_metals": data[13, :],
#         "gas_giants": data[14, :],
#         # custom columns
#         "sizes": sizes,
#     }
# )

type2color = {
    "BLACK_HOLE": "midnightblue",
    "BLUE_STAR": "royalblue",
    "HYPERGIANT": "goldenrod",
    "NEBULA": "darkorchid",
    "NEUTRON_STAR": "cyan",
    "ORANGE_STAR": "orange",
    "RED_STAR": "firebrick",
    "UNSTABLE": "lightgreen",
    "WHITE_DWARF": "whitesmoke",
    "YOUNG_STAR": "gold",
}
df["color_type"] = df["type"].cat.rename_categories(type2color)

# https://matplotlib.org/stable/gallery/color/named_colors.html#css-colors
faction2color = {
    "AEGIS": "slateblue",  # proud/defensive
    # "ANCIENTS": "blue",  # ?
    "ASTRO": "chocolate",  # scavengers
    "COBALT": "limegreen",  # money
    "CORSAIRS": "darkred",  # pirates
    "COSMIC": "cornflowerblue",  # default
    # "CULT": "blue",
    "DOMINION": "orangered",  # AGGRESSIVE
    "ECHO": "saddlebrown",  # Tech
    # "ETHEREAL": "blue",
    "GALACTIC": "olivedrab",  # PEACEFUL
    # "LORDS": "blue",
    "OBSIDIAN": "purple",  # secretive
    "OMEGA": "teal",  # exiles
    "QUANTUM": "cyan",  # science
    # "SHADOW": "blue",
    "SOLITARY": "seagreen",  # farmers
    "UNITED": "darkslateblue",  # proud/defensive
    "VOID": "gold",  # nomadic
    "None": "dimgrey",
}
df["color_faction"] = df["faction"].cat.rename_categories(faction2color)

# TODO: hover tooltip layout:
#  https://docs.bokeh.org/en/latest/docs/user_guide/interaction/tools.html#custom-tooltip
TOOLTIPS = [
    ("symbol", "@symbol"),
    ("type", "@type"),
    ("faction", "@faction"),
    ("marketplaces", "@marketplaces"),
    ("shipyards", "@shipyards"),
    ("uncharted", "@uncharted"),
    ("jump_gates", "@jump_gates"),
    ("minerals", "@minerals"),
    ("common_metals", "@common_metals"),
    ("rare_metals", "@rare_metals"),
    ("precious_metals", "@precious_metals"),
    ("gas_giants", "@gas_giants"),
    ("", ""),  # white line
]


def create_figure():
    p = figure(
        width=1000,
        height=1000,
        x_axis_label="x",
        y_axis_label="y",
        tools="pan,wheel_zoom,tap,reset",  # ,save
        active_scroll="wheel_zoom",
        tooltips=TOOLTIPS,
    )
    # TODO: pin x and y range (it flashes when filtering)
    # p.toolbar.autohide = True

    data = df.copy(True)
    data = data[data["marketplaces"].fillna(0) >= market_slider.value]
    if color.value == "Type":
        title = "System types"
        for group, source in data.groupby("type", observed=True):
            p.scatter(
                source=source,
                x="x",
                y="y",
                size="sizes",
                legend_label=group,
                fill_color="color_type",
                line_color="dimgrey",
                line_width=0.5,
                hover_color="white",
                hover_alpha=0.5,
            )

    elif color.value == "Faction":
        title = "Factions"
        for group, source in df.groupby("faction", observed=True):
            plot = p.scatter(
                source=source,
                x="x",
                y="y",
                size="sizes",
                legend_label=group,
                fill_color="color_faction",
                line_color="dimgrey",
                line_width=0.5,
                hover_color="white",
                hover_alpha=0.5,
            )
            if group == "None":
                plot.muted = True

    else:
        raise ValueError(f"{color.value=}")
    p.legend.title = title
    p.legend.click_policy = "mute"

    # if color.value == "Type":
    #     vectorized_map = np.vectorize(lambda x: type2color[x])
    #     colors = vectorized_map(data[1, :])
    #     labels = source.data["type"]  # data[1, :]
    #     title = "System types"
    # elif color.value == "Faction":
    #     vectorized_map = np.vectorize(lambda x: faction2color.get(x, "blue"))
    #     colors = vectorized_map(data[5, :])
    #     labels = source.data["faction"]
    #     title = "Factions"
    # else:
    #     raise ValueError(f"{color.value=}")
    # source.data["colors"] = colors
    # source.data["labels"] = labels
    #
    # p.scatter(
    #     source=source,
    #     x="x",
    #     y="y",
    #     size="sizes",
    #     legend_group="labels",
    #     fill_color="colors",
    #     line_color="dimgrey",
    #     line_width=0.5,
    #     hover_color="white",
    #     hover_alpha=0.5,
    # )
    # p.legend.title = title
    # p.legend.click_policy = "mute"

    return p


def update(attr, old, new):
    layout.children[0] = create_figure()


# TODO: more slider filters for # of traits
market_slider = Slider(
    title="Minimum marketplaces", value=0, start=0, end=df["marketplaces"].max(), step=1
)
market_slider.on_change("value", update)

color = Select(title="Color", value="Type", options=["Type", "Faction"])
color.on_change("value", update)

controls = column(color, width=200)
layout = row(create_figure(), controls, market_slider)

curdoc().add_root(layout)
curdoc().title = "SpaceTraders API"

# data
# [x] symbol, x, y, type, faction, ...
# [ ] gate connections?

# figure
#  [x] x and y axis fixed
#  [x] tools: "pan,wheel_zoom,box_zoom,reset,hover,save,tap"
#  [x] hover: https://docs.bokeh.org/en/latest/docs/user_guide/interaction/tools.html#basic-tooltips
#  - plot.title.text = f"{len(df)} systems selected"

# controls
#  [ ] color by type/factions/sellPrice/purchasePrice
#  [ ] filters (factions, systemTypes, waypointTypes, traits, tradeGoods)
#  [ ] show/hide gate connections?
#  [ ] show/hide HQs
#  [ ] show/hide my ships?
#  [ ] select: open the system plot
