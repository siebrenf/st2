from asyncio import sleep

from psycopg import connect
from psycopg.rows import dict_row

from st2 import time
from st2.agent import get_agent, get_agent_public
from st2.contract import Contract, get_active_contract
from st2.logging import logger
from st2.request import RequestMp
from st2.ship import Ship
from st2.system import System, get_start_systems

DEBUG = True


@logger.catch  # catch errors in a separate thread
async def ai_contract_controller(
    agent_symbol,
    qa_pairs,
    priority=1,
    interval=60,
    verbose=False,
):
    # TODO: track contract expenses and payments
    token = get_agent(agent_symbol)["token"]
    request = RequestMp(qa_pairs, priority=priority, token=token)
    while True:
        contract = get_active_contract(agent_symbol)

        if contract is None:
            # stop all current and queued deliver tasks (contract expired)
            queued_tasks_to_clear, current_tasks_to_cancel = _get_deliver_tasks(
                agent_symbol
            )
            if verbose:
                n = len(queued_tasks_to_clear) + len(current_tasks_to_cancel)
                if n:
                    logger.warning(f"{n} ships with outdated deliver tasks found!")
            for ship in queued_tasks_to_clear:
                _dequeue_task(ship, reason="contract expired")
            for ship in current_tasks_to_cancel:
                _cancel_task(ship, reason="contract expired")

            # negotiate a new contract
            system_symbol = _get_start_system_with_most_traders(agent_symbol)
            ship_symbol = _get_probe_for_negotiations(agent_symbol, system_symbol)
            ship = Ship(ship_symbol, request)
            if t := ship.nav_remaining():
                await sleep(t)
            contract = ship.contract(verbose)

        if not contract["accepted"]:
            # 1) determine if there are traders in all destination systems
            # 2) determine all markets are loaded into the database
            # 3) determine if the goods can be purchased in the destination systems
            doable = True
            reason = []
            sleep_timer = None
            system2trade_goods = {}
            for term in contract["terms"]["deliver"]:
                system_symbol = term["destinationSymbol"].rsplit("-", 1)[0]
                if system_symbol not in system2trade_goods:
                    system2trade_goods[system_symbol] = []
                system2trade_goods[system_symbol].append(term["tradeSymbol"])
            for system_symbol, trade_goods in system2trade_goods.items():
                ship_tasks = _get_active_traders(agent_symbol, system_symbol)
                if not ship_tasks:
                    doable = False
                    reason = f"No traders in {system_symbol}."
                    sleep_timer = interval  # new traders may be assigned to the system
                    break
                system = System(system_symbol, request)
                # TODO: use ships to scout all (possible) markets (if not in DB), then refresh system
                for good in trade_goods:
                    wps = system.markets_with(good, "sells")
                    if not wps:
                        doable = False
                        reason.append(good)
                        sleep_timer = time.remaining(contract["deadlineToAccept"])
                if not doable:
                    reason = "No" + ", ".join(reason) + f" for sale in {system_symbol}."
                    break
            if doable:
                Contract(contract["id"], request).accept(verbose)
            else:
                if DEBUG:
                    logger.debug(f"Contract not doable: {reason}")
                await sleep(sleep_timer)
                continue

        # TODO: make dependent on contract
        if get_agent_public(agent_symbol)["credits"] < 150_000:
            if DEBUG:
                logger.debug(f"Too poor for contract work")
            await sleep(interval)
            continue

        # fulfill (part of) a term
        fulfill_contract = True
        for term in contract["terms"]["deliver"]:
            units = term["unitsRequired"] - term["unitsFulfilled"]
            if units <= 0:
                continue  # next good
            good = term["tradeSymbol"]
            deliver_wp = term["destinationSymbol"]
            system_symbol = deliver_wp.rsplit("-", 1)[0]
            fulfill_contract = False

            # currently active tasks in this system
            ship_tasks = _get_active_traders(agent_symbol, system_symbol)
            available_traders = set()
            current = 0
            queued = 0
            for tasks in ship_tasks:
                ship = tasks["symbol"]
                if (
                    tasks["current"] is None
                    or tasks["queued"] is None
                    or tasks["queued"].startswith("trade ")
                ):
                    available_traders.add(ship)

                for key in ["current", "queued"]:
                    if str(tasks[key]).startswith("deliver "):
                        task_split = tasks[key].split(" ")
                        if task_split[1] == good and task_split[4] == deliver_wp:
                            u = int(task_split[2])
                            units -= u
                            if key == "current":
                                current += u
                            else:
                                queued += u

            if units <= 0:
                continue  # remaining units are already tasked
            if DEBUG:
                logger.debug(
                    f"{len(available_traders)} ships available to deliver {good} to {deliver_wp}"
                )
            if len(available_traders) == 0:
                break  # try again later

            # select the cheapest waypoint to purchase the goods from
            system = System(system_symbol, request)
            best = None, float("inf")
            for wp, md in system.markets_with(good, "sells").items():
                price = md["purchasePrice"]
                # if price > 1.25 * reward_per_unit[good]:  # TODO: ?
                #     continue
                if price < best[-1]:
                    best = wp, price
            purchase_wp = best[0]

            # select a ship to deliver the goods
            ship, units = _get_trader(available_traders, units)
            task = f"deliver {good} {units} {purchase_wp} {deliver_wp}"
            _queue_task(ship, task)
            queued += units
            if DEBUG:
                remaining = (
                    term["unitsRequired"] - term["unitsFulfilled"] - current - queued
                )
                logger.debug(
                    "Contract delivery: "
                    f"{remaining} remaining/"
                    f"{current} currently underway/"
                    f"{queued} queued underway/"
                    f"{term["unitsFulfilled"]} fulfilled/"
                    f"{term["unitsRequired"]} total {good}"
                )
            break

        if fulfill_contract:
            Contract(contract["id"], request).fulfill(verbose)
        else:
            await sleep(interval)


def _get_active_traders(agent_symbol, system_symbol):
    with connect(
        "dbname=st2 user=postgres", row_factory=dict_row
    ) as conn, conn.cursor() as cur:
        assigned_ships = cur.execute(
            """
            SELECT * FROM "tasks" 
            WHERE "agentSymbol" = %s 
            AND "pname" = %s
            AND "symbol" IN (
                SELECT "symbol" FROM "ships"
                WHERE "agentSymbol" = %s
                AND "nav" ->> 'systemSymbol' = %s
            )
            """,
            (agent_symbol, "traders", agent_symbol, system_symbol),
        ).fetchall()
    return assigned_ships


def _get_deliver_tasks(agent_symbol):
    with connect(
        "dbname=st2 user=postgres", row_factory=dict_row
    ) as conn, conn.cursor() as cur:
        ship_tasks = cur.execute(
            """
            SELECT * FROM "tasks" 
            WHERE "agentSymbol" = %s 
            AND "pname" = %s
            """,
            (agent_symbol, "traders"),
        ).fetchall()
    queued_tasks_to_clear = []
    current_tasks_to_cancel = []
    for tasks in ship_tasks:
        ship = tasks["symbol"]
        if str(tasks["current"]).startswith("deliver "):
            current_tasks_to_cancel.append(ship)
        if str(tasks["queued"]).startswith("deliver "):
            queued_tasks_to_clear.append(ship)
    return queued_tasks_to_clear, current_tasks_to_cancel


def _get_trader(available_traders, units):
    """
    Return the trader with the best fitting cargo capacity.
    Speed is used as tiebreaker.
    """
    best = None, 0, 0
    for ship_symbol in available_traders:
        with connect(
            "dbname=st2 user=postgres", row_factory=dict_row
        ) as conn, conn.cursor() as cur:
            ship = cur.execute(
                "SELECT * FROM ships WHERE symbol = %s", (ship_symbol,)
            ).fetchone()
        cargo_capacity = ship["cargo"]["capacity"]
        speed = ship["engine"]["speed"]
        if cargo_capacity >= units:
            score = 1 + units / cargo_capacity + speed / 1000
            deliver_units = units
        else:
            score = cargo_capacity / units + speed / 1000
            deliver_units = cargo_capacity
        if score > best[1]:
            best = ship_symbol, deliver_units, score
    ship_symbol, deliver_units, score = best
    return ship_symbol, deliver_units


def _queue_task(ship, task):
    with connect("dbname=st2 user=postgres") as conn, conn.cursor() as cur:
        cur.execute(
            """
            UPDATE tasks
            SET "queued" = %s
            WHERE "symbol" = %s
            """,
            (task, ship),
        )
    if DEBUG:
        logger.debug(f"Queueing {task=} to {ship}")


def _cancel_task(ship, reason=None, task=None):
    with connect("dbname=st2 user=postgres") as conn, conn.cursor() as cur:
        cur.execute(
            """
            UPDATE tasks
            SET "cancel" = %s
            WHERE "symbol" = %s
            """,
            (True, ship),
        )
    if DEBUG:
        msg = "Cancelled " + (f"{task=}" if task else "task") + f" for {ship}"
        if reason:
            msg += f" {reason=}"
        logger.debug(msg)


def _dequeue_task(ship, reason=None, task=None):
    with connect("dbname=st2 user=postgres") as conn, conn.cursor() as cur:
        cur.execute(
            """
            UPDATE tasks
            SET "queued" = %s
            WHERE "symbol" = %s
            """,
            (None, ship),
        )
    if DEBUG:
        msg = "Unqueued " + (f"{task=}" if task else "task") + f" for {ship}"
        if reason:
            msg += f" {reason=}"
        logger.debug(msg)


def _get_start_system_with_most_traders(agent_symbol):
    system2ship = {}
    for ship in _get_start_systems_traders(agent_symbol):
        system_symbol = ship["nav"]["systemSymbol"]
        if system_symbol not in system2ship:
            system2ship[system_symbol] = []
        system2ship[system_symbol].append(ship)
    best = None, 0
    for system_symbol, ships in system2ship.items():
        n = len(ships)
        if n > best[1]:
            best = system_symbol, n
    return best[0]


def _get_start_systems_traders(agent_symbol):
    faction = get_agent_public(agent_symbol)["startingFaction"]
    start_systems = get_start_systems(faction)
    with connect(
        "dbname=st2 user=postgres", row_factory=dict_row
    ) as conn, conn.cursor() as cur:
        traders = cur.execute(
            """
            SELECT * FROM "ships"
            WHERE "agentSymbol" = %s 
            AND "nav" ->> 'systemSymbol' = ANY(%s)
            AND "symbol" IN (
                SELECT "symbol" FROM "tasks"
                WHERE "agentSymbol" = %s
                AND "pname" = %s
            )
            """,
            [agent_symbol, start_systems, agent_symbol, "traders"],
        ).fetchall()
    return traders


def _get_probe_for_negotiations(agent_symbol, system_symbol):
    with connect(
        "dbname=st2 user=postgres", row_factory=dict_row
    ) as conn, conn.cursor() as cur:
        probes = cur.execute(
            """
            SELECT * FROM "ships"
            WHERE "agentSymbol" = %s 
            AND "nav" ->> 'systemSymbol' = %s
            AND "symbol" IN (
                SELECT "symbol" FROM tasks
                WHERE "agentSymbol" = %s
                AND "pname" = %s
            )
            """,
            [agent_symbol, system_symbol, agent_symbol, "probes"],
        ).fetchall()
    if probes is None:
        raise NotImplementedError(f"No probes in start system {system_symbol}")
    best = None, float("inf")
    for ship in probes:
        t = time.remaining(ship["nav"]["route"]["arrival"])
        if t < best[1]:
            best = ship["symbol"], t
    return best[0]
