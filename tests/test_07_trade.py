from st2.trade.functions import (
    x2supply,
    x2y_exchange,
    x2y_export,
    x2y_import,
    y2x_exchange,
    y2x_export,
    y2x_import,
)


def test_export():
    a = 0.55
    base_price = 1000
    for x_obs in [-6, -5, -4, -3, -2, -1, 0, 1, 2, 3, 4, 5, 6]:
        y = x2y_export(x_obs, a, base_price, "purchase")
        x_inf = y2x_export(y, a, base_price, "purchase")
        if x_obs == -1:
            assert y == base_price, (y, base_price)
        # print(f"{x_obs=}, {x_inf=}, {y=} supply={x2supply(x_obs)}")
        assert x_obs - x_inf < 0.01, f"{x_obs=}, {x_inf=}, {y=}"


def test_import():
    a = 0.55
    base_price = 1000
    for x_obs in [-6, -5, -4, -3, -2, -1, 0, 1, 2, 3, 4, 5, 6]:
        y = x2y_import(x_obs, a, base_price, "sell")
        x_inf = y2x_import(y, a, base_price, "sell")
        if x_obs == 1:
            assert y == base_price, (y, base_price)
        # print( f"{x_obs=}, {x_inf=}, {y=} supply={x2supply(x_obs)}")
        assert x_obs - x_inf < 0.01, f"{x_obs=}, {x_inf=}, {y=}"


def test_exchange():
    a = 0.55
    base_price = 1000
    for action in ["purchase", "sell"]:
        for x_obs in [-6, -5, -4, -3, -2, -1, 0, 1, 2, 3, 4, 5, 6]:
            y = x2y_exchange(x_obs, a, base_price, action)
            x_inf = y2x_exchange(y, a, base_price, action)
            if action == "purchase" and x_obs == 1:
                assert y == base_price + max(2, round(base_price / 100))
            if action == "sell" and x_obs == -1:
                assert y == base_price - max(2, round(base_price / 100))
            # print(f"{x_obs=}, {x_inf=}, {y=} supply={x2supply(x_obs)} {action=}")
            assert x_obs - x_inf < 0.01, f"{x_obs=}, {x_inf=}, {y=} {action=}"
