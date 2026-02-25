from asyncio import sleep

from psycopg import connect
from psycopg.rows import dict_row

from st2.ai.siphon import get_fuel_minimum
from st2.logging import logger
from st2.pathing.travel import travel
from st2.ship import Ship
from st2 import time


@logger.catch  # catch errors in a separate thread
async def ai_survey_start_system(
    ship_symbol,
    trait,
    extract_wp,
    sell_wp,
    whitelist,
    qa_pairs,
    priority=2,
    verbose=False,
):
    ship = Ship(ship_symbol, qa_pairs=qa_pairs, priority=priority)
    fuel_minimum = get_fuel_minimum(ship, extract_wp, sell_wp)
    mode = "CRUISE"
    if fuel_minimum > ship["fuel"]["capacity"]:
        mode = "DRIFT"
    whitelist = whitelist.split(",")
    if verbose:
        logger.info(
            f"{ship.name()} will survey the {trait} at {extract_wp}"
        )

    # travel to the extract waypoint
    if ship["nav"]["waypointSymbol"] not in [sell_wp, extract_wp]:
        await travel(ship, sell_wp, explore=False, verbose=False)
        ship.nav_patch(mode)
        ship.navigate(extract_wp, verbose=False)
    elif ship["nav"]["waypointSymbol"] == sell_wp:
        await sleep(ship.nav_remaining())
        ship.nav_patch(mode)
        ship.navigate(extract_wp, verbose=False)
    elif ship["nav"]["waypointSymbol"] == extract_wp:
        await sleep(ship.nav_remaining())

    while True:
        await sleep(ship.cooldown_remaining())

        surveys = ship.survey(verbose=False)
        compare_surveys(surveys, extract_wp, sell_wp, whitelist)


def compare_surveys(surveys, extract_wp, sell_wp, whitelist):
    current_survey = get_waypoint_survey(extract_wp)
    if current_survey is None:
        current_survey = compare_surveys_db(extract_wp, sell_wp, whitelist)
    trade_goods = get_tradegoods(sell_wp)
    score = get_survey_score(current_survey, trade_goods, whitelist)
    best = current_survey, score
    for survey in surveys:
        score = get_survey_score(survey, trade_goods, whitelist)
        if score > best[1]:
            best = survey, score
    survey = best[0]
    if survey != current_survey:
        set_waypoint_survey(extract_wp, survey)


def compare_surveys_db(extract_wp, sell_wp, whitelist):
    with connect("dbname=st2 user=postgres", row_factory=dict_row) as conn, conn.cursor() as cur:
        surveys = cur.execute(
            """SELECT * FROM surveys WHERE symbol = %s AND expiration > %s""",
            (extract_wp, time.now()),
        ).fetchall()
    if surveys is None:
        return None

    best = None, 0
    trade_goods = get_tradegoods(sell_wp)
    for survey in surveys:
        score = get_survey_score(survey, trade_goods, whitelist)
        if score > best[1]:
            best = survey, score
    survey = best[0]
    set_waypoint_survey(extract_wp, survey)
    return survey

def get_tradegoods(waypoint_symbol):
    # latest market information
    with connect(
        "dbname=st2 user=postgres", row_factory=dict_row
    ) as conn, conn.cursor() as cur:
        trade_goods = cur.execute(
            """
            SELECT DISTINCT ON ("symbol") * FROM market_tradegoods
            WHERE "waypointSymbol" = %s
            ORDER BY "symbol", "timestamp" DESC;
            """,
            (waypoint_symbol,),
        ).fetchall()
    return trade_goods


def get_survey_score(survey, trade_goods, whitelist=None):
    # score: higher is better
    score = 0
    goods = set(survey["deposits"])
    if whitelist:
        goods.intersection_update(whitelist)
    for tg in trade_goods:
        if tg["symbol"] not in goods:
            continue
        n = survey["deposits"].count(tg["symbol"])
        score += tg["sellPrice"] * n
    return score


def get_waypoint_survey(waypoint_symbol):
    with connect("dbname=st2 user=postgres", row_factory=dict_row) as conn, conn.cursor() as cur:
        survey = cur.execute(
            """
            SELECT * FROM surveys 
            WHERE signature IN (
                SELECT signature 
                FROM waypoint_survey 
                WHERE symbol = %s
            )
            """,
            (waypoint_symbol,),
        ).fetchone()
        return survey


def set_waypoint_survey(waypoint_symbol, survey=None):
    if survey is None:
        survey = {"signature": None}
    with connect("dbname=st2 user=postgres") as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO waypoint_survey (symbol, signature)
            VALUES (%s, %s)
            ON CONFLICT ("symbol") DO UPDATE
            SET "signature" = EXCLUDED."signature"
            """,
            (waypoint_symbol, survey["signature"])
        )
