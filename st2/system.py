from operator import itemgetter

import networkx as nx
import numpy as np
from networkx.algorithms.approximation import traveling_salesman_problem
from psycopg import connect
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from scipy.spatial.distance import cdist

from st2 import time
from st2.logging import logger
from st2.pathing.utils import dist

DEBUG = False


class System:

    # lazy attributes (loaded when called)
    # listed here for code autocompletion
    waypoints: dict = None
    gate: dict = None
    markets: dict = None
    shipyards: dict = None
    uncharted: dict = None
    graph: nx.Graph = None

    def __init__(self, symbol, request=None, priority=None):
        self.symbol = symbol
        self.request = None
        if request:
            self.request = request.copy()
        if priority:
            self.request.priority = priority

    # lazy attributes
    def __getattribute__(self, name):
        val = super(System, self).__getattribute__(name)
        if val is not None:
            return val

        # if the attribute is None/empty, check if it is a lazy attribute
        match name:
            case "waypoints":
                if DEBUG:
                    logger.debug(f"Loading {name}")
                with connect("dbname=st2 user=postgres", row_factory=dict_row) as conn:
                    with conn.cursor() as cur:
                        # ensure waypoints are in the database
                        query = "SELECT * FROM systems WHERE symbol = %s"
                        params = [self.symbol]
                        data = cur.execute(query, params).fetchone()
                        if data is None:
                            self._get_system(cur)

                        # ensure waypoint details are in the database
                        query = 'SELECT * FROM waypoints WHERE "systemSymbol" = %s  ORDER BY symbol'
                        data = cur.execute(query, params).fetchall()
                        if None in [wp.get("traits") for wp in data]:
                            self._get_waypoints(cur)
                            data = cur.execute(query, params).fetchall()
                val = {}
                for wp in data:
                    val[wp["symbol"]] = wp
                setattr(self, name, val)

            case "gate":
                if DEBUG:
                    logger.debug(f"Loading {name}")
                _ = self.waypoints  # load waypoints into DB
                with connect("dbname=st2 user=postgres", row_factory=dict_row) as conn:
                    with conn.cursor() as cur:
                        ret = cur.execute(
                            """
                            SELECT * 
                            FROM "waypoints"
                            WHERE "systemSymbol" = %s 
                            AND "type" = %s
                            ORDER BY "symbol"
                            """,
                            (self.symbol, "JUMP_GATE"),
                        ).fetchone()
                        if ret is None:
                            val = None
                            logger.warning(f"System {self.symbol} has no JUMP-GATE!")
                        elif ret["traits"] == ["UNCHARTED"]:
                            val = {
                                "symbol": ret["symbol"],
                                "systemSymbol": ret["systemSymbol"],
                                "connections": None,
                            }
                            logger.warning(
                                f"System {self.symbol} JUMP-GATE is UNCHARTED!"
                            )
                        else:
                            val = cur.execute(
                                """
                                SELECT * 
                                FROM "jump_gates"
                                WHERE "systemSymbol" = %s 
                                """,
                                (self.symbol,),
                            ).fetchone()
                setattr(self, name, val)

            case "shipyards":
                if DEBUG:
                    logger.debug(f"Loading {name}")
                _ = self.waypoints  # load waypoints into DB
                with connect("dbname=st2 user=postgres", row_factory=dict_row) as conn:
                    with conn.cursor() as cur:
                        ret = cur.execute(
                            """
                            SELECT * 
                            FROM "shipyards"
                            WHERE "systemSymbol" = %s 
                            ORDER BY "symbol"
                            """,
                            (self.symbol,),
                        ).fetchall()
                if ret:
                    val = {wp["symbol"]: wp for wp in ret}
                else:
                    val = {}
                    logger.warning(f"System {self.symbol} has no SHIPYARD!")
                setattr(self, name, val)

            case "markets":
                if DEBUG:
                    logger.debug(f"Loading {name}")
                _ = self.waypoints  # load waypoints into DB
                with connect("dbname=st2 user=postgres", row_factory=dict_row) as conn:
                    with conn.cursor() as cur:
                        ret = cur.execute(
                            """
                            SELECT * 
                            FROM "markets"
                            WHERE "systemSymbol" = %s 
                            ORDER BY "symbol"
                            """,
                            (self.symbol,),
                        ).fetchall()
                if ret:
                    val = {wp["symbol"]: wp for wp in ret}
                else:
                    val = {}
                    logger.warning(f"System {self.symbol} has no MARKET!")
                setattr(self, name, val)

            case "uncharted":
                if DEBUG:
                    logger.debug(f"Loading {name}")
                _ = self.waypoints  # load waypoints into DB
                with connect("dbname=st2 user=postgres", row_factory=dict_row) as conn:
                    with conn.cursor() as cur:
                        ret = cur.execute(
                            """
                            SELECT * 
                            FROM "waypoints"
                            WHERE "systemSymbol" = %s 
                            AND %s = ANY(traits)
                            ORDER BY "symbol"
                            """,
                            (self.symbol, "UNCHARTED"),
                        ).fetchone()
                if ret:
                    val = {wp["symbol"]: wp for wp in ret}
                else:
                    val = {}
                setattr(self, name, val)

            case "graph":
                if DEBUG:
                    logger.debug(f"Loading {name}")
                _ = self.waypoints  # load waypoints into DB
                val = self._get_graph()
                setattr(self, name, val)

        return val

    def refresh(self, refresh_graph=True):
        keys = ["waypoints", "gate", "shipyards", "markets", "uncharted"]
        if refresh_graph:  # only needed if the system wasn't loaded into the DB
            keys.append("graph")
        for name in keys:
            setattr(self, name, None)

    def _get_system(self, cur):
        """
        Add the system and all its waypoints to the database
        """
        data = self.request.get(f"systems/{self.symbol}")["data"]
        cur.execute(
            """
            INSERT INTO systems 
            (symbol, type, x, y)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (symbol) DO NOTHING
            """,
            (self.symbol, data["type"], data["x"], data["y"]),
        )

        # update waypoints (with very limited fields)
        waypoints = {}
        for wp in data["waypoints"]:
            waypoints[wp["symbol"]] = wp
        for waypoints_symbol in sorted(waypoints):
            wp = waypoints[waypoints_symbol]
            orbits = wp.get("orbits")
            orbitals = [o["symbol"] for o in wp["orbitals"]]
            cur.execute(
                """
                INSERT INTO waypoints
                ("symbol", "systemSymbol", "type", "x", "y", "orbits", "orbitals")
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT ("symbol") DO NOTHING
                """,
                (
                    waypoints_symbol,
                    self.symbol,
                    wp["type"],
                    wp["x"],
                    wp["y"],
                    orbits,
                    orbitals,
                ),
            )

    def _get_waypoints(self, cur):
        """
        Add the extended details of all waypoints to the database
        """
        if self.request is None:
            raise ValueError(
                f"System {self.symbol} is uncatalogued and "
                "requires a Request instance to proceed!"
            )
        for ret in self.request.get_all(f"systems/{self.symbol}/waypoints"):
            for wp in ret["data"]:
                symbol = wp["symbol"]
                traits = [t["symbol"] for t in wp["traits"]]
                chart = Jsonb(wp.get("chart"))
                faction = wp.get("faction", {}).get("symbol")
                cur.execute(
                    """
                    UPDATE "waypoints"
                    SET "traits" = %s,
                        "chart" = %s,
                        "faction" = %s,
                        "isUnderConstruction" = %s
                    WHERE "symbol" = %s
                    """,
                    (
                        traits,
                        chart,
                        faction,
                        wp["isUnderConstruction"],
                        symbol,
                    ),
                )

                if traits in [["UNCHARTED"], []]:
                    continue

                if wp["type"] == "JUMP_GATE":
                    self._get_gate(symbol, cur)
                if "MARKETPLACE" in traits:
                    self._get_market(symbol, cur)
                if "SHIPYARD" in traits:
                    self._get_shipyard(symbol, cur)

                # store unknown traits
                for trait in traits:
                    t = [t for t in wp["traits"] if t["symbol"] == trait][0]
                    # description = t["description"].replace("'", "''")
                    cur.execute(
                        """
                        INSERT INTO traits_waypoint
                        (symbol, name, description) 
                        VALUES (%s, %s, %s)
                        ON CONFLICT (symbol) DO NOTHING
                        """,
                        (t["symbol"], t["name"], t["description"]),
                    )

    def _get_gate(self, waypoint_symbol, cur):
        connections = self.request.get(
            f"systems/{self.symbol}/waypoints/{waypoint_symbol}/jump-gate"
        )["data"]["connections"]
        cur.execute(
            """
            INSERT INTO "jump_gates"
            ("symbol", "systemSymbol", "connections")
            VALUES (%s, %s, %s)
            ON CONFLICT ("symbol") DO NOTHING
            """,
            (
                waypoint_symbol,
                self.symbol,
                connections,
            ),
        )

    def _get_market(self, waypoint_symbol, cur):
        ret = self.request.get(
            f"systems/{self.symbol}/waypoints/{waypoint_symbol}/market"
        )["data"]
        cur.execute(
            """
            INSERT INTO "markets"
            ("symbol", "systemSymbol", "imports", "exports", "exchange")
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT ("symbol") DO NOTHING
            """,
            (
                waypoint_symbol,
                self.symbol,
                [good["symbol"] for good in ret["imports"]],
                [good["symbol"] for good in ret["exports"]],
                [good["symbol"] for good in ret["exchange"]],
            ),
        )

    def _get_shipyard(self, waypoint_symbol, cur):
        ret = self.request.get(
            f"systems/{self.symbol}/waypoints/{waypoint_symbol}/shipyard"
        )["data"]
        cur.execute(
            """
            INSERT INTO "shipyards"
            ("symbol", "systemSymbol", "shipTypes", "modificationsFee")
            VALUES (%s, %s, %s, %s)
            ON CONFLICT ("symbol") DO NOTHING
            """,
            (
                waypoint_symbol,
                self.symbol,
                [ship["type"] for ship in ret["shipTypes"]],
                ret["modificationsFee"],
            ),
        )

    def _get_graph(self):
        xy = np.array([itemgetter("x", "y")(wp) for wp in self.waypoints.values()])
        # all coordinates must be unique, so that the distances are nonzero
        while len(xy) != len(np.unique(xy, axis=0)):
            xy = xy + np.random.normal(0, 0.0001, xy.shape)
        g = nx.from_numpy_array(  # noqa
            A=cdist(xy, xy),
            parallel_edges=False,
            create_using=nx.Graph,
            edge_attr="distance",
            nodelist=self.waypoints,
        )
        return g

    def waypoints_with(
        self, type: list[str] | str = None, traits: list[str] | str = None
    ):
        query = """SELECT * FROM waypoints WHERE "systemSymbol" = %s """
        params = [self.symbol]
        if type:
            if isinstance(type, list):
                query += "AND type = ANY(%s) "
            elif isinstance(type, str):
                query += "AND type = %s "
            else:
                raise TypeError(f"Argument type must be list or str")
            params.append(type)
        if traits:
            if isinstance(traits, list):
                query += """
                    AND NOT EXISTS (
                        SELECT 1
                        FROM unnest(%s::text[]) AS elem
                        WHERE elem NOT IN (SELECT unnest(traits))
                    ) 
                """
            elif isinstance(traits, str):
                query += "AND %s = ANY(traits) "
            else:
                raise TypeError(f"Argument traits must be list or str")
            params.append(traits)
        query += """ORDER BY "symbol" """

        with connect("dbname=st2 user=postgres", row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                wps = {wp["symbol"]: wp for wp in cur.fetchall()}

        return wps

    def trade_goods(self, type: str = None):
        """
        List of tradeGoods from the specified type of trade

        :param type: "IMPORTS", "EXPORTS", "EXCHANGE", "BUYS", "SELLS", None
        :return: List of tradeGoods
        """
        query = """
        WITH
        system_markets AS (
            SELECT *
            FROM markets
            WHERE "systemSymbol" = %s
        )
        """
        params = [self.symbol]
        if isinstance(type, str):
            type = type.lower()
        match type:
            case "imports" | "exports" | "exchange":
                query += f"""
                SELECT DISTINCT unnest("{type}") FROM system_markets
                """
            case "buys" | "sells":
                port = "imports" if type == "buys" else "exports"
                query += f"""
                    SELECT DISTINCT value
                    FROM (
                        SELECT unnest("{port}") AS value FROM system_markets
                        UNION ALL
                        SELECT unnest("exchange") AS value FROM system_markets
                    )
                    """
            case None:
                query += """
                    SELECT DISTINCT value
                    FROM (
                        SELECT unnest("imports") AS value FROM system_markets
                        UNION ALL
                        SELECT unnest("exports") AS value FROM system_markets
                        UNION ALL
                        SELECT unnest("exchange") AS value FROM system_markets
                    )
                    """
            case "_":
                raise ValueError(f"{type=} not recognized")
        with connect("dbname=st2 user=postgres") as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                return sorted(row[0] for row in cur.fetchall())

    def markets_with(self, symbol: str, type: str = None):
        """
        Return a dict with all waypoints trading the good in the requested type

        :param symbol: tradeSymbol (e.g. "FUEL")
        :param type: "IMPORTS", "EXPORTS", "EXCHANGE", "BUYS", "SELLS", None
        :return: dict with waypoints as key and their latest tradeGood as values
        """
        # TODO: will return nothing if the system was not loaded, charted and scouted
        # TODO: this function can be converted into a single query
        query = """SELECT * FROM markets WHERE "systemSymbol" = %s """
        params = [self.symbol, symbol]
        if isinstance(type, str):
            type = type.lower()
        match type:
            case "imports":
                query += "AND %s = ANY(imports) "
            case "exports":
                query += "AND %s = ANY(exports) "
            case "exchange":
                query += "AND %s = ANY(exchange) "
            case "buys":
                query += "AND (%s = ANY(imports) OR %s = ANY(exchange)) "
                params.append(symbol)
            case "sells":
                query += "AND (%s = ANY(exports) OR %s = ANY(exchange)) "
                params.append(symbol)
            case None:
                query += "AND (%s = ANY(imports) OR %s = ANY(exports) OR %s = ANY(exchange)) "
                params.extend([symbol, symbol])
            case "_":
                raise ValueError(f"{type=} not recognized")
        query += "ORDER BY symbol"

        with connect("dbname=st2 user=postgres", row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                # this dict is complete
                cur.execute(query, params)
                wps = {wp["symbol"]: wp for wp in cur.fetchall()}

                # this dict can be incomplete (if the market has never been visited)
                cur.execute(
                    """
                    SELECT DISTINCT ON ("waypointSymbol") * 
                    FROM market_tradegoods
                    WHERE symbol = %s
                      AND "waypointSymbol" = ANY(%s)
                    ORDER BY "waypointSymbol", "timestamp" DESC
                    """,
                    (symbol, list(wps)),
                )
                ret = cur.fetchall()

        # create a dictionary for each waypoint,
        #   with the latest tradeGood info as values
        md = {}
        for wp in wps:
            for n, tg in enumerate(ret):
                if tg["waypointSymbol"] == wp:
                    md[wp] = ret.pop(n)
                    break
            else:
                # placeholder
                if symbol in wps[wp]["imports"]:
                    t = "IMPORTS"
                elif symbol in wps[wp]["exports"]:
                    t = "EXPORTS"
                else:
                    t = "EXCHANGE"
                md[wp] = {
                    "waypointSymbol": wps[wp]["symbol"],
                    "systemSymbol": self.symbol,
                    "symbol": symbol,
                    "tradeVolume": None,
                    "type": t,
                    "supply": None,
                    "activity": None,
                    "purchasePrice": None,
                    "sellPrice": None,
                    "timestamp": None,
                }
        return md

    def ship_types(self):
        """
        List of shipTypes

        :return: List of shipTypes
        """
        with connect("dbname=st2 user=postgres") as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT DISTINCT value
                    FROM (
                        SELECT unnest("shipTypes") AS value FROM shipyards
                        WHERE "systemSymbol" = %s
                    )
                    """,
                    [self.symbol],
                )
                return sorted(row[0] for row in cur.fetchall())

    def shipyards_with(self, type: str):
        """
        Return a dict with all waypoints trading the good in the requested type

        :param type: shipTypes (e.g. "SHIP_PROBE")
        :return: dict with waypoints as key and their latest ship as values
        """
        # TODO: will return nothing if the system was not loaded, charted and scouted
        with connect("dbname=st2 user=postgres", row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                # this dict is complete
                cur.execute(
                    """
                    SELECT "symbol"
                    FROM shipyards
                    WHERE %s = ANY("shipTypes")
                      AND "systemSymbol" = %s
                    ORDER BY "symbol"
                    """,
                    (type, self.symbol),
                )
                wps = [wp["symbol"] for wp in cur.fetchall()]

                # this dict can be incomplete (if the shipyard has never been visited)
                cur.execute(
                    """
                    SELECT DISTINCT ON ("waypointSymbol") * 
                    FROM shipyard_ships
                    WHERE type = %s
                      AND "systemSymbol" = %s
                    ORDER BY "waypointSymbol", "timestamp" DESC
                    """,
                    (type, self.symbol),
                )
                ret = cur.fetchall()

        # create a dictionary for each waypoint,
        #   with the latest shipType info as values
        md = {}
        for wp in wps:
            for n, tg in enumerate(ret):
                if tg["waypointSymbol"] == wp:
                    md[wp] = ret.pop(n)
                    break
            else:
                # placeholder
                md[wp] = {
                    "waypointSymbol": wp,
                    "systemSymbol": self.symbol,
                    "type": type,
                    "supply": None,
                    "activity": None,
                    "purchasePrice": None,
                    "timestamp": None,
                }
        return md

    def shortest_passing_path(self, wps: list, start: str = None, weight="distance"):
        """Return the shortest route through all specified waypoints/systems."""
        if start and start not in wps:
            wps = wps + [start]  # prevents updating wps out of scope

        if len(wps) >= 2:
            path = traveling_salesman_problem(
                self.graph, weight=weight, nodes=wps, cycle=False
            )
        elif len(wps) == 1:
            path = wps
        else:
            path = []

        if start:
            i = path.index(start)
            path = path[i:] + path[:i]
        return path

    def central_waypoint(self):
        """Return the waypoint nearest to (0,0)"""
        best = None, float("inf")
        for wp, md in self.waypoints.items():
            distance = dist(0, 0, md["x"], md["y"])
            if distance < best[1]:
                best = wp, distance
        return best[0]

    def waypoints_sort(self, source, waypoints=None, reverse=False):
        """Sort waypoints in ascending proximity to the source."""
        original_waypoints = set(waypoints)
        if waypoints is None:
            waypoints = list(self.waypoints)
        else:
            waypoints = list(waypoints)

        nodes = waypoints + [source]
        subgraph = nx.subgraph_view(self.graph, filter_node=lambda node: node in nodes)
        waypoint_distances = sorted(
            subgraph[source].items(),
            key=lambda edge: edge[1]["distance"],
            reverse=reverse,
        )

        if reverse is False and source in original_waypoints:
            yield source
        for wp, md in waypoint_distances:
            yield wp
        if reverse is True and source in original_waypoints:
            yield source

    def uncharted_markets(self):
        """Return uncharted waypoints with a chance on a marketplace"""
        # https://github.com/SpaceTradersAPI/api-docs/blob/main/models/WaypointType.json
        wps = []
        for wp, md in self.waypoints.items():
            if len(md["traits"]) != 1:
                continue
            if md["traits"][0] != "UNCHARTED":
                continue
            if md["type"] in {
                "ASTEROID",
                "ASTEROID_FIELD",
                "DEBRIS_FIELD",
                "GAS_GIANT",
                "GRAVITY_WELL",
                "NEBULA",
            }:
                continue
            wps.append(wp)
        return wps

    def unscouted_markets(self):
        """Return charted marketplaces that have not been scouted yet"""
        _ = self.waypoints
        with (
            connect("dbname=st2 user=postgres", row_factory=dict_row) as conn,
            conn.cursor() as cur,
        ):
            # contains charted marketplaces
            ret1 = cur.execute(
                """
                SELECT "symbol" FROM markets
                WHERE "systemSymbol" = %s
                """,
                (self.symbol,),
            ).fetchall()
            # contains scouted marketplaces
            ret2 = cur.execute(
                """
                SELECT DISTINCT ON ("waypointSymbol") * FROM market_tradegoods
                WHERE "systemSymbol" = %s
                ORDER BY "waypointSymbol", "timestamp" DESC;
                """,
                (self.symbol,),
            ).fetchall()
        wps = list(
            {row["symbol"] for row in ret1} - {row["waypointSymbol"] for row in ret2}
        )
        return wps

    def get_construction(self, waypoint_symbol):
        data = self.request.get(
            f"systems/{self.symbol}/waypoints/{waypoint_symbol}/construction"
        )["data"]
        with connect("dbname=st2 user=postgres") as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO construction
                (symbol, materials, "isComplete", timestamp)
                VALUES (%s, %s, %s, %s)
                """,
                (
                    data["symbol"],
                    Jsonb(data["materials"]),
                    data["isComplete"],
                    time.now(),
                ),
            )
        return data


def get_start_systems(faction):
    """
    Start systems:
      - contain an ENGINEERED_ASTEROID
      - do not sell "SHIP_EXPLORER"
      - can be the faction's headquarters
      - (might) have 3 "ORBITAL_STATION"s instead of 2?
    """
    with connect("dbname=st2 user=postgres") as conn, conn.cursor() as cur:
        ret = cur.execute(
            """
            SELECT "systemSymbol"
            FROM "waypoints"
            WHERE "faction" = %s 
              AND "type" = %s
              AND "systemSymbol" NOT IN (
                  SELECT "systemSymbol"
                    FROM "shipyards"
                   WHERE %s = ANY("shipTypes")
              )
            """,
            [faction, "ENGINEERED_ASTEROID", "SHIP_EXPLORER"],
        ).fetchall()
    start_systems = [row[0] for row in ret]
    return start_systems
