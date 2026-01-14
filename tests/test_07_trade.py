from st2.trade.functions import x2supply, x2y_export, y2x_export


def test_export():
    a = 0.55
    base_price = 1000
    for x_obs in [-6, -5, -4, -3, -2, -1, 0, 1, 2, 3, 4, 5, 6]:
        y = x2y_export(x_obs, a, base_price)
        x_inf = y2x_export(y, a, base_price)

        if x_obs == 1:
            assert y == base_price, (y, base_price)
        # print(x_obs, x_inf, y, x2supply(x_inf))
    assert round(x_obs) == round(x_inf), (x_obs, x_inf, y)
