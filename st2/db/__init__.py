"""
Postgresql: https://gist.github.com/gwangjinkim/f13bf596fefa7db7d31c22efd1627c7a
Psycopg3 docs: https://www.psycopg.org/psycopg3/docs/basic/index.html
"""

import atexit
import os
import subprocess as sp

from psycopg import connect
from psycopg.types.json import Jsonb

from st2 import time
from st2.caching import cache


def db_server_init():
    db = os.path.join(cache["data_dir"], f"sql")
    log = os.path.join(cache["log_dir"], f"sql.txt")
    if not os.path.exists(db):
        # make the database
        if not os.path.exists(cache["data_dir"]):
            os.makedirs(cache["data_dir"], exist_ok=True)
        sp.check_output(
            f"initdb -D {db} --username=postgres", shell=True, stderr=sp.STDOUT
        )
        if not os.path.exists(cache["log_dir"]):
            os.makedirs(cache["log_dir"], exist_ok=True)
        sp.check_output(f"pg_ctl -D {db} -l {log} start", shell=True, stderr=sp.STDOUT)
        sp.check_output(
            f"createdb --no-password --owner=postgres --user=postgres st2",
            shell=True,
            stderr=sp.STDOUT,
        )
        sp.check_output(f"pg_ctl -D {db} stop", shell=True)

    # check if the SQL server is running
    try:
        running = bool(sp.check_output(f"pg_ctl -D {db} status", shell=True))
    except sp.CalledProcessError as e:
        if str(e).endswith("exit status 3."):
            running = False
        else:
            raise e

    if not running:
        # start the database
        sp.check_output(f"pg_ctl -D {db} -l {log} start", shell=True)

        def stop_sql_server():
            sp.check_output(f"pg_ctl -D {db} stop", shell=True)

        # stop the sql_server when we stop
        atexit.register(stop_sql_server)


def db_tables_init():
    with connect("dbname=st2 user=postgres") as conn, conn.cursor() as cur:

        # Fetch existing table names
        cur.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            """
        )
        tables = [row[0] for row in cur.fetchall()]

        # # delete all tables
        # for table in tables:
        #     cur.execute(f"DROP TABLE {table}")
        #     conn.commit()
        # tables = []

        # Create missing tables
        if "agents" not in tables:
            cur.execute(
                """
                CREATE TABLE agents
                (
                    symbol text PRIMARY KEY,
                    token text,
                    role text,
                    faction text,
                    other text
                )
                """
            )

        if "ships" not in tables:
            cur.execute(
                """
                CREATE TABLE ships
                (
                    symbol text PRIMARY KEY,
                    agentSymbol text,
                    nav JsonB,
                    crew JsonB,
                    fuel JsonB,
                    cooldown JsonB,
                    frame JsonB,
                    reactor JsonB,
                    engine JsonB,
                    modules JsonB,
                    mounts JsonB,
                    registration JsonB,
                    cargo JsonB
                )
                """
            )

        if "tasks" not in tables:
            """
            Ship tasks:
             - If task is None or "idle", the ship is idle.
               - None if for new ships that will receive a task momentarily.
               - "idle" ships are ready to accept any task.
             - To use an idle ship, set a task & add the ship to a ship-manager process.
             - To commandeer a ship, overwrite the queued task (and cancel command if needed).

            Tasks should:
             - check the table regularly for external cancel commands.
             - update current/queued/cancel in the table.
             - self destruct when the current task finishes and the queued task is "idle".
            """
            cur.execute(
                """
                CREATE TABLE tasks
                (
                    symbol text PRIMARY KEY,
                    agentSymbol text,
                    current text,
                    queued text,
                    cancel bool,  -- cancel current task, start queued task
                    pname text,  -- process name (which should manage this task)
                    pid uuid  -- process ID (use to check if restarts occurred)
                )
                """
            )

        if "systems" not in tables:
            cur.execute(
                """
                CREATE TABLE systems 
                (
                    symbol text PRIMARY KEY,
                    type text,
                    x integer,
                    y integer
                )
                """
            )
            # sectorSymbol text, always X1
            # waypoints: see table system_waypoints
            # factions JSONB, always empty

        if "waypoints" not in tables:
            cur.execute(
                """
                CREATE TABLE waypoints 
                (
                    symbol text PRIMARY KEY,
                    systemSymbol text,
                    type text,
                    x integer,
                    y integer,
                    orbits text,
                    orbitals text[],
                    traits text[],
                    chart JSONB,
                    faction text,
                    isUnderConstruction bool
                )
                """
            )
            # orbitals: also in table waypoint_orbitals
            # traits: also in table waypoint_traits
            # modifiers JSONB, always empty

        if "traits_waypoint" not in tables:
            cur.execute(
                """
                CREATE TABLE traits_waypoint 
                (
                    symbol text PRIMARY KEY,
                    name text,
                    description text
                )
                """
            )

        if "traits_faction" not in tables:
            cur.execute(
                """
                CREATE TABLE traits_faction 
                (
                    symbol text PRIMARY KEY,
                    name text,
                    description text
                )
                """
            )

        if "factions" not in tables:
            cur.execute(
                """
                CREATE TABLE factions 
                (
                    symbol text PRIMARY KEY,
                    name text,
                    description text,
                    headquarters text,
                    traits text[],
                    isRecruiting bool
                )
                """
            )
            # traits: also in table faction_traits

        if "jump_gates" not in tables:
            cur.execute(
                """
                CREATE TABLE jump_gates 
                (
                    symbol text PRIMARY KEY,
                    systemSymbol text,
                    connections text[]
                )
                """
            )

        if "markets" not in tables:
            cur.execute(
                """
                CREATE TABLE markets 
                (
                    symbol text PRIMARY KEY,
                    systemSymbol text,
                    imports text[],
                    exports text[],
                    exchange text[]
                )
                """
            )

        if "market_transactions" not in tables:
            # - Create a waypoint specific transactions table:
            #   CREATE TABLE transactions_wp1 PARTITION OF transactions FOR VALUES IN ('wp1');
            cur.execute(
                """
                CREATE TABLE market_transactions
                (
                    waypointSymbol text,
                    systemSymbol text,
                    shipSymbol text,
                    tradeSymbol text,
                    type text,
                    units integer,
                    pricePerUnit integer,
                    totalPrice integer,
                    timestamp timestamptz,
                    PRIMARY KEY (waypointSymbol, timestamp)
                ) PARTITION BY LIST (waypointSymbol)
                """
            )

        if "market_tradegoods" not in tables:
            # - Create a waypoint specific tradegoods table:
            #   CREATE TABLE tradegoods_wp1 PARTITION OF tradegoods FOR VALUES IN ('wp1');
            # - Use st2.time.now() as timestamp
            cur.execute(
                """
                CREATE TABLE market_tradegoods
                (
                    waypointSymbol text,
                    systemSymbol text,
                    symbol text,
                    tradeVolume integer,
                    type text,
                    supply text,
                    activity text,
                    purchasePrice integer,
                    sellPrice integer,
                    timestamp timestamptz,
                    PRIMARY KEY (waypointSymbol, symbol, timestamp)
                ) PARTITION BY LIST (waypointSymbol)
                """
            )

        if "shipyards" not in tables:
            cur.execute(
                """
                CREATE TABLE shipyards 
                (
                    symbol text PRIMARY KEY,
                    systemSymbol text,
                    shipTypes text[],
                    modificationsFee integer
                )
                """
            )

        if "shipyard_transactions" not in tables:
            # - Create a waypoint specific transactions table:
            #   CREATE TABLE transactions_wp1 PARTITION OF transactions FOR VALUES IN ('wp1');
            # - Use st2.time.read(timestamp) as timestamp
            cur.execute(
                """
                CREATE TABLE shipyard_transactions
                (
                    waypointSymbol text,
                    systemSymbol text,
                    shipSymbol text,
                    agentSymbol text,
                    shipType text,
                    price integer,
                    timestamp timestamptz,
                    PRIMARY KEY (waypointSymbol, timestamp)
                ) PARTITION BY LIST (waypointSymbol)
                """
            )

        if "shipyard_ships" not in tables:
            # - Create a waypoint specific tradegoods table:
            #   CREATE TABLE tradegoods_wp1 PARTITION OF tradegoods FOR VALUES IN ('wp1');
            # - Use st2.time.now() as timestamp
            cur.execute(
                """
                CREATE TABLE shipyard_ships
                (
                    waypointSymbol text,
                    systemSymbol text,
                    type text,
                    supply text,
                    activity text,
                    purchasePrice integer,
                    timestamp timestamptz,
                    PRIMARY KEY (waypointSymbol, type, timestamp)
                ) PARTITION BY LIST (waypointSymbol)
                """
            )

        # intermediary tables
        if "system_waypoints" not in tables:
            cur.execute(
                """
                CREATE TABLE system_waypoints 
                (
                    systemSymbol text,
                    waypointSymbol text,
                    PRIMARY KEY (systemSymbol, waypointSymbol)
                )
                """
            )

        if "waypoint_traits" not in tables:
            cur.execute(
                """
                CREATE TABLE waypoint_traits 
                (
                    waypointSymbol text,
                    traitSymbol text,
                    PRIMARY KEY (waypointSymbol, traitSymbol)
                )
                """
            )

        if "faction_traits" not in tables:
            cur.execute(
                """
                CREATE TABLE faction_traits 
                (
                    factionSymbol text,
                    traitSymbol text,
                    PRIMARY KEY (factionSymbol, traitSymbol)
                )
                """
            )


def db_update_factions(request):
    factions = {}
    for fs in request.get_all("factions", 3):
        for f in fs["data"]:
            factions[f["symbol"]] = f

    with connect("dbname=st2 user=postgres") as conn, conn.cursor() as cur:
        # insert factions & faction_traits
        for symbol in sorted(factions):
            f = factions[symbol]
            description = f["description"].replace("'", "''")
            hq = f["headquarters"]
            if hq == "":
                hq = None
            traits = [t["symbol"] for t in f["traits"]]
            cur.execute(
                """
                INSERT INTO factions 
                (symbol, name, description, headquarters, traits, isRecruiting) 
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (symbol) DO NOTHING
                """,
                (f["symbol"], f["name"], description, hq, traits, f["isRecruiting"]),
            )

            # faction_traits
            for trait in traits:
                cur.execute(
                    """
                    INSERT INTO faction_traits
                    (factionSymbol, traitSymbol) 
                    VALUES (%s, %s)
                    ON CONFLICT (factionSymbol, traitSymbol) DO NOTHING
                    """,
                    (symbol, trait),
                )

        # traits_faction
        traits = {}
        for f in factions.values():
            for t in f["traits"]:
                traits[t["symbol"]] = t
        for symbol in sorted(traits):
            t = traits[symbol]
            description = t["description"].replace("'", "''")
            cur.execute(
                """
                INSERT INTO traits_faction 
                (symbol, name, description) 
                VALUES (%s, %s, %s)
                ON CONFLICT (symbol) DO NOTHING
                """,
                (t["symbol"], t["name"], description),
            )
        conn.commit()


def chart_gate(symbol, request, token, cur):
    system_symbol = symbol.rsplit("-", 1)[0]
    connections = request.get(
        endpoint=f"systems/{system_symbol}/waypoints/{symbol}/jump-gate",
        priority=3,
        token=token,
    )["data"]["connections"]
    cur.execute(
        """
        INSERT INTO jump_gates
        (symbol, systemSymbol, connections)
        VALUES (%s, %s, %s)
        ON CONFLICT (symbol) DO NOTHING
        """,
        (
            symbol,
            system_symbol,
            connections,
        ),
    )


def chart_market(symbol, request, token, cur):
    system_symbol = symbol.rsplit("-", 1)[0]
    ret = request.get(
        endpoint=f"systems/{system_symbol}/waypoints/{symbol}/market",
        priority=3,
        token=token,
    )["data"]
    cur.execute(
        """
        INSERT INTO markets
        (symbol, systemSymbol, imports, exports, exchange)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (symbol) DO NOTHING
        """,
        (
            symbol,
            system_symbol,
            [good["symbol"] for good in ret["imports"]],
            [good["symbol"] for good in ret["exports"]],
            [good["symbol"] for good in ret["exchange"]],
        ),
    )
    # TODO: split into charting (above part only) and logging (lower part only)?
    timestamp = time.now()
    for t in ret.get("tradeGoods", []):
        cur.execute(
            """
            INSERT INTO market_tradegoods
            (waypointSymbol, systemSymbol, symbol, tradeVolume, type,
             supply, activity, purchasePrice, sellPrice, timestamp)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (waypointSymbol, symbol, timestamp) DO NOTHING
            """,
            (
                symbol,
                system_symbol,
                t["symbol"],
                t["tradeVolume"],
                t["type"],
                t["supply"],
                t["activity"],
                t["purchasePrice"],
                t["sellPrice"],
                timestamp,
            ),
        )
    for t in ret.get("transactions", []):
        cur.execute(
            """
            INSERT INTO market_transactions
            (waypointSymbol, systemSymbol, shipSymbol, tradeSymbol,
             type, units, pricePerUnit, totalPrice, timestamp)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (waypointSymbol, timestamp) DO NOTHING
            """,
            (
                symbol,
                system_symbol,
                t["shipSymbol"],
                t["tradeSymbol"],
                t["type"],
                t["units"],
                t["pricePerUnit"],
                t["totalPrice"],
                time.read(t["timestamp"]),
            ),
        )


def chart_shipyard(symbol, request, token, cur):
    system_symbol = symbol.rsplit("-", 1)[0]
    ret = request.get(
        endpoint=f"systems/{system_symbol}/waypoints/{symbol}/shipyard",
        priority=3,
        token=token,
    )["data"]
    cur.execute(
        """
        INSERT INTO shipyards
        (symbol, systemSymbol, shipTypes, modificationsFee)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (symbol) DO NOTHING
        """,
        (
            symbol,
            system_symbol,
            [ship["type"] for ship in ret["shipTypes"]],
            ret["modificationsFee"],
        ),
    )
    timestamp = time.now()
    for s in ret.get("ships", []):
        cur.execute(
            """
            INSERT INTO shipyard_ships
            (waypointSymbol, systemSymbol, type,
             supply, activity, purchasePrice, timestamp)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (waypointSymbol, symbol, timestamp) DO NOTHING
            """,
            (
                symbol,
                system_symbol,
                s["type"],
                s["supply"],
                s["activity"],
                s["purchasePrice"],
                timestamp,
            ),
        )
    for s in ret.get("transactions", []):
        cur.execute(
            """
            INSERT INTO shipyard_transactions
            (waypointSymbol, systemSymbol, shipSymbol,
             agentSymbol, shipType, price, timestamp)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (waypointSymbol, timestamp) DO NOTHING
            """,
            (
                symbol,
                system_symbol,
                s["shipSymbol"],
                s["agentSymbol"],
                s["shipType"],
                s["price"],
                time.read(s["timestamp"]),
            ),
        )


def insert_ship(ship, agent_symbol, cur):
    cur.execute(
        """
        INSERT INTO ships
        (symbol, agentSymbol, nav, crew, fuel, cooldown, frame,
         reactor, engine, modules, mounts, registration, cargo)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            ship["symbol"],
            agent_symbol,
            Jsonb(ship["nav"]),
            Jsonb(ship["crew"]),
            Jsonb(ship["fuel"]),
            Jsonb(ship["cooldown"]),
            Jsonb(ship["frame"]),
            Jsonb(ship["reactor"]),
            Jsonb(ship["engine"]),
            Jsonb(ship["modules"]),
            Jsonb(ship["mounts"]),
            Jsonb(ship["registration"]),
            Jsonb(ship["cargo"]),
        ),
    )

    cur.execute(
        """
        INSERT INTO tasks (symbol, agentSymbol, current, queued, cancel, pname, pid) 
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        (ship["symbol"], agent_symbol, None, None, False, None, None),
    )


def print_tables():
    with connect("dbname=st2 user=postgres") as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            """
        )
        return [row[0] for row in cur.fetchall()]


def print_table(table):
    with connect("dbname=st2 user=postgres") as conn, conn.cursor() as cur:
        # print a table's columns
        cur.execute(
            """
            SELECT *
            FROM information_schema.columns
            WHERE table_name = %s
            ORDER BY ordinal_position
            """,
            (table,),
        )
        ret = cur.fetchall()
        header = []
        dtypes = []
        for row in ret:
            name = row[3]
            dtype = row[7]
            header.append(name)
            dtypes.append(dtype)
        print(header)
        print(dtypes)

        # print a table's rows
        cur.execute(f"SELECT * FROM {table}")
        ret = cur.fetchall()
        for row in ret:
            print(row)


def delete_table(table):
    with connect("dbname=st2 user=postgres") as conn, conn.cursor() as cur:
        cur.execute(f"DROP TABLE {table}")
        conn.commit()
