import math

import matplotlib.pyplot as plt

from st2.system import System
from st2.ui.utils import system_df


def plot_system(system_symbol, paths=None, annotate=True):
    df = system_df(system_symbol)
    fig, ax = plt.subplots()
    # df.plot(
    #     kind="scatter", x="x", y="y", s="size", c="color", label="type", ax=ax
    # )  # marker="marker",
    for g in df.groupby("type"):
        g[1].groupby("type").plot(
            kind="scatter", x="x", y="y", s="size", c="color", label=g[0], ax=ax
        )  # marker="marker",

    # draw one or more paths through the system
    system = System(system_symbol)
    if paths is None:
        paths = []
    for path in paths:
        for i in range(1, len(path)):
            n0 = path[i - 1]
            n1 = path[i]
            md0 = system.waypoints[n0]
            md1 = system.waypoints[n1]
            ax.annotate(
                text="",
                xytext=(md0["x"], md0["y"]),
                xy=(md1["x"], md1["y"]),
                xycoords="data",
                arrowprops=dict(
                    arrowstyle="->",
                    linestyle="--",
                    # connectionstyle="arc3,rad=0.1",
                    color="blue",
                    zorder=-2,
                ),
                zorder=-1,
            )

    # label each market, and highlight orbiters & shipyards
    if annotate:
        xmin = 1e9
        xmax = -1e9
        ymin = 1e9
        ymax = -1e9
        for md in system.waypoints.values():
            xmin = min(xmin, md["x"])
            xmax = max(xmax, md["x"])
            ymin = min(ymin, md["y"])
            ymax = max(ymax, md["y"])
        dx = abs(xmax - xmin)
        dy = abs(ymax - ymin)
        r = ((dx + dy) / 2) * 0.02
        seen = {None}
        for wp in system.markets.keys():
            md = system.waypoints[wp]
            label = wp.rsplit("-", 1)[1]
            if md["orbits"]:
                label = md["type"][0] + ":" + label
            if wp in system.shipyards:
                label = label + "(S)"
            xy = (md["x"], md["y"])
            xytext = None
            n = 1
            while xytext in seen:
                xytext = (
                    md["x"] + r * math.cos(2 * math.pi * n / 6),
                    md["y"] + r * math.sin(2 * math.pi * n / 6),
                )
                n += 1
            seen.add(xytext)
            ax.annotate(
                text=label,
                xytext=xytext,
                xy=xy,
                xycoords="data",
                arrowprops=dict(
                    arrowstyle="->",
                    connectionstyle="arc3,rad=0.1",
                    zorder=-2,
                ),
                zorder=-1,
            )

    ax.set_title(df.at[0, "systemSymbol"])
    # https://stackoverflow.com/questions/4700614/how-to-put-the-legend-outside-the-plot
    handles, labels = ax.get_legend_handles_labels()
    # sort both labels and handles by labels
    if handles:
        labels, handles = zip(*sorted(zip(labels, handles), key=lambda t: t[0]))
        ax.legend(handles, labels, loc="center left", bbox_to_anchor=(1, 0.5))
        fig.subplots_adjust(right=0.7)
    plt.show()


if __name__ == "__main__":
    import os

    from psycopg import connect

    from st2.startup import game_server

    game_server()
    agent_symbol = os.environ["ST_AGENT_SYMBOL"]

    with connect("dbname=st2 user=postgres") as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT "headquarters" FROM agents_public
            WHERE symbol = %s
            """,
            [agent_symbol],
        )
        hq = cur.fetchone()[0]
    system_symbol = hq.rsplit("-", 1)[0]
    plot_system(system_symbol)
