"""
Run with:
    bokeh serve st2/ui
"""
# https://stackoverflow.com/questions/78732362/how-to-upload-pandas-data-frames-fast-with-psycopg3
# https://gist.github.com/jakebrinkmann/de7fd185efe9a1f459946cf72def057e
# https://stackoverflow.com/questions/51144743/make-the-colour-and-marker-of-bokeh-plot-scatter-points-dependent-on-dataframe-v
# https://docs.bokeh.org/en/latest/docs/gallery.html
# https://matplotlib.org/stable/gallery/color/named_colors.html
# https://docs.bokeh.org/en/latest/docs/gallery.html
# https://docs.bokeh.org/en/latest/docs/user_guide/server/app.html#building-applications

import os
import sys

import numpy as np
import pandas as pd
from bokeh.layouts import column, row
from bokeh.models import (
    AutocompleteInput,
    BooleanFilter,
    Button,
    CDSView,
    CheckboxGroup,
    ColumnDataSource,
    CustomJS,
    Div,
    GraphRenderer,
    HoverTool,
    Jitter,
    MultiChoice,
    MultiLine,
    NodesAndLinkedEdges,
    NodesOnly,
    RangeSlider,
    RangeTool,
    Scatter,
    Select,
    StaticLayoutProvider,
    TapTool,
)
from bokeh.plotting import curdoc, figure

pkg = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.extend([pkg])
from st2.startup import db_server

from .utils import (
    connection_df,
    hq_df,
    sector_df,
    system_df,
    system_tradegoods,
    trade_dfs,
)

db_server()


"""
Variables
"""
sector = sector_df()
source_sector = ColumnDataSource(sector)
hqs = hq_df()
connections = connection_df()
source_connections = ColumnDataSource(connections)
source_system = ColumnDataSource(
    {
        c: []
        for c in [
            "symbol",
            "systemSymbol",
            "type",
            "x",
            "y",
            "orbits",
            "orbitals",
            "traits",
            "chart",
            "faction",
            "isUnderConstruction",
            "marker",
            "size",
            "color",
        ]
    }
)

# Filters for views
filter_sector = BooleanFilter(~sector.index.isna())
filter_hqs = BooleanFilter(sector.index.isin(hqs["headquarters"]))
filter_connections = BooleanFilter(~connections["start"].isna())

# Filters for checkboxes
filter_complete = BooleanFilter(sector["incomplete"] == 0)
filter_waypoints = BooleanFilter(sector["total_waypoints"] > 0)
filter_charted = BooleanFilter(sector["charted"] > 1)
filter_gate = BooleanFilter(sector["jump_gates"] > 0)
filter_observed = BooleanFilter(sector["observed"])

# Views
view_sector = CDSView(filter=filter_sector)
view_hqs = CDSView(filter=filter_hqs)
view_connections = CDSView(filter=filter_connections)


"""
Controls
"""
# selected system to plot
select_system = AutocompleteInput(
    title="Select a system in the Sector plot, or Search a system and press Enter",
    search_strategy="includes",
    value="X1-",
    completions=sector.index.to_list(),
    # sizing_mode="scale_both",
)

button_center = Button(
    label="Center",
    button_type="primary",  # "'default',
)

select_color = Select(
    title="Color",
    value="Type",
    options=["Type", "Faction"],
    # sizing_mode="scale_both",
)

checkboxes_system = CheckboxGroup(
    labels=[
        "complete only",  # observed by the Stargazer and the Cartographer
        "has waypoints",
        "has charted wps",  # any waypoint where traits != ["UNCHARTED"]
        "has jump gate",
        "observed",  # has entries in market_tradegoods
    ],
    active=[],
    # sizing_mode="scale_both",
)

m = sector["marketplaces"].max()
slider_marketplaces = RangeSlider(
    title="Marketplaces",
    value=(0, m),
    start=0,
    end=m,
    step=1,
    # sizing_mode="scale_both",
)

m = sector["shipyards"].max()
slider_shipyards = RangeSlider(
    title="Shipyards",
    value=(0, m),
    start=0,
    end=m,
    step=1,
    # sizing_mode="scale_both",
)

m = sector["points_of_interest"].max()
slider_interesting = RangeSlider(
    title="Waypoints of interest (possible marketplaces)",
    value=(0, m),
    start=0,
    end=m,
    step=1,
    # sizing_mode="scale_both",
)

select_tradegoods = MultiChoice(
    title="Select system tradeGood(s) to visualize",
    value=[],
    options=[],
    # sizing_mode="scale_both",
)

checkboxes_tradegoods = CheckboxGroup(
    labels=[
        "IMPORT",
        "EXPORT",
        "EXCHANGE",
    ],
    active=[0, 1, 2],
    # sizing_mode="scale_both",
)

"""
Other
"""
# Can print stuff here from CustomJS callbacks
debug = Div(
    height=300,
    width=200,
    stylesheets=[":host { white-space: pre; }"],
    text="Debug window",
    # sizing_mode="scale_both",
    background="navy",
)


"""
Plot sector
"""
plot_sector = figure(
    title="Sector X1",
    height=700,
    width=750,
    x_range=(int(sector["x"].min() * 1.02), int(sector["x"].max() * 1.02)),
    y_range=(int(sector["y"].min() * 1.02), int(sector["y"].max() * 1.02)),
    x_axis_label="x",
    y_axis_label="y",
    tools="pan,wheel_zoom,reset",
    active_scroll="wheel_zoom",
    # sizing_mode="scale_both",
)

# plot the faction HQ outlines
plot_sector.scatter(
    source=source_sector,
    view=view_hqs,
    x="x",
    y="y",
    size=12,
    marker="diamond",
    fill_color=None,
    line_color="white",
    line_width=1.0,
)

# graph figure
graph = GraphRenderer(name="sector")
scatter_glyph = Scatter(
    size=4,
    fill_color="color_type",
    fill_alpha="alpha_type",
    line_alpha="alpha_type",
    line_color="dimgrey",
    line_width=0.5,
)
graph.node_renderer.glyph = scatter_glyph
graph.node_renderer.hover_glyph = scatter_glyph.clone(size=12, line_width=1)

ml_glyph = MultiLine(
    line_color="goldenrod",
    line_alpha=0.2,
    line_width=1,
    line_dash="dotted",
    line_dash_offset=1,
)
graph.edge_renderer.glyph = ml_glyph
graph.edge_renderer.hover_glyph = ml_glyph.clone(
    line_color="red",
    line_width=2,
    line_dash="solid",
)

# nodes
graph.node_renderer.data_source = source_sector
graph.node_renderer.view = view_sector
graph.layout_provider = StaticLayoutProvider(
    graph_layout=sector[["x", "y"]].apply(list, axis=1).to_dict(),
)

# edges
graph.edge_renderer.data_source = source_connections
graph.edge_renderer.view = view_connections

graph.inspection_policy = NodesAndLinkedEdges()
graph.selection_policy = NodesOnly()

# add the graph to the plot
plot_sector.renderers.append(graph)


"""
Plot system
"""
plot_system = figure(
    title="Select a system to plot",
    x_range=(-1000, 1000),
    y_range=(-1000, 1000),
    x_axis_label="x",
    y_axis_label="y",
    tools="pan,wheel_zoom,reset",
    active_scroll="wheel_zoom",
    # sizing_mode="scale_both",
)

plot_system.scatter(
    source=source_system,
    x={"field": "x", "transform": Jitter(width=25)},
    y={"field": "y", "transform": Jitter(width=25)},
    marker="marker",
    size="size",
    alpha=0.75,
    fill_color="color",
    line_color="dimgrey",
    line_width=0.5,
)


"""
Plot market
"""
end = np.datetime64("now")
start = end - np.timedelta64(1, "D")
plot_tradegoods = figure(
    title="Select a tradeGood to plot",
    height=400,
    y_range=(0, 1),
    x_range=(start, end),
    y_axis_label="Prices",
    x_axis_type="datetime",
    x_axis_location="above",
    tools="pan,wheel_zoom",  # above ranges used as reset defaults
    active_scroll="wheel_zoom",
    sizing_mode="scale_width",
)
plot_tradegoods_price = plot_tradegoods.multi_line(
    source=ColumnDataSource(
        {key: [] for key in ["goods", "waypoint_symbols", "xs", "ys", "colors"]}
    ),
    xs="xs",
    ys="ys",
    line_color="colors",
)
tg_keys = [
    "waypointSymbol",
    "systemSymbol",
    "symbol",
    "tradeVolume",
    "type",
    "supply",
    "activity",
    "purchasePrice",
    "sellPrice",
    "timestamp",
    "marker",
    "color",
]
plot_tradegoods_tg_s = plot_tradegoods.scatter(
    source=ColumnDataSource({key: [] for key in tg_keys}),
    x="timestamp",
    y="sellPrice",
    color="color",
    marker="marker",
    alpha=0.5,
    size=15,
)
plot_tradegoods_tg_p = plot_tradegoods.scatter(
    source=ColumnDataSource({key: [] for key in tg_keys}),
    x="timestamp",
    y="purchasePrice",
    color="color",
    marker="marker",
    alpha=0.5,
    size=15,
)
ta_keys = [
    "waypointSymbol",
    "systemSymbol",
    "shipSymbol",
    "tradeSymbol",
    "type",
    "units",
    "pricePerUnit",
    "totalPrice",
    "timestamp",
    "color",
]
plot_tradegoods_ta = plot_tradegoods.scatter(
    source=ColumnDataSource({key: [] for key in ta_keys}),
    x="timestamp",
    y="pricePerUnit",
    color="color",
    size="units",
    alpha=0.5,
)

# range selection plot
plot_select_tradegoods = figure(
    # title="Drag the middle and edges of the selection box to change the range above",
    height=100,
    y_range=plot_tradegoods.y_range,
    x_axis_type="datetime",
    y_axis_type=None,
    tools="",
    toolbar_location=None,
    sizing_mode="scale_width",
)
plot_select_tradegoods.ygrid.grid_line_color = None
plot_select_tradegoods_price = plot_select_tradegoods.multi_line(
    source=ColumnDataSource(
        dict(
            goods=[],
            waypoint_symbols=[],
            xs=[],
            ys=[],
            colors=[],
        )
    ),
    xs="xs",
    ys="ys",
    line_color="colors",
    line_width=2,
)

# range selection tool
range_tool = RangeTool(x_range=plot_tradegoods.x_range, start_gesture="pan")
range_tool.overlay.fill_color = "#7ce07c"  # "navy"
range_tool.overlay.fill_alpha = 0.2
plot_select_tradegoods.add_tools(range_tool)


"""
Reactivity
"""
# JS debugging:
"""
div.text = `${div.text}\nthis.value: ${this.value}`;
console.log(gn.glyph.fill_color);
"""

plot_sector.add_tools(
    HoverTool(
        tooltips=[
            ("symbol", "@index"),
            ("type", "@type"),
            ("faction", "@faction"),
            ("waypoints", "@total_waypoints"),
            (
                "~markets/gates/asteroids/gas giants",
                "@points_of_interest/@jump_gates/@asteroids/@gas_giants",
            ),
            ("marketplaces/shipyards/uncharted", "@marketplaces/@shipyards/@uncharted"),
            (
                "C/R/P metal/mineral deposits",
                "@common_metals/@rare_metals/@precious_metals/@minerals",
            ),
            ("", ""),  # empty line
        ]
    ),
    TapTool(
        behavior="inspect",
        callback=CustomJS(
            args=dict(select_system=select_system),
            code="""
            select_system.value = cb_data.source.data.index[cb_data.source.inspected.indices]
            """,
        ),
    ),
)

plot_tradegoods.add_tools(
    HoverTool(
        renderers=[plot_tradegoods_tg_s, plot_tradegoods_tg_p],
        tooltips=[
            ("TradeGood", ""),
            ("waypointSymbol", "@waypointSymbol"),
            ("symbol", "@symbol"),
            ("tradeVolume", "@tradeVolume"),
            ("type", "@type"),
            ("supply", "@supply"),
            ("activity", "@activity"),
            ("purchasePrice", "@purchasePrice"),
            ("sellPrice", "@sellPrice"),
            ("timestamp", "@timestamp{%F %T}"),
            ("", ""),  # white line
        ],
        formatters={"@timestamp": "datetime"},
    ),
    HoverTool(
        renderers=[plot_tradegoods_ta],
        tooltips=[
            ("Transaction", ""),
            ("waypointSymbol", "@waypointSymbol"),
            ("shipSymbol", "@shipSymbol"),
            ("tradeSymbol", "@tradeSymbol"),
            ("type", "@type"),
            ("units", "@units"),
            ("pricePerUnit", "@pricePerUnit"),
            ("totalPrice", "@totalPrice"),
            ("timestamp", "@timestamp{%F %T}"),
            ("", ""),  # white line
        ],
        formatters={"@timestamp": "datetime"},
    ),
)

# Update system color and alpha in the browser
# https://stackoverflow.com/questions/57577028/in-python-bokeh-how-to-modify-the-field-of-a-fill-color-interactively-without-js
# https://stackoverflow.com/questions/52955868/bokeh-how-to-change-glyph-attribute-in-js-callback
select_color.js_on_change(
    "value",
    CustomJS(
        args=dict(gn=graph.node_renderer),
        code="""
        let color = 'color_' + this.value.toLowerCase()
        let alpha = 'alpha_' + this.value.toLowerCase()

        gn.glyph.fill_color.field = color
        gn.glyph.fill_alpha.field = alpha
        gn.glyph.line_alpha.field = alpha

        gn.data_source.change.emit()
        """,
    ),
)

update_view_sector = CustomJS(
    args=dict(
        filter=filter_sector,
        checkboxes_system=checkboxes_system,
        f1=filter_complete,
        f2=filter_waypoints,
        f3=filter_charted,
        f4=filter_gate,
        f5=filter_observed,
        source_sector=source_sector,
        slider_marketplaces=slider_marketplaces,
        slider_shipyards=slider_shipyards,
        slider_interesting=slider_interesting,
    ),
    code="""
    // List active filters based on checkboxes_system.active
    let activeFilters = [f1, f2, f3, f4, f5].filter((_, idx) => checkboxes_system.active.includes(idx));
    
    // Build the new filter
    const booleans = [];
    for (let i = 0; i < filter.booleans.length; i++) {
        let allTrue = true;
        for (let f of activeFilters) {
            if (!f.booleans[i]) {
                allTrue = false;
                break;  // No need to continue checking if one is false
            }
        }
        if (allTrue) {
            let n = source_sector.data["marketplaces"][i];
            let min = slider_marketplaces.value[0]
            let max = slider_marketplaces.value[1]
            if (isNaN(n)) {
                n = 0;
            }
            if (n < min || n > max) {
                allTrue = false;
            }
        }
        if (allTrue) {
            let n = source_sector.data["shipyards"][i];
            let min = slider_shipyards.value[0]
            let max = slider_shipyards.value[1]
            if (isNaN(n)) {
                n = 0;
            }
            if (n < min || n > max) {
                allTrue = false;
            }
        }
        if (allTrue) {
            let n = source_sector.data["points_of_interest"][i];
            let min = slider_interesting.value[0]
            let max = slider_interesting.value[1]
            if (isNaN(n)) {
                n = 0;
            }
            if (n < min || n > max) {
                allTrue = false;
            }
        }
        booleans.push(allTrue ? true : false);
    }
        
    // Update the old filter
    filter.booleans = booleans;
    filter.change.emit();
    """,
)
checkboxes_system.js_on_change("active", update_view_sector)
slider_marketplaces.js_on_change("value", update_view_sector)
slider_shipyards.js_on_change("value", update_view_sector)
slider_interesting.js_on_change("value", update_view_sector)


update_view_connections = CustomJS(
    args=dict(
        source_sector=source_sector,
        source_connections=source_connections,
        filter_sector=filter_sector,
        filter_connections=filter_connections,
    ),
    code="""
    const booleans = [];
    let starts = source_connections.data["start"]
    let ends = source_connections.data["end"]
    for (let i = 0; i < starts.length; i++) {
        // Find the index of starts[i] and ends[i] in source_sector.data.index
        const s = source_sector.data["index"].indexOf(starts[i]);
        const e = source_sector.data["index"].indexOf(ends[i]);

        // Check if both systems are visible
        if (s !== -1 && e !== -1) {
            booleans.push(filter_sector.booleans[s] && filter_sector.booleans[e] ? true : false);
        } else {
            console.log("error: ${starts[i]} or ${ends[i]} not in source_sector!")
            booleans.push(false);  // If any index is not found, push 0
        }
    }

    // Update the old filter
    filter_connections.booleans = booleans;
    filter_connections.change.emit();
    """,
)
filter_sector.js_on_change("booleans", update_view_connections)

plot_system.add_tools(
    HoverTool(
        tooltips=[
            ("symbol", "@symbol"),
            ("type", "@type"),
            ("traits", "@traits"),
            ("", ""),  # white line
        ]
    )
)


def update_plot_system(attr, old, new):
    system = system_df(new)
    source_system.data = system.to_dict(orient="list")
    plot_system.title.text = f"System {new}"
    if len(system) == 0:
        return  # system has zero waypoints

    x0 = system["x"].min()
    x1 = system["x"].max()
    xpad = (x1 - x0) * 0.1
    plot_system.x_range.start = x0 - xpad
    plot_system.x_range.end = x1 + xpad

    y0 = system["y"].min()
    y1 = system["y"].max()
    ypad = (y1 - y0) * 0.1
    plot_system.y_range.start = y0 - ypad
    plot_system.y_range.end = y1 + ypad


select_system.on_change("value", update_plot_system)


button_center.js_on_event(
    "button_click",
    CustomJS(
        args=dict(
            source_sector=source_sector,
            select_system=select_system,
            plot_sector=plot_sector,
            # source_connections=source_connections,
            # filter_sector=filter_sector,
            # filter_connections=filter_connections,
        ),
        code="""
        let systemSymbol = select_system.value;
        let idx = source_sector.data["index"].indexOf(systemSymbol);
        if (idx == -1) {
          return;
        }
        
        // get system coordinates
        let x = source_sector.data["x"][idx];
        let y = source_sector.data["y"][idx];
        
        // get current zoom level
        let dx = (plot_sector.x_range.end - plot_sector.x_range.start) / 2;
        let dy = (plot_sector.y_range.end - plot_sector.y_range.start) / 2;
        
        // center the plot on the system
        plot_sector.x_range.start = x - dx;
        plot_sector.x_range.end = x + dx;
        plot_sector.y_range.start = y - dy;
        plot_sector.y_range.end = y + dy;
        """,
    ),
)


def update_select_tradegoods(attr, old, new):
    tradegoods = system_tradegoods(new)
    select_tradegoods.value = []
    select_tradegoods.options = tradegoods


select_system.on_change("value", update_select_tradegoods)

def update_plot_tradegoods(attr, old, new):
    # https://docs.bokeh.org/en/latest/docs/reference/models/glyphs/multi_line.html#multiline
    # https://docs.bokeh.org/en/latest/docs/user_guide/basic/lines.html#multiple-lines
    # https://stackoverflow.com/questions/55592101/plot-a-groupby-object-with-bokeh/55594762#55594762
    if len(new) == 0:
        return

    title = []
    data_prices = {
        key: [] for key in ["goods", "waypoint_symbols", "xs", "ys", "colors"]
    }
    data_tg_s = {key: [] for key in tg_keys}
    data_tg_p = {key: [] for key in tg_keys}
    system_symbol = select_system.value

    type_sell = []
    type_purchase = []
    if 0 in checkboxes_tradegoods.active:
        type_sell.append("IMPORT")
    if 1 in checkboxes_tradegoods.active:
        type_purchase.append("EXPORT")
    if 2 in checkboxes_tradegoods.active:
        type_sell.append("EXCHANGE")
        type_purchase.append("EXCHANGE")
    tradegoods, transactions = trade_dfs(new, system_symbol)
    for tradegood, df_tg in tradegoods.groupby("symbol"):
        if len(df_tg) == 0:
            continue
        ta1 = transactions[transactions["tradeSymbol"] == tradegood]

        title.append(tradegood)
        for waypoint_symbol, df_tg_wp in df_tg.groupby("waypointSymbol"):
            if len(df_tg_wp) == 0:
                continue
            ta2 = ta1[ta1["waypointSymbol"] == waypoint_symbol]

            type_tg = df_tg_wp["type"].to_list()[0]
            if type_tg in type_purchase:
                # line plots
                data_prices["goods"].append(tradegood)
                data_prices["waypoint_symbols"].append(waypoint_symbol)
                ta3 = ta2[ta2["type"] == "PURCHASE"]
                if len(ta3):
                    df = pd.concat(
                        [
                            df_tg_wp[["timestamp", "purchasePrice"]],
                            ta3[["timestamp", "pricePerUnit"]].rename(
                                columns={"pricePerUnit": "purchasePrice"}
                            ),
                        ],
                        axis=0,
                        ignore_index=True,
                    ).sort_values("timestamp")
                    data_prices["xs"].append(df["timestamp"].to_list())
                    data_prices["ys"].append(df["purchasePrice"].to_list())
                else:
                    data_prices["xs"].append(df_tg_wp["timestamp"].to_list())
                    data_prices["ys"].append(df_tg_wp["purchasePrice"].to_list())
                data_prices["colors"].append("green")
                # scatter plots
                for k, v in df_tg_wp.to_dict(orient="list").items():
                    data_tg_p[k].extend(v)

            if type_tg in type_sell:
                # line plots
                data_prices["goods"].append(tradegood)
                data_prices["waypoint_symbols"].append(waypoint_symbol)
                ta3 = ta2[ta2["type"] == "SELL"]
                if len(ta3):
                    df = pd.concat(
                        [
                            df_tg_wp[["timestamp", "sellPrice"]],
                            ta3[["timestamp", "pricePerUnit"]].rename(
                                columns={"pricePerUnit": "sellPrice"}
                            ),
                        ],
                        axis=0,
                        ignore_index=True,
                    ).sort_values("timestamp")
                    data_prices["xs"].append(df["timestamp"].to_list())
                    data_prices["ys"].append(df["sellPrice"].to_list())
                else:
                    data_prices["xs"].append(df_tg_wp["timestamp"].to_list())
                    data_prices["ys"].append(df_tg_wp["sellPrice"].to_list())
                data_prices["colors"].append("red")
                # scatter plots
                for k, v in df_tg_wp.to_dict(orient="list").items():
                    data_tg_s[k].extend(v)

    # line plots
    plot_tradegoods_price.data_source.data = data_prices
    plot_select_tradegoods_price.data_source.data = data_prices
    # scatter plots
    plot_tradegoods_tg_s.data_source.data = data_tg_s
    plot_tradegoods_tg_p.data_source.data = data_tg_p
    plot_tradegoods_ta.data_source.data = transactions.to_dict(orient="list")

    # selection plot updates
    plot_select_tradegoods.x_range.start = tradegoods["timestamp"].min()
    plot_select_tradegoods.x_range.end = tradegoods["timestamp"].max()

    # main plot updates
    x1 = tradegoods["timestamp"].max()
    x0 = x1 - np.timedelta64(1, "D")
    plot_tradegoods.x_range.start = x0
    plot_tradegoods.x_range.end = x1
    y0 = min(tradegoods["sellPrice"].min(), tradegoods["purchasePrice"].min())
    y1 = max(tradegoods["sellPrice"].max(), tradegoods["purchasePrice"].max())
    ypad = (y1 - y0) * 0.1
    plot_tradegoods.y_range.start = y0 - ypad
    plot_tradegoods.y_range.end = y1 + ypad
    plot_tradegoods.title.text = ", ".join(title) + f" in {system_symbol}"


select_tradegoods.on_change("value", update_plot_tradegoods)


def update_plot_tradegoods2(attr, old, new):
    # TODO: plot all and filter with CustomJS instead?
    update_plot_tradegoods("value", select_tradegoods.value, select_tradegoods.value)


checkboxes_tradegoods.on_change("active", update_plot_tradegoods2)


"""
Layout
"""
# JavaScript colors:
#   http://www.spacetoday.org/BoilerRoom/Colors.html
layout = column(
    row(
        column(
            plot_sector,
            row(
                # Div(text="Sector controls"),
                column(
                    select_color,
                    checkboxes_system,
                    # sizing_mode="scale_width",
                ),
                column(
                    slider_marketplaces,
                    slider_shipyards,
                    slider_interesting,
                    # sizing_mode="scale_width",
                ),
                sizing_mode="scale_width",
            ),
            # sizing_mode="scale_both",
            # background="grey",
        ),
        column(
            plot_system,
            # Div(text="System controls"),
            row(
                column(select_system, align="end"),
                column(button_center, align="end"),
            ),
            row(
                select_tradegoods,
                checkboxes_tradegoods,
            ),
            # sizing_mode="scale_both",
            # background="dimgrey",
        ),
    ),
    row(
        column(
            plot_tradegoods,
            plot_select_tradegoods,
            sizing_mode="scale_width",
        ),
        column(
            debug,
            # background="grey",
            # sizing_mode="scale_height",
        ),
        sizing_mode="scale_both",
        # background="grey",
    ),
    sizing_mode="scale_both",
    # background="silver",
)

curdoc().title = "SpaceTraders API"
curdoc().add_root(layout)
