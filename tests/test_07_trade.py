from st2.trade.functions import *


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


def test_supply():
    for x in range(-6, 7):
        supply = x2supply(x)
        x_min, x_max = supply2x(supply)
        assert x_min <= x <= x_max


def test_supply2x_x2():
    action = "sell"
    s0 = "SCARCE"
    s1 = "LIMITED"
    x_min1, x_max1 = supply2x(s0)
    assert x_min1 == -float("inf")
    assert x_max1 == -4
    x_min2, x_max2 = supply2x(s1)
    assert x_min2 == -4
    assert x_max2 == -2
    x_min1, x_max1 = supply2x_x2(s0, s1, units=12, tv=6, action=action)[2:]
    assert x_min1 == -4
    assert x_max1 == -2  # -4 + 2
    assert x_max1 - x_min1 == 12 / 6  # units/tv = 2 tvs
    x_min1, x_max1 = supply2x_x2(s0, s1, units=6, tv=6, action=action)[2:]
    assert x_min1 == -4
    assert x_max1 == -3  # -4 + 1

    action = "purchase"
    s0 = "ABUNDANT"
    s1 = "HIGH"
    x_min1, x_max1 = supply2x(s0)
    assert x_min1 == 4
    assert x_max1 == float("inf")
    x_min2, x_max2 = supply2x(s1)
    assert x_min2 == 2
    assert x_max2 == 4
    x_min1, x_max1 = supply2x_x2(s0, s1, units=12, tv=6, action=action)[2:]
    assert x_min1 == 2  # 4 - 2
    assert x_max1 == 4
    x_min1, x_max1 = supply2x_x2(s0, s1, units=6, tv=6, action=action)[2:]
    assert x_min1 == 3  # 4 - 1
    assert x_max1 == 4

    s0 = "MODERATE"
    s1 = "MODERATE"
    x_min1, x_max1 = supply2x(s0)
    assert x_min1 == -2
    assert x_max1 == 2
    x_min1, x_max1 = supply2x_x2(s0, s1, units=12, tv=6, action=action)[2:]
    assert x_min1 == -2
    assert x_max1 == 0
    action = "sell"
    x_min1, x_max1 = supply2x_x2(s0, s1, units=12, tv=6, action=action)[2:]
    assert x_min1 == 0
    assert x_max1 == 2


def test_a_prior():
    base_price = 1000
    for port in ["IMPORT", "EXPORT", "EXCHANGE"]:
        for action in ["purchase", "sell"]:
            if port == "EXPORT" and action == "sell":
                continue
            if port == "IMPORT" and action == "purchase":
                continue
            for supply in ["ABUNDANT", "HIGH", "MODERATE", "LIMITED", "SCARCE"]:
                for a_obs in [0.2, 0.3, 0.4, 0.5, 0.6]:
                    x_min, x_max = supply2x(supply)
                    y_vals = sorted(
                        [
                            x2y(x_min, a_obs, base_price, port, action),
                            x2y(x_max, a_obs, base_price, port, action),
                        ]
                    )
                    for i, y in enumerate(y_vals):
                        a_inf = a_prior(y, supply, base_price, port, action)
                        # print(f"{port=} {supply=} {action=} {x_min=} {x_max=} {a_obs=} {a_inf=} {y=} {y_vals=}")
                        assert a_inf >= a_obs, (a_inf, a_obs)


def test_a_posterior():
    base_price = 1000
    units = 2
    tv = 6
    x0 = 2 - 1 / tv
    s0 = "MODERATE"
    for port in ["IMPORT", "EXPORT"]:  # , "EXCHANGE"
        for action in ["purchase", "sell"]:
            if port == "EXPORT" and action == "sell":
                continue
            if port == "IMPORT" and action == "purchase":
                continue
            if action == "sell":
                dx = units / tv
            else:
                dx = -units / tv
            for a_obs in [0.2, 0.3, 0.4, 0.5, 0.6]:
                y0 = x2y(x0, a_obs, base_price, port, action)
                x1 = x0 + dx
                s1 = x2supply(x1)
                y1 = x2y(x1, a_obs, base_price, port, action)
                # print("start", s0, s1, port, action)
                a_inf_prior = a_prior(y1, s1, base_price, port, action)
                a_inf_posterior = a_posterior(
                    y0, s0, y1, s1, units, tv, port, action, base_price
                )
                # print("end", a_obs, a_inf_prior, a_inf_post)
                assert a_obs <= a_inf_posterior <= a_inf_prior, (
                    a_obs,
                    a_inf_prior,
                    a_inf_posterior,
                )
