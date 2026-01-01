import json
import subprocess as sp

from st2.db import get_table
from st2.db.static import (
    ACTIVITY,
    ENGINES,
    FRAMES,
    GOODS,
    MODULES,
    MOUNTS,
    REACTORS,
    SHIPS,
    SUPPLY,
)
from st2.db.static import __file__ as static_init_file


def _reorder(dict_old, order):
    dict_new = {k: dict_old[k] for k in order if k in dict_old}
    if "requirements" in dict_new:
        order = ["power", "crew", "slots"]
        dict_new["requirements"] = _reorder(dict_new["requirements"], order)
    return dict_new


def update_ships():
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
    ) in get_table("ship_templates", column_names=False):
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

    file_name = static_init_file.replace("__init__.py", "ships.py")
    with open(file_name, "w") as f:
        f.write("SHIPS = " + json.dumps(SHIPS, indent=4).replace("null", "None"))
    sp.check_output(f"black -q {file_name}", shell=True)


def update_frames():
    for symbol, ship in SHIPS.items():
        FRAMES[symbol] = ship["frame"]

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

    file_name = static_init_file.replace("__init__.py", "frames.py")
    with open(file_name, "w") as f:
        f.write("FRAMES = " + json.dumps(FRAMES, indent=4).replace("null", "None"))
    sp.check_output(f"black -q {file_name}", shell=True)


def update_reactors():
    for symbol, ship in SHIPS.items():
        REACTORS[symbol] = ship["reactor"]

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

    file_name = static_init_file.replace("__init__.py", "reactors.py")
    with open(file_name, "w") as f:
        f.write("REACTORS = " + json.dumps(REACTORS, indent=4).replace("null", "None"))
    sp.check_output(f"black -q {file_name}", shell=True)


def update_engines():
    for symbol, ship in SHIPS.items():
        ENGINES[symbol] = ship["engine"]

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

    file_name = static_init_file.replace("__init__.py", "engines.py")
    with open(file_name, "w") as f:
        f.write("ENGINES = " + json.dumps(ENGINES, indent=4).replace("null", "None"))
    sp.check_output(f"black -q {file_name}", shell=True)


def update_modules():
    for symbol, ship in SHIPS.items():
        for module in ship["modules"]:
            MODULES[module["symbol"]] = module

    order = ["symbol", "name", "description", "capacity", "range", "requirements"]
    for e in MODULES.values():
        if isinstance(e, dict):
            e = _reorder(e, order)

    file_name = static_init_file.replace("__init__.py", "modules.py")
    with open(file_name, "w") as f:
        f.write("MODULES = " + json.dumps(MODULES, indent=4).replace("null", "None"))
    sp.check_output(f"black -q {file_name}", shell=True)


def update_mounts():
    for symbol, ship in SHIPS.items():
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

    file_name = static_init_file.replace("__init__.py", "mounts.py")
    with open(file_name, "w") as f:
        f.write("MOUNTS = " + json.dumps(MOUNTS, indent=4).replace("null", "None"))
    sp.check_output(f"black -q {file_name}", shell=True)


# def update_tables():
#     goods = set()
#     types = set()
#     supplies = set()
#     activity = set()
#     for row in get_table("market_tradegoods", column_names=False):
#         goods.add(row[2])
#         types.add(row[4])
#         supplies.add(row[5])
#         activity.add(row[6])
#
#     ships = set()
#     for row in get_table("shipyard_ships", column_names=False):
#         ships.add(row[2])
#         supplies.add(row[3])
#         activity.add(row[4])
#
#     if sorted(types) != ['EXCHANGE', 'EXPORT', 'IMPORT']:
#         print(f"Types changed: {types}")
#
#     if sorted(supplies) != sorted(SUPPLY):
#         print(f"Supply levels changed: {supplies}")
#
#     activity.discard(None)
#     if sorted(activity) != sorted(ACTIVITY):
#         print(f"Activity levels changed: {activity}")
#
#     for good in goods:
#         if good not in GOODS:
#             print(f"New tradegood found: {good}")
#
#     for ship in ships:
#         if ship not in GOODS:
#             print(f"New ship found: {ship}")
#
#     return goods, types, supplies, activity, ships
