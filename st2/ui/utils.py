import math

import numpy as np
import pandas as pd
from bokeh.layouts import column
from bokeh.models import (
    Circle,
    Div,
    GraphRenderer,
    HoverTool,
    Legend,
    MultiLine,
    RangeTool,
    StaticLayoutProvider,
)
from bokeh.plotting import figure
from psycopg import connect

pd.set_option("future.no_silent_downcasting", True)


def sector_df():
    params = []

    # count the number of asteroids
    asteroids = """COUNT(CASE WHEN type = ANY(%s) THEN 1 END) AS asteroids,"""
    params.append(["ASTEROID", "ASTEROID_FIELD", "ENGINEERED_ASTEROID"])

    # count the number of potential markets in each system
    points_of_interest = (
        "COUNT(CASE WHEN type = ANY(%s) THEN 1 END) AS points_of_interest,"
    )
    params.append(
        [
            "ARTIFICIAL_GRAVITY_WELL",
            "ASTEROID_BASE",
            "ENGINEERED_ASTEROID",
            "FUEL_STATION",
            "GRAVITY_WELL",
            # "JUMP_GATE",
            "MOON",
            "ORBITAL_STATION",
            "PLANET",
        ]
    )

    # count the number of charted waypoints in each system
    charted = "COUNT(CASE WHEN traits != %s THEN 1 END) AS charted, "
    params.append(["UNCHARTED"])

    # count the number of extractable deposits in each system
    deposits = ""
    for deposit in [
        "MINERAL_DEPOSITS",
        "COMMON_METAL_DEPOSITS",
        "PRECIOUS_METAL_DEPOSITS",
        "RARE_METAL_DEPOSITS",
    ]:
        name = deposit.rsplit("_", 1)[0].lower()
        deposits += f"COUNT(CASE WHEN type = ANY(%s) AND trait = '{deposit}' THEN 1 END) AS {name}s, "
        params.append(["ASTEROID", "ASTEROID_FIELD", "ENGINEERED_ASTEROID"])

    # list faction & traits per system
    query = f"""
            SELECT 
                s.symbol,
                s.type,
                s.x,
                s.y,
                CASE 
                    WHEN mg."systemSymbol" IS NOT NULL THEN TRUE
                    ELSE FALSE
                END AS observed,
                n.faction,
                n.total_waypoints,
                n.incomplete,
                n.asteroids,
                n.points_of_interest,
                n.charted,
                n.jump_gates,
                n.gas_giants,
                w.minerals,
                w.common_metals,
                w.rare_metals,
                w.precious_metals,
                w.uncharted,
                w.marketplaces,
                w.shipyards
            FROM systems AS s
            LEFT JOIN (
                SELECT
                    DISTINCT "systemSymbol" 
                FROM 
                    market_tradegoods
            ) AS mg
            ON 
                s.symbol = mg."systemSymbol"
            LEFT JOIN (
                SELECT 
                    "systemSymbol",
                    STRING_AGG(DISTINCT faction, ', ') AS faction,
                    COUNT(symbol) AS total_waypoints,
                    COUNT(CASE WHEN traits IS NULL THEN 1 END) AS incomplete,
                    {asteroids}
                    {points_of_interest}
                    {charted}
                    COUNT(CASE WHEN type = 'JUMP_GATE' THEN 1 END) AS jump_gates,
                    COUNT(CASE WHEN type = 'GAS_GIANT' THEN 1 END) AS gas_giants
                FROM 
                    waypoints
                GROUP BY 
                    "systemSymbol"
            ) AS n
            ON s.symbol = n."systemSymbol"
            LEFT JOIN (
                SELECT 
                    "systemSymbol",
                    {deposits}
                    COUNT(CASE WHEN trait = 'UNCHARTED' THEN 1 END) AS uncharted,
                    COUNT(CASE WHEN trait = 'MARKETPLACE' THEN 1 END) AS marketplaces,
                    COUNT(CASE WHEN trait = 'SHIPYARD' THEN 1 END) AS shipyards
                FROM 
                    waypoints,
                    UNNEST(traits) AS trait
                GROUP BY 
                    "systemSymbol"
            ) AS w
            ON s.symbol = w."systemSymbol"
            ORDER BY s.symbol
            """
    with connect("dbname=st2 user=postgres") as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            ret = cur.fetchall()
    # convert to a pandas dataframe for quick (re)grouping later
    df = pd.DataFrame(
        ret,
        columns=[
            "index",  # for graph plotting
            "type",
            "x",
            "y",
            "observed",
            "faction",
            "total_waypoints",
            "incomplete",
            "asteroids",
            "points_of_interest",
            "charted",
            "jump_gates",
            "gas_giants",
            "minerals",
            "common_metals",
            "rare_metals",
            "precious_metals",
            "uncharted",
            "marketplaces",
            "shipyards",
        ],
    )
    df.set_index("index", inplace=True)
    # fix values for systems with zero waypoints
    df.loc[
        df["total_waypoints"].isna(),
        [
            "total_waypoints",
            "incomplete",
            "asteroids",
            "points_of_interest",
            "charted",
            "jump_gates",
            "gas_giants",
            "minerals",
            "common_metals",
            "rare_metals",
            "precious_metals",
            "uncharted",
            "marketplaces",
            "shipyards",
        ],
    ] = 0
    # df.drop(columns=["_1", "_2"], inplace=True)
    # df["total_waypoints"] = df["total_waypoints"].fillna(0)
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
    # df["color"] = df["color_type"]

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
    df["alpha_type"] = 1.0

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
    df["alpha_faction"] = df["faction"].apply(lambda v: 1.0 if v != "None" else 0.3)

    return df


def hq_df():
    with connect("dbname=st2 user=postgres") as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT symbol, headquarters
                FROM factions
                """,
            )
            ret = cur.fetchall()
    df = pd.DataFrame(ret, columns=["index", "headquarters"])
    # df = df.dropna().set_index("symbol")
    return df


def system_df(system_symbol):
    query = """
            SELECT * 
            FROM waypoints
            WHERE "systemSymbol" = %s
            """
    params = [system_symbol]
    with connect("dbname=st2 user=postgres") as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            ret = cur.fetchall()
    df = pd.DataFrame(
        ret,
        columns=[
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
        ],
    )
    # df.set_index("symbol", inplace=True)

    type2marker = {
        "ARTIFICIAL_GRAVITY_WELL": "triangle_pin",
        "ASTEROID": "circle_dot",  # small
        "ASTEROID_BASE": "circle_y",
        "ASTEROID_FIELD": "circle_x",
        "DEBRIS_FIELD": "diamond",
        "ENGINEERED_ASTEROID": "circle_dot",
        "FUEL_STATION": "plus",
        "GAS_GIANT": "circle",  # large
        "GRAVITY_WELL": "triangle_pin",
        "JUMP_GATE": "hex",
        "MOON": "circle_dot",  # small
        "NEBULA": "circle",  # large
        "ORBITAL_STATION": "plus",
        "PLANET": "circle",  # large
    }
    df["marker"] = df["type"].replace(type2marker)

    n = 1.3
    type2size = {
        "ARTIFICIAL_GRAVITY_WELL": 5 * n,
        "ASTEROID": 3 * n,
        "ASTEROID_BASE": 6 * n,
        "ASTEROID_FIELD": 9 * n,
        "DEBRIS_FIELD": 9 * n,
        "ENGINEERED_ASTEROID": 4 * n,
        "FUEL_STATION": 6 * n,
        "GAS_GIANT": 12 * n,
        "GRAVITY_WELL": 6 * n,
        "JUMP_GATE": 6 * n,
        "MOON": 5 * n,
        "NEBULA": 12 * n,
        "ORBITAL_STATION": 6 * n,
        "PLANET": 7 * n,
    }
    df["size"] = df["type"].replace(type2size).infer_objects(copy=False)

    # type2alpha = {
    #     "ARTIFICIAL_GRAVITY_WELL": 1.0,
    #     "ASTEROID": 1.0,
    #     "ASTEROID_BASE": 1.0,
    #     "ASTEROID_FIELD": 0.5,
    #     "DEBRIS_FIELD": 1.0,
    #     "ENGINEERED_ASTEROID": 1.0,
    #     "FUEL_STATION": 1.0,
    #     "GAS_GIANT": 0.5,
    #     "GRAVITY_WELL": 1.0,
    #     "JUMP_GATE": 1.0,
    #     "MOON": 1.0,
    #     "NEBULA": 0.5,
    #     "ORBITAL_STATION": 1.0,
    #     "PLANET": 0.8,
    # }
    # df["alpha"] = df["type"].replace(type2alpha).infer_objects(copy=False)

    type2color = {
        "ARTIFICIAL_GRAVITY_WELL": "blue",
        "ASTEROID": "brown",
        "ASTEROID_BASE": "blue",
        "ASTEROID_FIELD": "brown",
        "DEBRIS_FIELD": "brown",
        "ENGINEERED_ASTEROID": "brown",
        "FUEL_STATION": "purple",
        "GAS_GIANT": "yellow",
        "GRAVITY_WELL": "blue",
        "JUMP_GATE": "orange",
        "MOON": "darkgrey",
        "NEBULA": "blue",
        "ORBITAL_STATION": "blue",
        "PLANET": "green",
    }
    df["color"] = df["type"].replace(type2color)

    return df


def connection_df():
    with connect("dbname=st2 user=postgres") as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    j."systemSymbol" AS jump_gate_system,
                    w."systemSymbol" AS connected_system
                FROM
                    jump_gates j
                LEFT JOIN
                    waypoints w ON w.symbol = ANY(j.connections)
                """
            )
            ret = cur.fetchall()
    connections = pd.DataFrame(ret, columns=["start", "end"])
    return connections


def sector_graph(df, connections):
    # TODO: plot nodes (including colors)
    graph = GraphRenderer(name="sector")
    graph.node_renderer.glyph = Circle()  # dont plot nodes
    graph.edge_renderer.glyph = MultiLine(
        line_color="goldenrod",
        line_alpha=0.3,
        line_width=1,
        line_dash="dotted",
        line_dash_offset=1,
    )

    # nodes
    graph.node_renderer.data_source.data = dict(index=df.index.to_list())
    graph.layout_provider = StaticLayoutProvider(
        graph_layout=df[["x", "y"]].apply(list, axis=1).to_dict(),
    )

    # edges
    edges = connections[
        (connections["start"].isin(df.index)) & (connections["end"].isin(df.index))
    ]
    graph.edge_renderer.data_source.data = dict(
        start=edges["start"],
        end=edges["end"],
    )

    return graph


def connection_graph():
    query = """
            SELECT
                j."systemSymbol" AS jump_gate_system,
                w."systemSymbol" AS connected_system
            FROM
                jump_gates j
            LEFT JOIN
                waypoints w ON w.symbol = ANY(j.connections)
            """
    with connect("dbname=st2 user=postgres") as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            ret = cur.fetchall()
    edges = pd.DataFrame(ret, columns=["n1", "n2"])

    query = """
            WITH 
            edges AS (
                SELECT 
                    j."systemSymbol" AS jump_gate_system,
                    w."systemSymbol" AS connected_system
                FROM 
                    jump_gates j
                LEFT JOIN 
                    waypoints w ON w.symbol = ANY(j.connections)
            ),
            gate_system AS (
                SELECT jump_gate_system
                FROM edges
                UNION
                SELECT connected_system
                FROM edges
            ),
            system_coordinates AS (
                SELECT 
                    s.symbol,
                    s.x,
                    s.y
                FROM 
                    systems s
            )
            SELECT 
                gs.jump_gate_system,
                sc.x,
                sc.y
            FROM 
                gate_system gs
            JOIN 
                system_coordinates sc ON sc.symbol = gs.jump_gate_system
            """
    nodes = {}
    with connect("dbname=st2 user=postgres") as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            for symbol, x, y in cur.fetchall():
                nodes[symbol] = (x, y)

    graph = GraphRenderer(name="connections")

    # nodes
    graph.node_renderer.glyph = Circle()  # dont plot nodes
    graph.node_renderer.data_source.data = dict(index=list(nodes))

    # node coordinates
    graph.layout_provider = StaticLayoutProvider(graph_layout=nodes)

    # edges
    graph.edge_renderer.glyph = MultiLine(
        line_color="goldenrod",
        line_alpha=0.3,
        line_width=1,
        line_dash="dotted",
        line_dash_offset=1,
    )
    graph.edge_renderer.data_source.data = dict(
        start=edges["n1"],
        end=edges["n2"],
    )

    return graph


def trade_dfs(goods: str or list = None, systems: str or list = None):
    if goods is None and systems is None:
        raise ValueError("Must provide either good(s) or system(s)")
    n = 0
    operators = ["WHERE", "AND"]
    params = []
    query1 = """SELECT * FROM market_tradegoods """
    query2 = """SELECT * FROM market_transactions """
    if isinstance(goods, str):
        query1 += f"""{operators[n]} "symbol" = %s """
        query2 += f"""{operators[n]} "tradeSymbol" = %s """
        params.append(goods)
        n += 1
    elif isinstance(goods, list):
        query1 += f"""{operators[n]} "symbol" = ANY(%s) """
        query2 += f"""{operators[n]} "tradeSymbol" = ANY(%s) """
        params.append(goods)
        n += 1
    elif goods is not None:
        raise TypeError(f"goods must be a string or list")
    if isinstance(systems, str):
        query1 += f"""{operators[n]} "systemSymbol" = %s """
        query2 += f"""{operators[n]} "systemSymbol" = %s """
        params.append(systems)
        n += 1
    elif isinstance(systems, list):
        query1 += f"""{operators[n]} "systemSymbol" = ANY(%s) """
        query2 += f"""{operators[n]} "systemSymbol" = ANY(%s) """
        params.append(systems)
        n += 1
    elif systems is not None:
        raise TypeError(f"systems must be a string or list")
    with connect("dbname=st2 user=postgres") as conn:
        tradegoods = pd.DataFrame(
            conn.execute(query1, params).fetchall(),
            columns=[
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
            ],
        )
    #     tradegoods = pd.read_sql_query(query, conn, params=params)
    tradegoods["activity"] = tradegoods["activity"].fillna("N/A")  # for exchange goods
    activity2marker = {
        "N/A": "y",
        "RESTRICTED": "dot",
        "WEAK": "cross",
        "GROWING": "x",
        "STRONG": "asterisk",
    }
    tradegoods["marker"] = tradegoods["activity"].replace(activity2marker)
    supply2color = {
        "SCARCE": "red",
        "LIMITED": "pink",
        "MODERATE": "grey",
        "HIGH": "lightblue",
        "ABUNDANT": "blue",
    }
    tradegoods["color"] = tradegoods["supply"].replace(supply2color)

    with connect("dbname=st2 user=postgres") as conn:
        transactions = pd.DataFrame(
            conn.execute(query2, params).fetchall(),
            columns=[
                "waypointSymbol",
                "systemSymbol",
                "shipSymbol",
                "tradeSymbol",
                "type",
                "units",
                "pricePerUnit",
                "totalPrice",
                "timestamp",
            ],
        )
        # transactions = pd.read_sql_query(query, conn, params=params)
    type2color = {
        "SELL": "red",
        "PURCHASE": "green",
    }
    transactions["color"] = transactions["type"].replace(type2color)
    return tradegoods, transactions


def plot_markets(goods: str or list, systems: str or list):
    tradegoods, transactions = trade_dfs(goods, systems)
    if len(tradegoods) == 0:
        return column(
            Div(text=f"{goods} not observed in {systems}."), sizing_mode="scale_both"
        )

    # main figure
    end = tradegoods["timestamp"][len(tradegoods) - 1]
    start = end - np.timedelta64(1, "D")
    # width = 1700
    p = figure(
        # height=300,
        # width=width,
        x_range=(start, end),
        x_axis_type="datetime",
        x_axis_location="above",
        tools="pan,wheel_zoom,reset",
        active_scroll="wheel_zoom",
        sizing_mode="scale_both",
    )
    p.title.text_font = "Courier New"
    p.axis.axis_label_text_font = "Courier New"
    p.axis.major_label_text_font = "Courier New"
    p.yaxis.axis_label = "Prices"

    # complete time range for overview
    select = figure(
        title="Drag the middle and edges of the selection box to change the range above",
        height=100,
        # width=width,
        y_range=p.y_range,
        x_axis_type="datetime",
        y_axis_type=None,
        tools="",
        toolbar_location=None,
        sizing_mode="scale_width",
    )
    select.title.text_font = "Courier New"
    select.axis.axis_label_text_font = "Courier New"
    select.axis.major_label_text_font = "Courier New"
    select.ygrid.grid_line_color = None

    # range selection tool
    range_tool = RangeTool(x_range=p.x_range, start_gesture="pan")
    range_tool.overlay.fill_color = "navy"
    range_tool.overlay.fill_alpha = 0.2
    select.add_tools(range_tool)

    # main figure content
    hover_plots = {"transactions": [], "tradeGoods": []}
    legend_plots = {
        "sellPrice": [],
        "purchasePrice": [],
    }
    legend_text = {"\nWaypoints:": []}
    for good in sorted(tradegoods["symbol"].unique()):
        for wp in sorted(tradegoods["waypointSymbol"].unique()):
            ta = transactions[
                (transactions["waypointSymbol"] == wp)
                & (transactions["tradeSymbol"] == good)
            ]
            tg = tradegoods[
                (tradegoods["waypointSymbol"] == wp) & (tradegoods["symbol"] == good)
            ]

            # merge the transactions & tradeGoods so the line plot contains all observed events
            df = pd.concat(
                [
                    ta[ta["type"] == "PURCHASE"][["timestamp", "pricePerUnit"]].rename(
                        columns={"pricePerUnit": "purchasePrice"}
                    ),
                    tg[["timestamp", "purchasePrice"]],
                ],
                ignore_index=True,
            ).sort_values("timestamp")
            plot = p.line("timestamp", "purchasePrice", color="green", source=df)
            select.line("timestamp", "purchasePrice", color="green", source=df)
            legend_plots["purchasePrice"].append(plot)

            # merge the transactions & tradeGoods so the line plot contains all observed events
            df = pd.concat(
                [
                    ta[ta["type"] == "SELL"][["timestamp", "pricePerUnit"]].rename(
                        columns={"pricePerUnit": "sellPrice"}
                    ),
                    tg[["timestamp", "sellPrice"]],
                ],
                ignore_index=True,
            ).sort_values("timestamp")
            plot = p.line("timestamp", "sellPrice", color="red", source=df)
            select.line("timestamp", "sellPrice", color="red", source=df)
            legend_plots["sellPrice"].append(plot)

            # plot tradeGoods updates
            plot = p.scatter(
                "timestamp",
                "sellPrice",
                alpha=0.5,
                size=10,
                marker="marker",
                color="color",
                source=tg,
            )
            hover_plots["tradeGoods"].append(plot)
            plot = p.scatter(
                "timestamp",
                "purchasePrice",
                alpha=0.5,
                size=10,
                marker="marker",
                color="color",
                source=tg,
            )
            hover_plots["tradeGoods"].append(plot)

            # plot transactions TODO: scale/max sizes
            plot = p.scatter(
                "timestamp",
                "pricePerUnit",
                alpha=0.5,
                size="units",
                color="color",
                source=ta,
            )
            hover_plots["transactions"].append(plot)

            # legend: mark the waypoint and its type (IMPORT/EXPORT/EXCHANGE)
            if len(tg):
                key = f'{wp: <10} {good} {tg["type"].head(1).to_list()[0]}'
                legend_text[key] = []

    # legend title
    if isinstance(goods, str):
        goods = [goods]
    if isinstance(systems, str):
        systems = [systems]
    title = f"{', '.join(goods)} @ {', '.join(systems)}"
    # legend width
    n_wps = len(legend_plots["purchasePrice"])
    n_cols = 1 + math.ceil((n_wps - 5) / 10)
    legend = Legend(
        title=title,
        items=[i for i in legend_plots.items()]
        + [i for i in hover_plots.items()]
        + [i for i in legend_text.items()],
        location="top",
        title_text_font="Courier New",
        label_text_font="Courier New",
        title_text_font_size="8pt",
        label_text_font_size="8pt",
        ncols=n_cols,
    )
    p.add_layout(legend, "right")

    p.add_tools(
        HoverTool(
            renderers=hover_plots["transactions"],
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
        HoverTool(
            renderers=hover_plots["tradeGoods"],
            tooltips=[
                ("Tradegood", ""),
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
    )
    return column(p, select, sizing_mode="scale_both")


def system_tradegoods(system_symbol):
    query = """
        WITH
        system_markets AS (
            SELECT *
            FROM markets
            WHERE "systemSymbol" = %s
        )
        SELECT DISTINCT value
        FROM (
            SELECT unnest("imports") AS value FROM system_markets
            UNION ALL
            SELECT unnest("exports") AS value FROM system_markets
            UNION ALL
            SELECT unnest("exchange") AS value FROM system_markets
        )
    """
    params = [system_symbol]
    with connect("dbname=st2 user=postgres") as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            return sorted(row[0] for row in cur.fetchall())
