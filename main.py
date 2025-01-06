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

    game_server()
    db_server()
    manager, api_handler, qa_pairs = api_server()

    request = RequestMp(qa_pairs)
    status = request.get(endpoint="", priority=0)
    print(status['status'])

    # update databases
    from st2.db import db_update_factions
    from st2.stargazers import astronomer, cartographer

    db_update_factions(request)
    astronomer(request)
    cartographer(request)

    ###
