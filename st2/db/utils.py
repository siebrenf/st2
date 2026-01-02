import json
import os
import subprocess as sp

from st2.db import get_table
from st2.db.static import (
    ACTIVITY,
    ENGINES,
    FACTIONS,
    FRAMES,
    GOODS,
    MODULES,
    MOUNTS,
    REACTORS,
    SHIPS,
    SUPPLY,
    SUPPLY_CHAIN,
    TRAITS_FACTION,
    TRAITS_WAYPOINT,
    TYPES_SYSTEM,
    TYPES_WAYPOINT,
)
from st2.db.static import __file__ as static_init_file
from st2.logging import logger


def update_all():
    """
    Update (almost) all static databases
    """
    # missing DBs: goods, modifiers, ship_events, ship_modes, ship_roles, ship_status
    update_ships()
    update_factions()
    update_waypoints()
    update_supply_chain()
    check_other()


def update_ships():
    """
    Update all ship related static DBs
    """
    _update_ships()
    _update_frames()
    _update_reactors()
    _update_engines()
    _update_modules()
    _update_mounts()


def _reorder(dict_old, order):
    dict_new = {k: dict_old[k] for k in order if k in dict_old}
    if "requirements" in dict_new:
        order = ["power", "crew", "slots"]
        dict_new["requirements"] = _reorder(dict_new["requirements"], order)
    return dict_new


def _update_ships():
    # update ships from logs
    for (
        ship,
        name,
        description,
        frame,
        reactor,
        engine,
        modules,
        mounts,
        crew,
    ) in get_table("ship_templates", header=False):
        price = SHIPS[ship].get("purchasePrice", None)
        SHIPS[ship] = {
            "type": ship,
            "name": name,
            "description": description,
            "purchasePrice": price,
            "frame": frame,
            "reactor": reactor,
            "engine": engine,
            "modules": modules,
            "mounts": mounts,
            "crew": crew,
        }

    # sort ship keys
    for ship in SHIPS.values():
        order = [
            "symbol",
            "name",
            "description",
            "moduleSlots",
            "mountingPoints",
            "fuelCapacity",
            "quality",
            "condition",
            "integrity",
            "requirements",
        ]
        ship["frame"] = _reorder(ship["frame"], order)

        order = [
            "symbol",
            "name",
            "description",
            "powerOutput",
            "quality",
            "condition",
            "integrity",
            "requirements",
        ]
        ship["reactor"] = _reorder(ship["reactor"], order)

        order = [
            "symbol",
            "name",
            "description",
            "speed",
            "quality",
            "condition",
            "integrity",
            "requirements",
        ]
        ship["engine"] = _reorder(ship["engine"], order)

        order = ["symbol", "name", "description", "capacity", "range", "requirements"]
        for i in range(len(ship["modules"])):
            ship["modules"][i] = _reorder(ship["modules"][i], order)

        order = [
            "symbol",
            "name",
            "description",
            "strength",
            "deposits",
            "requirements",
        ]
        for i in range(len(ship["mounts"])):
            ship["mounts"][i] = _reorder(ship["mounts"][i], order)

        order = ["current", "required", "capacity", "rotation", "morale", "wages"]
        ship["crew"] = _reorder(ship["crew"], order)

    version = os.environ["ST_VERSION"]
    session = os.environ["ST_RESET_WINDOW"]
    file_name = static_init_file.replace("__init__.py", "ships.py")
    with open(file_name, "w") as f:
        f.write(f"# SpaceTraders {version}. Last update: {session}\n")
        f.write("SHIPS = " + json.dumps(SHIPS, indent=4).replace("null", "None"))
    sp.check_output(f"black -q {file_name}", shell=True)


def _update_frames():
    for ship in SHIPS.values():
        FRAMES[ship["frame"]["symbol"]] = ship["frame"]

    order = [
        "symbol",
        "name",
        "description",
        "moduleSlots",
        "mountingPoints",
        "fuelCapacity",
        "quality",
        "condition",
        "integrity",
        "requirements",
    ]
    for e in FRAMES.values():
        if isinstance(e, dict):
            e = _reorder(e, order)

    version = os.environ["ST_VERSION"]
    session = os.environ["ST_RESET_WINDOW"]
    file_name = static_init_file.replace("__init__.py", "frames.py")
    with open(file_name, "w") as f:
        f.write(f"# SpaceTraders {version}. Last update: {session}\n")
        f.write("FRAMES = " + json.dumps(FRAMES, indent=4).replace("null", "None"))
    sp.check_output(f"black -q {file_name}", shell=True)


def _update_reactors():
    for ship in SHIPS.values():
        REACTORS[ship["reactor"]["symbol"]] = ship["reactor"]

    order = [
        "symbol",
        "name",
        "description",
        "powerOutput",
        "quality",
        "condition",
        "integrity",
        "requirements",
    ]
    for e in REACTORS.values():
        if isinstance(e, dict):
            e = _reorder(e, order)

    version = os.environ["ST_VERSION"]
    session = os.environ["ST_RESET_WINDOW"]
    file_name = static_init_file.replace("__init__.py", "reactors.py")
    with open(file_name, "w") as f:
        f.write(f"# SpaceTraders {version}. Last update: {session}\n")
        f.write("REACTORS = " + json.dumps(REACTORS, indent=4).replace("null", "None"))
    sp.check_output(f"black -q {file_name}", shell=True)


def _update_engines():
    for ship in SHIPS.values():
        ENGINES[ship["engine"]["symbol"]] = ship["engine"]

    order = [
        "symbol",
        "name",
        "description",
        "speed",
        "quality",
        "condition",
        "integrity",
        "requirements",
    ]
    for e in ENGINES.values():
        if isinstance(e, dict):
            e = _reorder(e, order)

    version = os.environ["ST_VERSION"]
    session = os.environ["ST_RESET_WINDOW"]
    file_name = static_init_file.replace("__init__.py", "engines.py")
    with open(file_name, "w") as f:
        f.write(f"# SpaceTraders {version}. Last update: {session}\n")
        f.write("ENGINES = " + json.dumps(ENGINES, indent=4).replace("null", "None"))
    sp.check_output(f"black -q {file_name}", shell=True)


def _update_modules():
    for ship in SHIPS.values():
        for module in ship["modules"]:
            MODULES[module["symbol"]] = module

    order = ["symbol", "name", "description", "capacity", "range", "requirements"]
    for e in MODULES.values():
        if isinstance(e, dict):
            e = _reorder(e, order)

    version = os.environ["ST_VERSION"]
    session = os.environ["ST_RESET_WINDOW"]
    file_name = static_init_file.replace("__init__.py", "modules.py")
    with open(file_name, "w") as f:
        f.write(f"# SpaceTraders {version}. Last update: {session}\n")
        f.write("MODULES = " + json.dumps(MODULES, indent=4).replace("null", "None"))
    sp.check_output(f"black -q {file_name}", shell=True)


def _update_mounts():
    for ship in SHIPS.values():
        for mount in ship["mounts"]:
            MOUNTS[mount["symbol"]] = mount

    order = [
        "symbol",
        "name",
        "description",
        "strength",
        "deposits",
        "requirements",
    ]
    for e in MOUNTS.values():
        if isinstance(e, dict):
            e = _reorder(e, order)

    version = os.environ["ST_VERSION"]
    session = os.environ["ST_RESET_WINDOW"]
    file_name = static_init_file.replace("__init__.py", "mounts.py")
    with open(file_name, "w") as f:
        f.write(f"# SpaceTraders {version}. Last update: {session}\n")
        f.write("MOUNTS = " + json.dumps(MOUNTS, indent=4).replace("null", "None"))
    sp.check_output(f"black -q {file_name}", shell=True)


def update_factions():
    """
    Update all faction related static DBs
    """
    for symbol, name, description in get_table("traits_faction", header=False):
        TRAITS_FACTION[symbol] = {
            "symbol": symbol,
            "name": name,
            "description": description,
        }

    version = os.environ["ST_VERSION"]
    session = os.environ["ST_RESET_WINDOW"]
    file_name = static_init_file.replace("__init__.py", "traits.py")
    with open(file_name, "w") as f:
        f.write(f"# SpaceTraders {version}. Last update: {session}\n")
        f.write(
            "TRAITS_WAYPOINT = "
            + json.dumps(TRAITS_WAYPOINT, indent=4).replace("null", "None")
        )
        f.write("\n")
        f.write(
            "TRAITS_FACTION = "
            + json.dumps(TRAITS_FACTION, indent=4).replace("null", "None")
        )
    sp.check_output(f"black -q {file_name}", shell=True)

    for symbol, name, description, _, traits, is_recruiting in get_table(
        "factions", header=False
    ):
        FACTIONS[symbol] = {
            "symbol": symbol,
            "name": name,
            "description": description,
            "traits": [TRAITS_FACTION[t] for t in traits],
            "isRecruiting": is_recruiting,
        }

    file_name = static_init_file.replace("__init__.py", "factions.py")
    with open(file_name, "w") as f:
        f.write(f"# SpaceTraders {version}. Last update: {session}\n")
        f.write("FACTIONS = " + json.dumps(FACTIONS, indent=4).replace("true", "True"))
    sp.check_output(f"black -q {file_name}", shell=True)


def update_waypoints():
    """
    Update all waypoint related static DBs
    """
    for symbol, name, description in get_table("traits_waypoint", header=False):
        TRAITS_WAYPOINT[symbol] = {
            "symbol": symbol,
            "name": name,
            "description": description,
        }

    version = os.environ["ST_VERSION"]
    session = os.environ["ST_RESET_WINDOW"]
    file_name = static_init_file.replace("__init__.py", "traits.py")
    with open(file_name, "w") as f:
        f.write(f"# SpaceTraders {version}. Last update: {session}\n")
        f.write(
            "TRAITS_WAYPOINT = "
            + json.dumps(TRAITS_WAYPOINT, indent=4).replace("null", "None")
        )
        f.write("\n")
        f.write(
            "TRAITS_FACTION = "
            + json.dumps(TRAITS_FACTION, indent=4).replace("null", "None")
        )
    sp.check_output(f"black -q {file_name}", shell=True)

    wp_types = set(TYPES_WAYPOINT)
    for row in get_table("waypoints", header=False):
        wp_types.add(row[2])

    system_types = set(TYPES_SYSTEM)
    for row in get_table("systems", header=False):
        system_types.add(row[1])

    file_name = static_init_file.replace("__init__.py", "types.py")
    with open(file_name, "w") as f:
        f.write(f"# SpaceTraders {version}. Last update: {session}\n")
        f.write("TYPES_WAYPOINT = " + json.dumps(sorted(wp_types), indent=4))
        f.write("\n")
        f.write("TYPES_SYSTEM = " + json.dumps(sorted(system_types), indent=4))
    sp.check_output(f"black -q {file_name}", shell=True)


def update_supply_chain():
    """
    Update the supply chain DB
    """
    for export, imports in get_table("supply_chain", header=False):
        SUPPLY_CHAIN[export] = imports

    version = os.environ["ST_VERSION"]
    session = os.environ["ST_RESET_WINDOW"]
    file_name = static_init_file.replace("__init__.py", "supply_chain.py")
    with open(file_name, "w") as f:
        f.write(f"# SpaceTraders {version}. Last update: {session}\n")
        f.write("# export: [imports]\n")
        f.write("SUPPLY_CHAIN = " + json.dumps(SUPPLY_CHAIN, indent=4))
    sp.check_output(f"black -q {file_name}", shell=True)


def check_other():
    """
    Report changes in (most) remaining static DBs
    """
    goods = set()
    types = set()
    supplies = set()
    activity = set()
    for row in get_table("market_tradegoods", header=False):
        goods.add(row[2])
        types.add(row[4])
        supplies.add(row[5])
        activity.add(row[6])

    ships = set()
    for row in get_table("shipyard_ships", header=False):
        ships.add(row[2])
        supplies.add(row[3])
        activity.add(row[4])

    if sorted(types) != ["EXCHANGE", "EXPORT", "IMPORT"]:
        logger.info(f"Types changed: {types}")

    if sorted(supplies) != sorted(SUPPLY):
        logger.info(f"Supply levels changed: {supplies}")

    activity.discard(None)
    if sorted(activity) != sorted(ACTIVITY):
        logger.info(f"Activity levels changed: {activity}")

    for good in goods:
        if good not in GOODS:
            logger.info(f"New tradegood found: {good}")

    return goods, types, supplies, activity, ships
