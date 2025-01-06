import multiprocessing as mp

from st2.request import Request, RequestMp, messenger


def test_request():
    request = Request()
    ret = request.get(endpoint="")
    assert "status" in ret


def test_requestmp():
    manager = mp.Manager()
    qa_pairs = (
        (manager.Queue(), manager.dict()),  # high prio (e.g. high quality trades)
        (manager.Queue(), manager.dict()),  # mid prio (e.g. normal trades & exploring)
        (manager.Queue(), manager.dict()),  # low prio (e.g. probing markets)
        (manager.Queue(), manager.dict()),  # no prio (e.g. building the sector map)
    )
    api_handler = mp.Process(
        target=messenger,
        kwargs={
            "qa_pairs": qa_pairs,
        },
    )
    api_handler.start()
    ret = manager.dict()  # collect the response JSON

    def get_status(qa_pairs, name, ret):  # noqa
        request = RequestMp(qa_pairs)
        ret[name] = request.get(endpoint="", priority=0)

    p2 = mp.Process(
        target=get_status,
        kwargs={
            "qa_pairs": qa_pairs,
            "name": 1,
            "ret": ret,
        },
    )
    p3 = mp.Process(
        target=get_status,
        kwargs={
            "qa_pairs": qa_pairs,
            "name": 2,
            "ret": ret,
        },
    )
    p2.start()
    p3.start()
    p2.join()
    p3.join()
    assert "status" in ret[1]
    assert "status" in ret[2]

    # This prevents the BrokenPipeError
    #  because the script is garbage collected while running infinitely
    api_handler.terminate()
    api_handler.join()
