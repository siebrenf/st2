from json import dumps
from time import sleep
from uuid import uuid1

from requests.exceptions import ConnectionError, JSONDecodeError  # noqa
from requests_ratelimiter import LimiterSession  # noqa

from st2.exceptions import GameError
from st2.logging import logger

DEBUG = False


class Request:
    """
    Handles all API requests.
    Only one instance of this class should be used per IP address & agent.

    To use this class in a multiprocess context, see main.py.
    """

    base_url = "https://api.spacetraders.io/v2/"
    rate_limit_codes = [
        429,  # too many requests
    ]
    ddos_protection_codes = [
        502,  # way too many requests
    ]
    ddos_protection_sleep = 210
    server_down_codes = [
        500,  # unexpected server error
        503,  # service unavailable
        504,  # gateway timeout
    ]
    server_down_sleep = 3

    def __init__(self, qa_pairs=None, priority=None, token=None):
        _ = qa_pairs
        _ = priority
        _ = token
        self.session = LimiterSession(
            per_second=2,
            limit_statuses=self.rate_limit_codes,
        )

    def __copy__(self, priority=None, token=None):
        return Request()

    def copy(self, priority=None, token=None):
        _ = priority
        _ = token
        return self.__copy__()

    def _request(
        self,
        method: str,
        endpoint: str,
        token: str = None,
        data: dict = None,
        params: dict = None,
    ):
        if method == "get":
            method = self.session.get
        elif method == "post":
            method = self.session.post
        elif method == "patch":
            method = self.session.patch
        else:
            raise NotImplementedError
        url = self.base_url + endpoint
        headers = {
            "Accept": "application/json",
        }
        if data:
            data = dumps(data)
            headers["Content-Type"] = "application/json"
        if token:
            headers["Authorization"] = f"Bearer {token}"

        # debug spurious API calls
        if DEBUG:
            d = f"{data=}" if data else ""
            p = f"{params=}" if params and params.get("page", 1) != 1 else ""
            logger.debug(f"{endpoint=} {d} {p}")

        status_code, error_code, resp_json = self._request_response(
            method, url, headers, data, params
        )
        if status_code in [200, 201]:
            return resp_json

        # check for errors
        if status_code == 204:  # no-content
            logger.debug(f"Endpoint '{endpoint}' returned no content (204)")
        elif error_code in [4221, 4224]:  # survey expired/exhausted
            pass  # TODO: capture /w try-except in ship.extract()
        # elif status_code == 401:  # server reset, token outdated
        #     message = resp_json.get("error", {}).get("message", "")
        #     raise ServerResetError(
        #         f"request_{endpoint=} error_{message=} {self.headers=}"
        #     )
        elif "error" in resp_json:
            self._raise_formatted_error(resp_json, url, data, status_code)
        else:
            raise NotImplementedError(
                f"Unknown situation. Status code: {status_code}. "
                f"Endpoint: {endpoint} Data: {data} Params: {params}"
            )
        return resp_json

    def _request_response(self, method, url, headers, data=None, params=None):
        """Make the request until a response is given"""
        while True:
            try:
                response = method(url, headers=headers, data=data, params=params)
            except ConnectionError:
                # Server is still processing the request. Patience...
                sleep(0.1)
                continue
            try:
                resp_json = response.json()
            except JSONDecodeError:
                resp_json = {}
            status_code = response.status_code
            error = resp_json.get("error", {})
            if not isinstance(error, dict):
                msg = f"An error occurred but no error dict was returned.\n\t"
                req = f"Request: {url[8:]}\n\t"
                udata = "" if data is None else f"Request data: {data}\n\t"
                api_code = f"Request error code: {status_code}\n\t"
                raise GameError(resp_json, f"\n\n\t{msg}{req}{udata}{api_code}")
            if status_code in self.rate_limit_codes:
                logger.debug(resp_json.get("error", {}).get("message", resp_json))
                sleep(resp_json.get("error", {}).get("data", {}).get("retryAfter", 1))
            elif status_code in self.ddos_protection_codes:
                logger.warning(f"Error code 502: {resp_json}")
                sleep(self.ddos_protection_sleep)
            elif status_code in self.server_down_codes:
                logger.warning(
                    f"Server down (error code {status_code}). "
                    f"Retrying in {self.server_down_sleep} sec"
                )
                sleep(self.server_down_sleep)
            else:
                error_code = error.get("code")
                return status_code, error_code, resp_json

    @staticmethod
    def _raise_formatted_error(resp_json, url, data, status_code):
        resp_error = resp_json["error"]
        msg = f'Message: {resp_error["message"]}\n\t'
        req = f"Request: {url[8:]}\n\t"
        udata = "" if data is None else f"Request data: {data}\n\t"
        edata = resp_error.get("data")
        edata = "" if edata is None else f"Error data: {edata}\n\t"
        api_code = f"Request error code: {status_code}\n\t"
        game_code = ""
        if resp_error["code"] != status_code:
            game_code = f'Game error code: {resp_error["code"]}\n\t'
        # https://docs.spacetraders.io/api-guide/response-errors
        raise GameError(
            resp_json, f"\n\n\t{msg}{req}{udata}{edata}{api_code}{game_code}"
        )

    def get(self, endpoint, priority=None, token=None, params=None):
        _ = priority
        if endpoint == "status":
            endpoint = ""
        if params is None:
            params = {"page": 1, "limit": 20}

        return self._request("get", endpoint, token, None, params)

    def get_all(self, endpoint, priority=None, token=None):
        """yield all results from the get request, not just the first 20 results."""
        total = 0
        page = 0
        while True:
            page += 1
            resp_json = self.get(endpoint, priority, token, {"page": page, "limit": 20})
            yield resp_json
            total += len(resp_json["data"])
            if total == resp_json["meta"]["total"]:
                break

    def post(self, endpoint, priority=None, token=None, data=None):
        _ = priority
        return self._request("post", endpoint, token, data)

    def patch(self, endpoint, priority=None, token=None, data=None):
        _ = priority
        return self._request("patch", endpoint, token, data)


class RequestMp:
    """
    Request helper class for multiprocess contexts.
    Uses the same arguments, but requires additional `priority`.

    See main.py.
    """

    def __init__(self, qa_pairs, priority=1, token=None):
        self.queues = {}
        self.priority = priority
        for priority, (queue, answer_dict) in enumerate(qa_pairs):
            self.queues[priority] = (queue, answer_dict)
        self.token = token
        self.sleep = 0.01

    def __copy__(self, priority=None, token=None):
        if priority is None:
            priority = self.priority
        if token is None:
            token = self.token
        return RequestMp(tuple(self.queues.values()), priority, token)

    def copy(self, priority=None, token=None):
        return self.__copy__(priority, token)

    def _request(self, method, endpoint, priority, token, data=None, params=None):
        if priority is None:
            priority = self.priority
        if token is None:
            token = self.token
        queue, answer_dict = self.queues[priority]
        uuid = uuid1()
        queue.put((uuid, method, endpoint, token, data, params))
        while uuid not in answer_dict:
            sleep(self.sleep)
        ret = answer_dict.pop(uuid)
        if isinstance(ret, Exception):
            raise ret
        return ret

    def get(self, endpoint, priority=None, token=None, params=None):
        if endpoint == "status":
            endpoint = ""
        if params is None:
            params = {"page": 1, "limit": 20}

        return self._request("get", endpoint, priority, token, None, params)

    def get_all(self, endpoint, priority=None, token=None):
        """yield all results from the get request, not just the first 20 results."""
        total = 0
        page = 0
        while True:
            page += 1
            resp_json = self.get(endpoint, priority, token, {"page": page, "limit": 20})
            yield resp_json
            total += len(resp_json["data"])
            if total == resp_json["meta"]["total"]:
                break

    def post(self, endpoint, priority=None, token=None, data=None):
        return self._request("post", endpoint, priority, token, data)

    def patch(self, endpoint, priority=None, token=None, data=None):
        return self._request("patch", endpoint, priority, token, data)


def messenger(qa_pairs):
    """
    Delivers API requests between Request() and any number of RequestMp() instances.

    :param qa_pairs: can contain any number of tuples, in order of importance (high -> low).
    Each tuple should contain a queue and a dictionary.
    :return: None.
    The messenger draws API requests from the queues
    (which must be a tuple in the form seen below)
    and stores the results in the answer dicts.
    """
    session = Request()
    while True:
        for queue, answer_dict in qa_pairs:
            try:
                if queue.empty():
                    continue  # next queue
                uuid, method, endpoint, token, data, params = queue.get()
            except (ConnectionResetError, EOFError) as e:
                if DEBUG:
                    logger.debug(
                        f"""{str(type(e)).split("'")[1]} from messenger(): {e}"""
                    )
                return  # script killed
            except Exception as e:
                raise e

            try:
                ret = session._request(method, endpoint, token, data, params)  # noqa
            except Exception as exc:
                ret = exc
            answer_dict[uuid] = ret
            break  # next iteration
        sleep(0.01)  # no requests
