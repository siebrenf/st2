import pandas as pd
from bokeh.models import Circle, GraphRenderer, MultiLine, StaticLayoutProvider
from psycopg import connect

pd.set_option("future.no_silent_downcasting", True)


def sector_df():
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
    df = pd.DataFrame(ret, columns=["symbol", "headquarters"])
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
    df.set_index("symbol", inplace=True)

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
