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
    from st2.startup import game_server, db_server, api_server
    from st2.request import RequestMp
    from st2.agent import api_agent

    game_server()
    db_server()
    manager, api_handler, qa_pairs = api_server()

    request = RequestMp(qa_pairs, priority=0, token=None)
    status = request.get(endpoint="")
    print(status['status'])

    # update databases
    from st2.db import db_update_factions
    from st2.stargazers import astronomer, cartographer

    token = api_agent(request, priority=0)[1]
    db_update_factions(request, priority=0, token=token)
    astronomer(request, priority=0, token=token)
    cartographer(request, priority=0, token=token, chart="start systems")

    # # (Re)start the start system probing
    # from st2.spies import spymaster
    #
    # spymaster(request, priority=3)

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
        sleep(1)
