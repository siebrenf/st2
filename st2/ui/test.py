# https://stackoverflow.com/questions/78732362/how-to-upload-pandas-data-frames-fast-with-psycopg3
# https://gist.github.com/jakebrinkmann/de7fd185efe9a1f459946cf72def057e
# https://stackoverflow.com/questions/51144743/make-the-colour-and-marker-of-bokeh-plot-scatter-points-dependent-on-dataframe-v
# https://docs.bokeh.org/en/latest/docs/gallery.html
# https://matplotlib.org/stable/gallery/color/named_colors.html

# # Faction per system
# """
# SELECT "systemSymbol", STRING_AGG(DISTINCT faction, ', ') AS faction
# FROM waypoints
# GROUP BY "systemSymbol"
# """
#
#
# """
# SELECT
#     s.*,
#     w.faction AS faction,
#     w.traits AS traits
# FROM systems s
# LEFT JOIN (
#     SELECT
#         "systemSymbol",
#         STRING_AGG(DISTINCT faction, ', ') AS faction,
#         ARRAY_AGG(trait) AS traits
#     FROM
#         waypoints,
#         UNNEST(traits) AS trait
#     GROUP BY "systemSymbol"
# ) w
# ON s.symbol = w."systemSymbol"
# """
#
# """
# SELECT
#     s.*,
#     w.faction AS faction,
#     w.trait,
#     w.frequency
# FROM systems s
# LEFT JOIN (
#     SELECT
#         "systemSymbol",
#         STRING_AGG(DISTINCT faction, ', ') AS faction,
#         trait,
#         COUNT(*) AS frequency
#     FROM
#         waypoints,
#         UNNEST(traits) AS trait
#     GROUP BY "systemSymbol", trait
# ) w
# ON s.symbol = w."systemSymbol"
# """
#
# """
# SELECT
#     s.*,
#     w.faction,
#     w.traits_frequency
# FROM systems AS s
# LEFT JOIN (
#     SELECT
#         "systemSymbol",
#         STRING_AGG(DISTINCT faction, ', ') AS faction,
#         jsonb_object_agg(trait, frequency ORDER BY trait) AS traits_frequency
#     FROM (
#         SELECT
#             "systemSymbol",
#             trait,
#             COUNT(*) AS frequency,
#             faction
#         FROM
#             waypoints,
#             UNNEST(traits) AS trait
#         GROUP BY
#             "systemSymbol", faction, trait
#     )
#     GROUP BY
#         "systemSymbol"
# ) AS w
# ON s.symbol = w."systemSymbol"
# ORDER BY
#     "systemSymbol"
# """
#
# # add a column for each trait
# query_traits = []
# for trait in ["MARKETPLACE", "SHIPYARD", "UNCHARTED"]:  # sorted(TRAITS_WAYPOINT):
#     query_traits.append(
#         f"""COUNT(CASE WHEN trait = '{trait}' THEN 1 END) AS "{trait}" """
#     )
# query_traits = ",\n                    ".join(query_traits)

if __name__ == "__main__":
    import pandas.io.sql as sqlio
    from bokeh.plotting import curdoc, figure, show
    from psycopg import connect

    from st2.startup import db_server

    db_server()

    with connect("dbname=st2 user=postgres") as conn:
        df = sqlio.read_sql_query(
            "SELECT * FROM systems",
            conn,
            index_col="symbol",
            dtype={"type": "category"},
        )
        # with conn.cursor() as cur:
        #     cur.execute(
        #         """
        #         SELECT ARRAY_AGG(symbol) AS system_symbols,
        #                ARRAY_AGG(type) AS system_types,
        #                ARRAY_AGG(x) AS system_xs,
        #                ARRAY_AGG(y) AS system_ys
        #         FROM systems
        #         """
        #     )
        #     s, t, x, y = cur.fetchall()[0]

    # type2marker = {
    #     'BLACK_HOLE': "circle",
    #     'BLUE_STAR': "circle",
    #     'HYPERGIANT': "circle",
    #     "NEBULA": "hex",
    #     'NEUTRON_STAR': "circle",
    #     'ORANGE_STAR': "circle",
    #     'RED_STAR': "circle",
    #     'UNSTABLE': "circle_x",
    #     'WHITE_DWARF': "circle",
    #     'YOUNG_STAR': "circle",
    # }
    # markers = [type2marker[st] for st in t]
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
    # sizes = [type2size[st] for st in t]
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
    # colors = [type2color[st] for st in t]
    df["colors"] = df["type"].cat.rename_categories(type2color)
    df["sizes"] = df["type"].cat.rename_categories(type2size)

    curdoc().theme = "carbon"
    p = figure(
        width=1000,
        height=1000,
        x_axis_label="x",
        y_axis_label="y",
    )

    for t, group in df.groupby("type"):
        p.scatter(
            x="x",
            y="y",
            source=group,
            legend_label=t,
            size="sizes",
            fill_color="colors",
            line_color="dimgrey",
            line_width=0.5,
        )
    # p.scatter(
    #     x="x",
    #     y="y",
    #     source=df,
    #     legend_group="type",
    #     size="sizes",
    #     fill_color="colors",
    #     line_color='dimgrey',
    #     line_width=0.5,
    # )

    # p.scatter(
    #     x=x,
    #     y=y,
    #     size=sizes,
    #     legend_label="System types",
    #     fill_color=colors,
    #     line_color='dimgrey',
    #     line_width=0.5,
    # )
    p.legend.location = "top_right"
    p.legend.title = "System type"
    p.legend.click_policy = "hide"

    # show the results
    show(p)

    # # prepare some data
    # x = [1, 2, 3, 4, 5]
    # y = [6, 7, 2, 4, 5]
    #
    # # create a new plot with a title and axis labels
    # p = figure(title="Simple line example", x_axis_label="x", y_axis_label="y")
    #
    # # add a line renderer with legend and line thickness
    # p.line(x, y, legend_label="Temp.", line_width=2)
    #
    # # show the results
    # show(p)
