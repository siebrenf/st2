import random
import string

import psycopg


def api_agent(request):
    """
    Register an agent to use for agent-independent API requests.
    This is to notice server resets immediately.
    """
    role = "reset detection"
    with psycopg.connect(f"dbname=st2 user=postgres") as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT * FROM agents WHERE role = %s",
            (role,),
        )
        ret = cur.fetchone()
        if ret is None:
            symbol, token = register_random_agent(request)
            cur.execute(
                """
                INSERT INTO agents
                (symbol, token, role)
                VALUES (%s, %s, %s)
                """,
                (symbol, token, role),
            )
            conn.commit()
        else:
            symbol, token, role = ret
    return symbol, token


def register_random_agent(request, faction="COSMIC", max_tries=10):
    tries = []
    while len(tries) < max_tries:
        try:
            symbol = "".join(
                random.choices(string.ascii_lowercase + string.digits, k=8)
            )
            payload = {"symbol": symbol, "faction": faction}
            token = request.post("register", 3, None, payload)["data"]["token"]
            return symbol, token
        except Exception as e:
            tries.append(e)
    for error in tries:
        print(str(error))
    raise tries[-1]
