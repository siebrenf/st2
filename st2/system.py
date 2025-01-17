from psycopg import connect
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from st2.agent import api_agent
from st2.db.static.traits import TRAITS_WAYPOINT
from st2.logging import logger


class System:

    # lazy attributes (loaded when called)
    # listed here for code autocompletion
    gate: dict = None
    markets: dict = None
    shipyard: dict = None
    uncharted: dict = None

    def __init__(self, symbol, request, priority=None):
        self.symbol = symbol
        self.waypoints = {}
        self.request = request
        if priority:
            self.request.priority = priority
        if self.request.token is None:
            self.request.token = api_agent(request)[1]
        with connect("dbname=st2 user=postgres", row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                data = cur.execute(
                    """SELECT * FROM "systems" WHERE "symbol" = %s""", (symbol,)
                ).fetchone()
                if data is None:
                    self._get_system(symbol, cur)

                data = cur.execute(
                    """
                    SELECT * 
                    FROM "waypoints" 
                    WHERE "systemSymbol" = %s 
                    ORDER BY "symbol"
                    """,
                    (symbol,),
                ).fetchall()
                if None in [wp.get("traits") for wp in data]:
                    # system waypoints have not been added to the database yet
                    self._get_waypoints(symbol, cur)
                    data = cur.execute(
                        """
                        SELECT * 
                        FROM "waypoints" 
                        WHERE "systemSymbol" = %s 
                        ORDER BY "symbol"
                        """,
                        (symbol,),
                    ).fetchall()
                for wp in data:
                    self.waypoints[wp["symbol"]] = wp

    def _get_system(self, system_symbol, cur):
        """
        Add the system and all its waypoints to the database
        """
        data = self.request.get(f"system/{system_symbol}")["data"]
        cur.execute(
            """
            INSERT INTO systems 
            (symbol, type, x, y)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (symbol) DO NOTHING
            """,
            (system_symbol, data["type"], data["x"], data["y"]),
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
                    system_symbol,
                    wp["type"],
                    wp["x"],
                    wp["y"],
                    orbits,
                    orbitals,
                ),
            )

    def _get_waypoints(self, system_symbol, cur):
        """
        Add the extended details of all waypoints to the database
        """
        for ret in self.request.get_all(f"systems/{system_symbol}/waypoints"):
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
                    self._get_gate(symbol, system_symbol, cur)
                if "MARKETPLACE" in traits:
                    self._get_market(symbol, system_symbol, cur)
                if "SHIPYARD" in traits:
                    self._get_shipyard(symbol, system_symbol, cur)

                # store unknown traits
                for trait in traits:
                    if TRAITS_WAYPOINT.get(trait) is None:
                        t = [t for t in wp["traits"] if t["symbol"] == trait][0]
                        description = t["description"].replace("'", "''")
                        cur.execute(
                            """
                            INSERT INTO traits_waypoint
                            (symbol, name, description) 
                            VALUES (%s, %s, %s)
                            """,
                            (t["symbol"], t["name"], description),
                        )
                        logger.info(
                            f"The Cartographer has discovered a new trait: {t['symbol']}!"
                        )

    def _get_gate(self, symbol, system_symbol, cur):
        connections = self.request.get(
            f"systems/{system_symbol}/waypoints/{symbol}/jump-gate"
        )["data"]["connections"]
        cur.execute(
            """
            INSERT INTO "jump_gates"
            ("symbol", "systemSymbol", "connections")
            VALUES (%s, %s, %s)
            ON CONFLICT ("symbol") DO NOTHING
            """,
            (
                symbol,
                system_symbol,
                connections,
            ),
        )

    def _get_market(self, symbol, system_symbol, cur):
        ret = self.request.get(
            f"systems/{system_symbol}/waypoints/{symbol}/market",
        )["data"]
        cur.execute(
            """
            INSERT INTO "markets"
            ("symbol", "systemSymbol", "imports", "exports", "exchange")
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT ("symbol") DO NOTHING
            """,
            (
                symbol,
                system_symbol,
                [good["symbol"] for good in ret["imports"]],
                [good["symbol"] for good in ret["exports"]],
                [good["symbol"] for good in ret["exchange"]],
            ),
        )

    def _get_shipyard(self, symbol, system_symbol, cur):
        ret = self.request.get(
            f"systems/{system_symbol}/waypoints/{symbol}/shipyard",
        )["data"]
        cur.execute(
            """
            INSERT INTO "shipyards"
            ("symbol", "systemSymbol", "shipTypes", "modificationsFee")
            VALUES (%s, %s, %s, %s)
            ON CONFLICT ("symbol") DO NOTHING
            """,
            (
                symbol,
                system_symbol,
                [ship["type"] for ship in ret["shipTypes"]],
                ret["modificationsFee"],
            ),
        )

    # lazy attributes
    def __getattribute__(self, name):
        val = super(System, self).__getattribute__(name)
        if val is not None:
            return val

        # if the attribute is None/empty, check if it is a lazy attribute
        if name == "gate":
            with connect("dbname=st2 user=postgres", row_factory=dict_row) as conn:
                with conn.cursor() as cur:
                    ret = cur.execute(
                        """
                        SELECT * 
                        FROM "waypoints"
                        WHERE "systemSymbol" = %s 
                        AND "type" = %s
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
                        logger.warning(f"System {self.symbol} JUMP-GATE is UNCHARTED!")
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

        elif name == "shipyard":
            with connect("dbname=st2 user=postgres", row_factory=dict_row) as conn:
                with conn.cursor() as cur:
                    ret = cur.execute(
                        """
                        SELECT * 
                        FROM "shipyards"
                        WHERE "systemSymbol" = %s 
                        """,
                        (self.symbol,),
                    ).fetchall()
                    if ret:
                        val = {wp["symbol"]: wp for wp in ret}
                    else:
                        val = {}
                        logger.warning(f"System {self.symbol} has no SHIPYARD!")
            setattr(self, name, val)

        elif name == "markets":
            with connect("dbname=st2 user=postgres", row_factory=dict_row) as conn:
                with conn.cursor() as cur:
                    ret = cur.execute(
                        """
                        SELECT * 
                        FROM "markets"
                        WHERE "systemSymbol" = %s 
                        """,
                        (self.symbol,),
                    ).fetchall()
                    if ret:
                        val = {wp["symbol"]: wp for wp in ret}
                    else:
                        val = {}
                        logger.warning(f"System {self.symbol} has no MARKET!")
            setattr(self, name, val)

        elif name == "uncharted":
            with connect("dbname=st2 user=postgres", row_factory=dict_row) as conn:
                with conn.cursor() as cur:
                    ret = cur.execute(
                        """
                        SELECT * 
                        FROM "waypoints"
                        WHERE "systemSymbol" = %s 
                        AND %s = ANY(traits)
                        """,
                        (self.symbol, "UNCHARTED"),
                    ).fetchone()
                    if ret:
                        val = {wp["symbol"]: wp for wp in ret}
                    else:
                        val = {}
            setattr(self, name, val)

        return val

    @staticmethod
    def trade_goods(type: str = None):
        """
        List of tradeGoods from the specified type of trade

        :param type: "IMPORTS", "EXPORTS", "EXCHANGE", "BUYS", "SELLS", None
        :return: List of tradeGoods
        """
        query = """
            SELECT DISTINCT value
            FROM (
            """
        if isinstance(type, str):
            type = type.lower()
        match type:
            case "imports":
                query += """SELECT unnest("imports") AS value FROM markets"""
            case "exports":
                query += """SELECT unnest("exports") AS value FROM markets"""
            case "exchange":
                query += """SELECT unnest("exchange") AS value FROM markets"""
            case "buys":
                query += """
                SELECT unnest("imports") AS value FROM markets
                UNION
                SELECT unnest("exchange") AS value FROM markets
                """
            case "sells":
                query += """
                    SELECT unnest("exports") AS value FROM markets
                    UNION
                    SELECT unnest("exchange") AS value FROM markets
                    """
            case None:
                query += """
                SELECT unnest("imports") AS value FROM markets
                UNION
                SELECT unnest("exports") AS value FROM markets
                UNION
                SELECT unnest("exchange") AS value FROM markets
                """
            case "_":
                raise ValueError(f"{type=} not recognized")
        query += """\n) AS all_values"""
        with connect("dbname=st2 user=postgres") as conn:
            with conn.cursor() as cur:
                cur.execute(query)
                return sorted(row[0] for row in cur.fetchall())

    @staticmethod
    def markets_with(symbol: str, type: str = None):
        """
        Return a dict with all waypoints trading the good in the requested type

        :param symbol: tradeSymbol (e.g. "FUEL")
        :param type: "IMPORTS", "EXPORTS", "EXCHANGE", "BUYS", "SELLS", None
        :return: dict with waypoints as key and their latest tradeGood as values
        """
        query = "SELECT symbol FROM markets "
        params = [symbol]
        if isinstance(type, str):
            type = type.lower()
        match type:
            case "imports":
                query += "WHERE %s = ANY(imports)"
            case "exports":
                query += "WHERE %s = ANY(exports)"
            case "exchange":
                query += "WHERE %s = ANY(exchange)"
            case "buys":
                query += """
                WHERE %s = ANY(imports)
                   OR %s = ANY(exchange)
                """
                params.append(symbol)
            case "sells":
                query += """
                    WHERE %s = ANY(exports)
                       OR %s = ANY(exchange)
                    """
                params.append(symbol)
            case None:
                query += """
                        WHERE %s = ANY(imports)
                           OR %s = ANY(exports)
                           OR %s = ANY(exchange)
                        """
                params.extend([symbol, symbol])
            case "_":
                raise ValueError(f"{type=} not recognized")
        query += " ORDER BY symbol"
        with connect("dbname=st2 user=postgres", row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                wps = [wp["symbol"] for wp in cur.fetchall()]

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
                #   with the latest tradeGood info as value
                #   (None if the market has never been visited)
                md = {}
                for wp in wps:
                    md[wp] = None
                    for n, tg in enumerate(ret):
                        if tg["waypointSymbol"] == wp:
                            md[wp] = ret.pop(n)
                            break
        return md

    @staticmethod
    def ship_types():
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
                    ) AS all_values
                    """
                )
                return sorted(row[0] for row in cur.fetchall())

    def shipyards_with(self, type: str):
        """
        Return a dict with all waypoints trading the good in the requested type

        :param type: shipTypes (e.g. "SHIP_PROBE")
        :return: dict with waypoints as key and their latest ship as values
        """
        with connect("dbname=st2 user=postgres", row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT "symbol"
                    FROM shipyards
                    WHERE %s = ANY("shipTypes")
                    ORDER BY "symbol"
                    """,
                    (type,),
                )
                wps = [wp["symbol"] for wp in cur.fetchall()]

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
                #   with the latest tradeGood info as value
                #   (None if the market has never been visited)
                md = {}
                for wp in wps:
                    md[wp] = None
                    for n, tg in enumerate(ret):
                        if tg["waypointSymbol"] == wp:
                            md[wp] = ret.pop(n)
                            break
        return md
