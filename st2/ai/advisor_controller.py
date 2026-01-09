from asyncio import sleep

from st2.request import RequestMp
from st2.spies import detective, private_eye, spymaster
from st2.stargazers import ambassador, astronomer, cartographer, merchant


async def ai_advisor_controller(qa_pairs, priority=3, interval=3600, verbose=False):
    """Perform all low-priority background tasks"""
    request = RequestMp(qa_pairs, priority)

    merchant(request, priority)
    ambassador(request, priority)
    astronomer(request, priority, verbose)
    cartographer(request, priority, "start systems", verbose)
    cartographer(request, priority, "gate systems", verbose)
    detective(request, priority, verbose)
    spymaster(request, priority, verbose)

    n = 0
    while True:
        await sleep(interval)
        if n == 6:
            detective(request, priority, verbose)
            n = 0
        else:
            private_eye(request, priority, verbose)
            n += 1
