"""
Postgresql: https://gist.github.com/gwangjinkim/f13bf596fefa7db7d31c22efd1627c7a
Psycopg3 docs: https://www.psycopg.org/psycopg3/docs/basic/index.html
"""

import atexit
import os
import subprocess as sp

from psycopg import connect

from st2.caching import cache
from st2.db.static.traits import TRAITS_FACTION


def db_server_path():
    db = os.path.join(cache["data_dir"], f"sql")
    return db


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
                    "symbol" text PRIMARY KEY,
                    "token" text,
                    "role" text,
                    "faction" text,
                    "other" text
                )
                """
            )

        if "agents_public" not in tables:
            cur.execute(
                """
                CREATE TABLE agents_public
                (
                    "accountId" text,
                    "symbol" text,
                    "headquarters" text,
                    "credits" integer,
                    "startingFaction" text,
                    "shipCount" integer,
                    "timestamp" timestamptz
                )
                """
            )

        if "contracts" not in tables:
            cur.execute(
                """
                CREATE TABLE contracts
                (
                    "id" text PRIMARY KEY, 
                    "agentSymbol" text, 
                    "factionSymbol" text, 
                    "type" text,  -- PROCUREMENT/TRANSPORT/SHUTTLE
                    "terms" JsonB,
                    "accepted" bool, 
                    "fulfilled" bool, 
                    "deadlineToAccept" timestamptz
                )
                """
            )

        if "ships" not in tables:
            cur.execute(
                """
                CREATE TABLE ships
                (
                    "symbol" text PRIMARY KEY,
                    "agentSymbol" text,
                    "nav" JsonB,
                    "crew" JsonB,
                    "fuel" JsonB,
                    "cooldown" JsonB,
                    "frame" JsonB,
                    "reactor" JsonB,
                    "engine" JsonB,
                    "modules" JsonB,
                    "mounts" JsonB,
                    "registration" JsonB,
                    "cargo" JsonB
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
                    "symbol" text PRIMARY KEY,
                    "agentSymbol" text,
                    "current" text,
                    "queued" text,
                    "cancel" bool,  -- cancel current task, start queued task
                    "pname" text,  -- process name (which should manage this task)
                    "pid" uuid  -- process ID (use to check if restarts occurred)
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
            # factions JSONB, always empty

        if "waypoints" not in tables:
            cur.execute(
                """
                CREATE TABLE waypoints 
                (
                    "symbol" text PRIMARY KEY,
                    "systemSymbol" text,
                    "type" text,
                    "x" integer,
                    "y" integer,
                    "orbits" text,
                    "orbitals" text[],
                    "traits" text[],
                    "chart" JSONB,
                    "faction" text,
                    "isUnderConstruction" bool
                )
                """
            )
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
                    "symbol" text PRIMARY KEY,
                    "name" text,
                    "description" text,
                    "headquarters" text,
                    "traits" text[],
                    "isRecruiting" bool
                )
                """
            )

        if "jump_gates" not in tables:
            cur.execute(
                """
                CREATE TABLE jump_gates 
                (
                    "symbol" text PRIMARY KEY,
                    "systemSymbol" text,
                    "connections" text[]
                )
                """
            )

        if "markets" not in tables:
            cur.execute(
                """
                CREATE TABLE markets 
                (
                    "symbol" text PRIMARY KEY,
                    "systemSymbol" text,
                    "imports" text[],
                    "exports" text[],
                    "exchange" text[]
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
                    "waypointSymbol" text,
                    "systemSymbol" text,
                    "shipSymbol" text,
                    "tradeSymbol" text,
                    "type" text,
                    "units" integer,
                    "pricePerUnit" integer,
                    "totalPrice" integer,
                    "timestamp" timestamptz,
                    PRIMARY KEY ("waypointSymbol", "timestamp")
                )
                """
            )
            #  PARTITION BY LIST ("waypointSymbol")

        if "market_tradegoods" not in tables:
            # - Create a waypoint specific tradegoods table:
            #   CREATE TABLE tradegoods_wp1 PARTITION OF tradegoods FOR VALUES IN ('wp1');
            # - Use st2.time.now() as timestamp
            cur.execute(
                """
                CREATE TABLE market_tradegoods
                (
                    "waypointSymbol" text,
                    "systemSymbol" text,
                    "symbol" text,
                    "tradeVolume" integer,
                    "type" text,  --IMPORT/EXPORT/EXCHANGE
                    "supply" text,
                    "activity" text,
                    "purchasePrice" integer,
                    "sellPrice" integer,
                    "timestamp" timestamptz,
                    PRIMARY KEY ("waypointSymbol", "symbol", "timestamp")
                )
                """
            )
            #  PARTITION BY LIST ("waypointSymbol")

        if "shipyards" not in tables:
            cur.execute(
                """
                CREATE TABLE shipyards 
                (
                    "symbol" text PRIMARY KEY,
                    "systemSymbol" text,
                    "shipTypes" text[],
                    "modificationsFee" integer
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
                    "waypointSymbol" text,
                    "systemSymbol" text,
                    "shipSymbol" text,
                    "agentSymbol" text,
                    "shipType" text,
                    "price" integer,
                    "timestamp" timestamptz,
                    PRIMARY KEY ("waypointSymbol", "timestamp")
                )
                """
            )
            #  PARTITION BY LIST ("waypointSymbol")

        if "shipyard_ships" not in tables:
            # - Create a waypoint specific tradegoods table:
            #   CREATE TABLE tradegoods_wp1 PARTITION OF tradegoods FOR VALUES IN ('wp1');
            # - Use st2.time.now() as timestamp
            cur.execute(
                """
                CREATE TABLE shipyard_ships
                (
                    "waypointSymbol" text,
                    "systemSymbol" text,
                    "type" text,
                    "supply" text,
                    "activity" text,
                    "purchasePrice" integer,
                    "timestamp" timestamptz,
                    PRIMARY KEY ("waypointSymbol", "type", "timestamp")
                )
                """
            )
            # PARTITION BY LIST ("waypointSymbol")

        if "events" not in tables:
            cur.execute(
                """
                CREATE TABLE events
                (
                    "symbol" text,
                    "shipSymbol" text,
                    "activity" text,
                    "component" text,
                    "condition" float8,
                    "timestamp" timestamptz
                )
                """
            )

        if "navigation" not in tables:
            cur.execute(
                """
                CREATE TABLE navigation
                (
                    "distance" float8,
                    "time" float8,
                    "fuel" integer,
                    "flightMode" text,
                    "speed" integer,
                    "frame" text,
                    "frame_condition" float8,
                    "frame_integrity" float8,
                    "reactor" text,
                    "reactor_condition" float8,
                    "reactor_integrity" float8,
                    "engine" text,
                    "engine_condition" float8,
                    "engine_integrity" float8
                )
                """
            )

        if "extraction" not in tables:
            cur.execute(
                """
                CREATE TABLE extraction
                (
                    "symbol" text,
                    "units" integer,
                    "survey" JsonB,
                    "cargo_full" bool,
                    "mount" text,
                    "frame" text,
                    "frame_condition" float8,
                    "frame_integrity" float8,
                    "reactor" text,
                    "reactor_condition" float8,
                    "reactor_integrity" float8,
                    "engine" text,
                    "engine_condition" float8,
                    "engine_integrity" float8
                )
                """
            )


def db_update_factions(request, priority=0, token=None):
    factions = {}
    for fs in request.get_all("factions", priority, token):
        for f in fs["data"]:
            factions[f["symbol"]] = f

    with connect("dbname=st2 user=postgres") as conn:
        with conn.cursor() as cur:
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
                    ("symbol", "name", "description", "headquarters", "traits", "isRecruiting")
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT ("symbol") DO NOTHING
                    """,
                    (
                        f["symbol"],
                        f["name"],
                        description,
                        hq,
                        traits,
                        f["isRecruiting"],
                    ),
                )

                # traits_faction
                for trait in f["traits"]:
                    if TRAITS_FACTION.get(trait["symbol"]):
                        continue
                    description = trait["description"].replace("'", "''")
                    cur.execute(
                        """
                        INSERT INTO traits_faction
                        (symbol, name, description)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (symbol) DO NOTHING
                        """,
                        (trait["symbol"], trait["name"], description),
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


def delete_tables():
    with connect("dbname=st2 user=postgres") as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            """
        )
        for row in cur.fetchall():
            table = row[0]
            cur.execute(f"DROP TABLE {table}")
            conn.commit()
