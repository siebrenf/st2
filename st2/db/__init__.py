"""
Postgresql: https://gist.github.com/gwangjinkim/f13bf596fefa7db7d31c22efd1627c7a
Psycopg3 docs: https://www.psycopg.org/psycopg3/docs/basic/index.html
"""

import atexit
import os
import subprocess as sp

import psycopg

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
    with psycopg.connect(f"dbname=st2 user=postgres") as conn, conn.cursor() as cur:

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

        # # print a table
        # table = ""
        # cur.execute(f"SELECT * FROM {table}")
        # ret = cur.fetchall()
        # for row in ret:
        #     print(row)

        # Create missing tables
        if "agents" not in tables:
            cur.execute(
                """
                CREATE TABLE agents
                (
                    symbol text PRIMARY KEY,
                    token text,
                    role text
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
                    imports text[],
                    exports text[],
                    exchange text[]
                )
                """
            )

        if "market_transactions" not in tables:
            # - Create a waypoint specific transactions table:
            #   CREATE TABLE transactions_wp1 PARTITION OF transactions FOR VALUES IN ('wp1');
            # - Use st2.read(timestamp) as timestamp
            cur.execute(
                """
                CREATE TABLE market_transactions
                (
                    waypointSymbol text,
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

        if "tradegoods" not in tables:
            # - Create a waypoint specific tradegoods table:
            #   CREATE TABLE tradegoods_wp1 PARTITION OF tradegoods FOR VALUES IN ('wp1');
            # - Use st2.now() as timestamp
            cur.execute(
                """
                CREATE TABLE tradegoods
                (
                    waypointSymbol text,
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
                    shipTypes text[],
                    modificationsFee integer
                )
                """
            )

        if "shipyard_transactions" not in tables:
            # - Create a waypoint specific transactions table:
            #   CREATE TABLE transactions_wp1 PARTITION OF transactions FOR VALUES IN ('wp1');
            # - Use st2.read(timestamp) as timestamp
            cur.execute(
                """
                CREATE TABLE shipyard_transactions
                (
                    shipSymbol text,
                    shipType text,
                    waypointSymbol text,
                    agentSymbol text,
                    price integer,
                    timestamp timestamptz,
                    PRIMARY KEY (waypointSymbol, timestamp)
                ) PARTITION BY LIST (waypointSymbol)
                """
            )

        if "ships" not in tables:
            # - Create a waypoint specific tradegoods table:
            #   CREATE TABLE tradegoods_wp1 PARTITION OF tradegoods FOR VALUES IN ('wp1');
            # - Use st2.now() as timestamp
            cur.execute(
                """
                CREATE TABLE ships
                (
                    waypointSymbol text,
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

    with psycopg.connect(f"dbname=st2 user=postgres") as conn, conn.cursor() as cur:
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
