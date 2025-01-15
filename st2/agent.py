import random
import string

from psycopg import connect


def api_agent(request, priority):
    """
    Register an agent to use for agent-independent API requests.
    This is to notice server resets immediately.
    """
    role = "reset detection"
    with connect("dbname=st2 user=postgres") as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT * FROM agents WHERE role = %s",
            (role,),
        )
        ret = cur.fetchone()
        if ret is None:
            data = register_random_agent(request, priority)
            cur.execute(
                """
                INSERT INTO agents
                (symbol, token, role)
                VALUES (%s, %s, %s)
                """,
                (data["agent"]["symbol"], data["token"], role),
            )
            conn.commit()
        else:
            symbol, token, role = ret
    return symbol, token


def register_random_agent(request, priority, faction="COSMIC", max_tries=10):
    tries = []
    while len(tries) < max_tries:
        try:
            symbol = "".join(
                random.choices(string.ascii_lowercase + string.digits, k=8)
            )
            payload = {"symbol": symbol, "faction": faction}
            data = request.post("register", priority, None, payload)["data"]
            return data  # keys: ['token', 'agent', 'contract', 'faction', 'ship']
        except Exception as e:
            tries.append(e)
    for error in tries:
        print(str(error))
    raise tries[-1]
