import json
import subprocess as sp

from st2.db import get_table
from st2.db.static import ACTIVITY, GOODS, SHIPS, SUPPLY
from st2.db.static import __file__ as static_init_file


def update_ships():
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

    file_name = static_init_file.replace("__init__.py", "ships.py")
    with open(file_name, "w") as f:
        f.write("SHIPS = " + json.dumps(SHIPS, indent=4).replace("null", "None"))
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
