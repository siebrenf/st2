import os
import sys

import numpy as np
from bokeh.events import Tap
from bokeh.layouts import column, row
from bokeh.models import (
    Checkbox,
    ColumnDataSource,
    Div,
    Legend,
    RangeSlider,
    Select,
    TapTool,
)
from bokeh.plotting import curdoc, figure

pkg = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.extend([pkg])
from st2.startup import db_server
from st2.ui.utils import connection_graph, hq_df, sector_df, system_df

db_server()

df = sector_df()
hqs = hq_df()
graph = connection_graph()
sources = []


def sector_figure():
    while sources:
        sources.pop(0)

    data = df.copy(True)
    if catalogued_only_checkbox.active:
        data = data.dropna(subset="marketplaces")
    data = data[
        (data["marketplaces"].fillna(0).between(*marketplace_slider.value))
        & (data["shipyards"].fillna(0).between(*shipyard_slider.value))
        & (data["uncharted"].fillna(0).between(*uncharted_slider.value))
        & (data["jump_gates"].fillna(0).between(*gate_slider.value))
    ]

    plots = {}
    p = figure(
        title="Sector X1",
        width=1000,
        height=800,
        # pin the range (required when filtering)
        x_range=(int(df["x"].min() * 1.02), int(df["x"].max() * 1.02)),
        y_range=(int(df["y"].min() * 1.02), int(df["y"].max() * 1.02)),
        x_axis_label="x",
        y_axis_label="y",
        # hover is included via the tooltips
        tools="pan,wheel_zoom,reset",  # ,save
        active_scroll="wheel_zoom",
        tooltips=SECTOR_TOOLTIPS,
    )
    p.toolbar.autohide = True

    if gate_connection_checkbox.active:
        p.renderers.append(graph)

    systems_to_show = set()
    if color.value == "Type":
        title = "System types"
        for group, source in data.groupby("type", observed=True):
            systems_to_show.update(source.index)

            source = ColumnDataSource(source)
            sources.append(source)
            plot = p.scatter(
                source=source,
                x="x",
                y="y",
                size="sizes",
                # legend_label=group,
                fill_color="color_type",
                line_color="dimgrey",
                line_width=0.5,
                hover_color="white",
                hover_alpha=0.5,
            )
            plots[group] = [plot]

    elif color.value == "Faction":
        title = "Factions"
        for group, source in data.groupby("faction", observed=True):
            systems_to_show.update(source.index)

            source = ColumnDataSource(source)
            sources.append(source)
            plot = p.scatter(
                source=source,
                x="x",
                y="y",
                size="sizes",
                # legend_label=group,
                fill_color="color_faction",
                line_color="dimgrey",
                line_width=0.5,
                hover_color="white",
                hover_alpha=0.5,
            )
            if group == "None":
                plot.muted = True
            plots[group] = [plot]

    else:
        raise ValueError(f"{color.value=}")

    # add markers around headquarters
    if headquarter_checkbox.active:
        hqs_to_show = list(systems_to_show & set(hqs["headquarters"]))
        source = ColumnDataSource(data.loc[hqs_to_show])
        sources.append(source)
        plot = p.scatter(
            source=source,
            x="x",
            y="y",
            size=12,
            marker="diamond",
            # legend_label="Headquarters",
            fill_color=None,
            line_color="white",
            line_width=1.0,
        )
        plots["Headquarters"] = [plot]

    legend = Legend(
        title=title,
        items=[(t, plots[t]) for t in plots],
        location="top",
    )
    p.add_layout(legend, "right")
    p.legend.title = title
    p.legend.click_policy = "mute"

    # system plot
    # https://stackoverflow.com/questions/69812932/open-new-plot-with-bokeh-taptool
    p.add_tools(TapTool())  # behavior="inspect"
    p.on_event(Tap, tapfunc)

    return p


def tapfunc():

    def selected_system_symbol():
        symbol = None
        for source in sources:
            for idx in source.selected.indices:
                # janky deselect
                source.selected.indices = []
                if symbol is None:
                    symbol = source.data["symbol"][idx]
                break
        return symbol

    system_symbol = selected_system_symbol()
    plot = system_figure(system_symbol)
    if plot:
        layout.children[0].children[1].children[0] = plot


def update_sector_figure(attr, old, new):
    layout.children[0].children[0] = sector_figure()


def orbiter_coordinates(radius, n):
    t = np.linspace(0, 2 * np.pi, n, endpoint=False)
    x = radius * np.cos(t)
    y = radius * np.sin(t)
    coordinates = np.c_[x, y]
    return coordinates


def system_figure(system_symbol=None):
    if system_symbol is None:
        return

    df = system_df(system_symbol)
    xrange = (0, 0)
    yrange = (0, 0)
    if len(df):
        xrange = (int(df["x"].min() * 1.5), int(df["x"].max() * 1.5))
        yrange = (int(df["y"].min() * 1.5), int(df["y"].max() * 1.5))
    p = figure(
        title=f"System {system_symbol}",
        width=700,
        height=500,
        # pin the range (required when filtering)
        x_range=xrange,
        y_range=yrange,
        x_axis_label="x",
        y_axis_label="y",
        # hover is included via the tooltips
        tools="pan,wheel_zoom,reset",  # ,tap,save
        active_scroll="wheel_zoom",
        tooltips=SYSTEM_TOOLTIPS,
    )
    p.toolbar.autohide = True

    # bokeh has no z-order, so we plot in order
    plot_order = [
        "NEBULA",
        "GAS_GIANT",
        "DEBRIS_FIELD",
        "ASTEROID_FIELD",
        "PLANET",
        "GRAVITY_WELL",
        "ARTIFICIAL_GRAVITY_WELL",
        "MOON",
        "JUMP_GATE",
        "ORBITAL_STATION",
        "FUEL_STATION",
        "ASTEROID_BASE",
        "ENGINEERED_ASTEROID",
        "ASTEROID",
    ]
    plots = {t: [] for t in sorted(plot_order)}
    for t in plot_order:
        # df2 = df[df["type"] == t]
        # if len(df2) == 0:
        #     continue
        # plot = p.scatter(
        #     source=df2,
        #     x="x",
        #     y="y",
        #     # legend_label=t,
        #     # alpha="alpha",
        #     marker="marker",
        #     size="size",
        #     fill_color="color",
        #     line_color="dimgrey",
        #     line_width=1.0,
        #     hover_color="white",
        #     hover_alpha=0.5,
        # )
        # plots[t] = [plot]

        df2 = df[(df["orbits"].isna()) & (df["type"] == t)]
        if len(df2) == 0:
            continue
        plot = p.scatter(
            source=df2,
            x="x",
            y="y",
            # legend_label=t,
            # alpha="alpha",
            marker="marker",
            size="size",
            fill_color="color",
            line_color="dimgrey",
            line_width=1.0,
            hover_color="white",
            hover_alpha=0.5,
        )
        plots[t].append(plot)

    for wp in df[df["orbitals"].str.len() > 0].index:
        orbitals = df.at[wp, "orbitals"]
        radius = abs(xrange[0] - xrange[1]) * 0.003
        coordinates = orbiter_coordinates(radius, len(orbitals))
        df2 = df.loc[orbitals].copy()
        for wp, (x, y) in zip(orbitals, coordinates):
            df2.at[wp, "x"] += int(x)
            df2.at[wp, "x"] += int(y)
        for t, df3 in df2.groupby("type"):
            plot = p.scatter(
                source=df3,
                x="x",
                y="y",
                color="color",
                marker="marker",
                size="size",
            )
            plots[t].append(plot)

        # for waypoint, (x, y) in zip(orbitals, coordinates):
        #     md = df[df.index == waypoint].copy()
        #     md["x"] = md["x"] + x
        #     md["y"] = md["y"] + y
        #     plot = p.scatter(
        #         source=md,
        #         x="x",
        #         y="y",
        #         color="color",
        #         marker="marker",
        #         size="size",
        #     )
        #     plots[md.at[waypoint, "type"]].append(plot)

    legend = Legend(
        title="Waypoint type",
        items=[(t, plots[t]) for t in sorted(plots) if plots[t]],
        location="top",
    )
    p.add_layout(legend, "right")

    return p


# TODO: hover tooltip layout:
#  https://docs.bokeh.org/en/latest/docs/user_guide/interaction/tools.html#custom-tooltip
SECTOR_TOOLTIPS = [
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


SYSTEM_TOOLTIPS = [
    ("symbol", "@symbol"),
    ("type", "@type"),
    ("traits", "@traits"),
    ("", ""),  # white line
]


# TODO: more slider filters for # of traits
color = Select(title="Color", value="Type", options=["Type", "Faction"])
color.on_change("value", update_sector_figure)

catalogued_only_checkbox = Checkbox(label="Catalogued systems only", active=False)
catalogued_only_checkbox.on_change("active", update_sector_figure)

headquarter_checkbox = Checkbox(label="Show headquarters", active=True)
headquarter_checkbox.on_change("active", update_sector_figure)

gate_connection_checkbox = Checkbox(label="Show gate connections", active=True)
gate_connection_checkbox.on_change("active", update_sector_figure)


m = df["marketplaces"].max()
marketplace_slider = RangeSlider(
    title="Marketplaces", value=(0, m), start=0, end=m, step=1
)
marketplace_slider.on_change("value", update_sector_figure)

m = df["shipyards"].max()
shipyard_slider = RangeSlider(title="Shipyards", value=(0, m), start=0, end=m, step=1)
shipyard_slider.on_change("value", update_sector_figure)

m = df["jump_gates"].max()
gate_slider = RangeSlider(title="Jump gates", value=(0, m), start=0, end=m, step=1)
gate_slider.on_change("value", update_sector_figure)

m = df["uncharted"].max()
uncharted_slider = RangeSlider(title="Uncharted", value=(0, m), start=0, end=m, step=1)
uncharted_slider.on_change("value", update_sector_figure)


"""
layout:

+---------------------------+---------------------+
|top_left top_left top_left | top_right top_right |
|top_left top_left top_left | top_right top_right |
|top_left top_left top_left | top_right top_right |
|top_left top_left top_left | top_right top_right |
|top_left top_left top_left | top_right top_right |
|top_left top_left top_left +----------+----------+
|top_left top_left top_left | controls | controls |
|top_left top_left top_left | sector   | system   |
+---------------------------+----------+----------+
|bottom bottom bottom bottom bottom bottom bottom |
|bottom bottom bottom bottom bottom bottom bottom |
|bottom bottom bottom bottom bottom bottom bottom |
+-------------------------------------------------+
"""

top_left = sector_figure()

controls_sector_figure = column(
    Div(text="Sector controls"),
    row(
        color,
        column(
            catalogued_only_checkbox, headquarter_checkbox, gate_connection_checkbox
        ),
    ),
    marketplace_slider,
    shipyard_slider,
    gate_slider,
    uncharted_slider,
    width=220,
)
controls_system_figure = column(
    Div(text="System controls"),
    width=220,
)
controls = row(
    controls_sector_figure, controls_system_figure, align="center"
)  # width=400,
top_right = column(figure(width=700, height=500), controls)

top = row(top_left, top_right)
bottom = row()

layout = column(top, bottom)

curdoc().add_root(layout)
curdoc().title = "SpaceTraders API"

# data
# [x] symbol, x, y, type, faction, ...
# [x] gate connections?

# figure
#  [x] x and y axis fixed
#  [x] tools: "pan,wheel_zoom,box_zoom,reset,hover,save,tap"
#  [x] hover: https://docs.bokeh.org/en/latest/docs/user_guide/interaction/tools.html#basic-tooltips
#  - plot.title.text = f"{len(df)} systems selected"

# controls
#  [x] color by type/factions
#  [ ] color by sellPrice/purchasePrice
#  [x] filters (factions, systemTypes, waypointTypes)
#  [ ] filters (traits, tradeGoods)
#  [x] show/hide gate connections?
#  [x] show/hide HQs
#  [ ] show/hide my ships?
#  [x] select: open the system plot
