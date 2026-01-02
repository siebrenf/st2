"""
Create a number of FIFO queues in priority order (high -> low) and start the `api_handler` process.
Now, any process can make API requests using helper class `Request(qa_pairs)`.

Example:
    ```
    from st2.requests import RequestMp

    request = RequestMp(qa_pairs)
    request.get(endpoint="my/ships", priority=3, token="abc123")
    ```
"""

if __name__ == "__main__":
    from st2.startup import game_server, api_server
    from st2.request import RequestMp

    game_server()
    manager, api_handler, qa_pairs = api_server()
    request = RequestMp(qa_pairs, priority=0, token=None)

    # update databases
    from st2.stargazers import merchant, ambassador, astronomer, cartographer

    merchant(request, priority=0)
    ambassador(request, priority=0)
    astronomer(request, priority=0)
    cartographer(request, priority=0, chart="start systems")
    cartographer(request, priority=3, chart="gate systems")

    # (Re)start the start system probing
    from st2.spies import spymaster, detective, private_eye

    detective(request, priority=3)

    spymaster(request, priority=3)

    import atexit
    import multiprocessing as mp
    from st2.ai import taskmaster

    pname = "traders"
    trade_taskmaster = mp.Process(
        target=taskmaster,
        kwargs={"pname": pname, "qa_pairs": qa_pairs},
    )


    def stop_trade_taskmaster():
        trade_taskmaster.terminate()
        trade_taskmaster.join()


    atexit.register(stop_trade_taskmaster)
    trade_taskmaster.start()

    # start the probing process
    pname = "probes"
    probe_taskmaster = mp.Process(
        target=taskmaster,
        kwargs={"pname": pname, "qa_pairs": qa_pairs},
    )


    def stop_probe_taskmaster():
        probe_taskmaster.terminate()
        probe_taskmaster.join()


    atexit.register(stop_probe_taskmaster)
    probe_taskmaster.start()

    ###

    from time import sleep
    while True:
        sleep(3600)
        private_eye(request, priority=3)
