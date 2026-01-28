import matplotlib.pyplot as plt

from st2.ui.utils import system_df


def plot_system(system_symbol):
    df = system_df(system_symbol)
    fig, ax = plt.subplots()
    df.plot(
        kind="scatter", x="x", y="y", s="size", c="color", ax=ax
    )  # marker="marker",
    ax.set_title(df.at[0, "systemSymbol"])
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
