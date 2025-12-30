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
    from st2.stargazers import ambassador, astronomer, cartographer

    ambassador(request, priority=0)
    astronomer(request, priority=0)
    cartographer(request, priority=0, chart="start systems")
    cartographer(request, priority=3, chart="gate systems")

    # (Re)start the start system probing
    from st2.spies import spymaster, detective

    spymaster(request, priority=3)

    # start the probing process
    import multiprocessing as mp
    from st2.ai import taskmaster

    pname = "probes"
    probe_taskmaster = mp.Process(
        target=taskmaster,
        kwargs={"pname": pname, "qa_pairs": qa_pairs},
    )
    probe_taskmaster.start()

    ###

    from time import sleep
    while True:
        detective(request, priority=3)
        sleep(3600)
