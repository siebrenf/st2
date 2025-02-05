# https://stackoverflow.com/questions/78732362/how-to-upload-pandas-data-frames-fast-with-psycopg3
# https://gist.github.com/jakebrinkmann/de7fd185efe9a1f459946cf72def057e
# https://stackoverflow.com/questions/51144743/make-the-colour-and-marker-of-bokeh-plot-scatter-points-dependent-on-dataframe-v
# https://docs.bokeh.org/en/latest/docs/gallery.html
# https://matplotlib.org/stable/gallery/color/named_colors.html
# https://docs.bokeh.org/en/latest/docs/gallery.html
# https://docs.bokeh.org/en/latest/docs/user_guide/server/app.html#building-applications

from bokeh.layouts import column, row
from bokeh.models import (
    AutocompleteInput,
    BooleanFilter,
    CDSView,
    CheckboxGroup,
    ColumnDataSource,
    CustomJS,
    Div,
    GraphRenderer,
    HoverTool,
    MultiLine,
    NodesAndLinkedEdges,
    NodesOnly,
    RangeSlider,
    Scatter,
    Select,
    StaticLayoutProvider,
    TapTool,
)
from bokeh.plotting import curdoc, figure, show

from st2.ui.utils import connection_df, hq_df, sector_df

"""
Variables
"""
sector = sector_df()
source_sector = ColumnDataSource(sector)
hqs = hq_df()
connections = connection_df()
source_connections = ColumnDataSource(connections)

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
    title="Select a system in the Sector plot, or Search a system and press Enter:",
    search_strategy="includes",
    value="X1-",
    completions=sector.index.to_list(),
    # sizing_mode="scale_both",
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

"""
Other
"""
# Can print stuff here from CustomJS callbacks
debug = Div(
    stylesheets=[":host { white-space: pre; }"],
    text="Debug window",
    sizing_mode="scale_both",
)

"""
Plot sector
"""
plot_sector = figure(
    title="Sector X1",
    # height=800,
    # width=1600,
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


"""
Layout
"""
if __name__ == "__main__":
    # JavaScript colors:
    #   http://www.spacetoday.org/BoilerRoom/Colors.html
    layout = row(
        column(
            plot_sector,
            select_system,
            # sizing_mode="scale_both",
            background="grey",
        ),
        column(
            select_color,
            checkboxes_system,
            slider_marketplaces,
            slider_shipyards,
            slider_interesting,
            # sizing_mode="scale_both",
            background="silver",
        ),
        # debug,
        sizing_mode="scale_both",
        background="dimgrey",
    )

    curdoc().title = "SpaceTraders API"
    curdoc().theme = "dark_minimal"
    curdoc().add_root(layout)

    show(layout)
