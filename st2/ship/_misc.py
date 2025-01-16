from psycopg import connect
from psycopg.types.json import Jsonb


def chart(self):
    """Command a ship to chart the waypoint at its current location."""
    data = self.request.post(f'my/ships/{self["symbol"]}/chart')["data"]["waypoint"]
    with connect("dbname=st2 user=postgres") as conn:
        with conn.cursor() as cur:
            # cur.execute(
            #     """
            #     INSERT INTO waypoints
            #     ("symbol", "systemSymbol", "type", "x", "y", "orbits",
            #      "orbitals", "traits", "chart", "faction", "isUnderConstruction")
            #     VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            #     ON CONFLICT ("symbol") DO UPDATE
            #     SET "traits" = EXCLUDED."traits",
            #         "chart" = EXCLUDED."chart",
            #         "faction" = EXCLUDED."faction",
            #         "isUnderConstruction" = EXCLUDED."isUnderConstruction"
            #     """,
            #     (
            #         data["symbol"],
            #         data["systemSymbol"],
            #         data["type"],
            #         data["x"],
            #         data["y"],
            #         data.get("orbits"),
            #         [o["symbol"] for o in data["orbitals"]],
            #         [t["symbol"] for t in data["traits"]],
            #         Jsonb(data.get("chart")),
            #         data.get("faction", {}).get("symbol"),
            #         data["isUnderConstruction"],
            #     ),
            # )
            traits = [t["symbol"] for t in data["traits"]]
            chart = Jsonb(data.get("chart"))
            faction = data.get("faction", {}).get("symbol")
            cur.execute(
                """
                UPDATE waypoints
                SET traits = %s,
                    chart = %s,
                    faction = %s,
                    isUnderConstruction = %s
                WHERE symbol = %s
                """,
                (
                    traits,
                    chart,
                    faction,
                    data["isUnderConstruction"],
                    data["symbol"],
                ),
            )
    return data
