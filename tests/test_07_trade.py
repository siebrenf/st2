import random

from st2.trade.functions import x2y_export, y2x_export


def test_export():
    for _ in range(10):
        base_price = random.randrange(20, 10_000)
        for _ in range(10):
            y1 = random.randrange(20, 10_000)
            x = y2x_export(y1, 0.35, base_price)
            y2 = x2y_export(x, 0.35, base_price)
            print(base_price, y1, y2)
            assert y1 == y2, (base_price, y1, y2)
