from asyncio import sleep

from st2.investigators import detective, get_last_detective_run, private_eye
from st2.request import RequestMp
from st2.stargazers import ambassador, astronomer, cartographer, merchant


async def ai_advisor_controller(qa_pairs, priority=3, interval=3600, verbose=False):
    """Perform all low-priority background tasks"""
    request = RequestMp(qa_pairs, priority)

    merchant(request, priority)
    ambassador(request, priority)
    await astronomer(request, priority, verbose)
    await cartographer(request, priority, "start systems", verbose)
    await cartographer(request, priority, "gate systems", verbose)
    # too many API requests!
    # await spymaster(request, priority, verbose)

    # TODO: also set a timer for private_eye
    # number of intervals since the last detective run
    n = round(get_last_detective_run() / interval)
    while True:
        if n >= 6:
            await detective(request, priority, verbose)
            n = 0
        else:
            await private_eye(request, priority, verbose)
            n += 1
        await sleep(interval)


# too many API requests!
# async def ai_spymaster_controller(agent_symbol, qa_pairs, priority=2, verbose=False):
#     """
#     Dispatch ships to all markets in the start system to automatically gather intelligence.
#
#     This controller self-destructs after completing its task.
#     """
#     request = RequestMp(qa_pairs, priority)
#     await spymasters_apprentice(agent_symbol, request, priority, verbose)
#     return "self destruct"
