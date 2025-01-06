"""
run from the command line with:
    pytest --disable-pytest-warnings -vvv
"""

import subprocess as sp
from os.path import dirname, join


def test_lint():
    base = dirname(dirname(__file__))
    sp.check_output(
        f'black {join(base, "st2")} {join(base, "tests")} ',  # {join(base, "tools")} {join(base, "scripts")}
        shell=True,
    )
    sp.check_output(
        "isort --overwrite-in-place --profile black --conda-env requirements.yaml "
        + f'{join(base, "st2")} {join(base, "tests")} ',  # {join(base, "tools")} {join(base, "scripts")}
        shell=True,
    )


def test_imports():
    sp.check_output(
        # "pydeps st2 --max-bacon 2 --cluster --rmprefix st2. --no-show -T png -o dependency_graph.png",
        "pydeps st2 --max-bacon 1 --rmprefix st2. --no-show -T png -o dependency_graph.png",
        shell=True,
    )
