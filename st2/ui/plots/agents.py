from matplotlib import pyplot as plt

from st2.db import get_table


def plot_agents(agents=None):
    data = {}
    for row in get_table("agents_public", as_dict=True):
        if row["credits"] <= 175_000:
            continue
        if row["symbol"] not in data:
            data[row["symbol"]] = {"x": [], "y": [], "s": []}
        data[row["symbol"]]["y"].append(row["credits"])
        data[row["symbol"]]["x"].append(row["timestamp"])
        data[row["symbol"]]["s"].append(row["shipCount"])

    for k, v in data.items():
        if agents and k not in agents:
            continue
        plt.plot(v["x"], v["y"], label=k)
        plt.scatter(v["x"], v["y"], s=[i / 100 for i in v["s"]])
    plt.legend()
    plt.show()


if __name__ == "__main__":
    from st2.startup import game_server

    game_server()
    plot_agents()
