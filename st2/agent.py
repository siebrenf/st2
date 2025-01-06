import random
import string

from st2.caching import cache


def api_agent(request):
    """
    Register an agent to use for agent-independent API requests.
    This is to notice server resets immediately.
    """
    tries = []
    while "api_agent" not in cache:
        try:
            symbol = "".join(
                random.choices(string.ascii_lowercase + string.digits, k=8)
            )
            payload = {"symbol": symbol, "faction": "COSMIC"}
            data = request.post("register", 3, None, payload)["data"]
            cache["api_agent"] = (symbol, data["token"])
        except Exception as e:
            tries.append(e)
            if len(tries) == 10:
                for error in tries:
                    print(str(error))
                raise e
    return cache["api_agent"]
