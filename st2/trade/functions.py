import numpy as np

from st2.logging import logger

DEBUG = True

# all known values for 'a'. Values seem to occur on a distribution.
A_VALUES = [0.6, 0.55, 0.5, 0.45, 0.4, 0.35, 0.3, 0.25, 0.2]


def x2y(x, a, base_price, port, action):
    if port == "EXPORT":
        y = x2y_export(x, a, base_price, action)
    elif port == "IMPORT":
        y = x2y_import(x, a, base_price, action)
    elif port == "EXCHANGE":
        y = x2y_exchange(x, a, base_price, action)
    else:
        raise ValueError(port)
    return y


def y2x(y, a, base_price, port, action):
    if port == "EXPORT":
        x = y2x_export(y, a, base_price, action)
    elif port == "IMPORT":
        x = y2x_import(y, a, base_price, action)
    elif port == "EXCHANGE":
        x = y2x_exchange(y, a, base_price, action)
    else:
        raise ValueError(port)
    return x


def x2y_export(x, a, base_price, action):
    if action == "sell":
        raise NotImplementedError
    x = x + 1
    y = base_price * (a * 2 ** (-0.3 * x) - a + 1)
    return y


def y2x_export(y, a, base_price, action):
    """
    y = base_price * (a * 2 ** (-0.3 * x) - a + 1)
    y / base_price = a * 2 ** (-0.3 * x) - a + 1
    y / base_price + a - 1 = a * 2 ** (-0.3 * x)
    (y / base_price + a - 1) / a = 2 ** (-0.3 * x)
    np.log2((y / base_price + a - 1) / a) = -0.3 * x
    (1 / -0.3) * np.log2((y / base_price + a - 1) / a) = x
    (-10 / 3) * np.log2((y / base_price + a - 1) / a) = x

    note: error if np.log2(<=0)
    (y / base_price + a - 1) / a > 0
    """
    if action == "sell":
        raise NotImplementedError
    value = (y / base_price + a - 1) / a
    if value > 0:
        x = (-10 / 3) * np.log2(value) - 1
    else:
        x = 10 - 1
    return x


def x2y_import(x, a, base_price, action):
    if action != "sell":
        raise NotImplementedError
    x = x - 1
    y = base_price * (-a * 2 ** (0.3 * x) + a + 1)
    return y


def y2x_import(y, a, base_price, action):
    """
    y = base_price * (-a * 2 ** (0.3 * x) + a + 1)
    y / base_price = -a * 2 ** (0.3 * x) + a + 1
    y / base_price - a - 1 = -a * 2 ** (0.3 * x)
    (y / base_price - a - 1) / -a = 2 ** (0.3 * x)
    np.log2((y / base_price - a - 1) / -a) = 0.3 * x
    (1 / 0.3) * np.log2((y / base_price - a - 1) / -a) = x
    (10 / 3) * np.log2((y / base_price - a - 1) / -a) = x

    note: error if np.log2(<=0)
    (y / base_price - a + 1) / -a > 0
    """
    if action != "sell":
        raise NotImplementedError
    value = (y / base_price - a - 1) / -a
    if value > 0:
        x = (10 / 3) * np.log2(value) + 1
    else:
        x = -10 + 1
    return x


def x2y_exchange(x, a, base_price, action):
    value = max(2, round(base_price / 100))
    if action == "sell":
        x = x + 1
        base_price = base_price - value
    else:
        x = x - 1
        base_price = base_price + value
    y = base_price * (-a / 1000 * x**3 + 1)
    return y


def y2x_exchange(y, a, base_price, action):
    """
    y = base_price * (-a / 1000 * x ** 3 + 1)
    y / base_price = -a / 1000 * x ** 3 + 1
    a / 1000 * x ** 3 = 1 - y / base_price
    x ** 3 = 1000 / a * (1 - y / base_price)
    x = (1000 / a * (1 - y / base_price)) ** (1/3)

    Must use numpy's cubic root to get the real-value answer
    x = np.cbrt(1000 / a * (1 - y / base_price))
    """
    value = max(2, round(base_price / 100))
    if action == "sell":
        base_price = base_price - value
    else:
        base_price = base_price + value
    x = np.cbrt(1000 / a * (1 - y / base_price))
    if action == "sell":
        x = x - 1
    else:
        x = x + 1
    return x


def x2supply(x):
    if x <= -4:
        return "SCARCE"
    if x <= -2:
        return "LIMITED"
    if x <= 2:
        return "MODERATE"
    if x <= 4:
        return "HIGH"
    return "ABUNDANT"


def supply2x(supply):
    return {
        "SCARCE": (-float("inf"), -4),
        "LIMITED": (-4, -2),
        "MODERATE": (-2, 2),
        "HIGH": (2, 4),
        "ABUNDANT": (4, float("inf")),
    }[supply]


def supply2x_avg(supply):
    return {
        "SCARCE": -5,
        "LIMITED": -3,
        "MODERATE": 0,
        "HIGH": 3,
        "ABUNDANT": 5,
    }[supply]


def a_prior(y, supply, base_price, port, action):
    """
    Returns the highest value of the waypoint modifier (a) that can yield the
    given price (y) within the supply level.
    """
    best = A_VALUES[0], 100.0
    x_min, x_max = supply2x(supply)
    x_max += 0.005  # compensate for floating point rounding errors
    x_min -= 0.005
    for a in A_VALUES:
        x = y2x(y, a, base_price, port, action)
        if not x_max > x > x_min:
            continue
        x_avg = supply2x_avg(supply)
        diff = 20.0 + abs(x_avg - x)  # 20 = pseudovalue
        if diff < best[1]:
            best = a, diff
    return best


def a_posterior1(y0, y1, s1, units, tv, port, action, base_price):
    """
    Returns the value of the waypoint modifier (a)
    that best matches the difference in price (y)
    """
    best = A_VALUES[0], 100.0
    dx = units / tv
    x_min1, x_max1 = supply2x(s1)
    x_max1 += 0.005  # compensate for floating point rounding errors
    x_min1 -= 0.005
    for a in A_VALUES:
        x0 = y2x(y0, a, base_price, port, action)
        x1 = y2x(y1, a, base_price, port, action)
        if not x_max1 > x1 > x_min1:
            continue
        diff = 10.0 + abs(abs(x1 - x0) - dx) / dx  # 10 = pseudovalue
        if diff < best[1]:
            best = a, diff
    return best


def a_posterior2(waypoint_symbol, tgs, tas, action, base_price):
    """
    Returns the value of the waypoint modifier (a)
    that best matches the differences in price (y)
    across any number of transactions.
    """
    symbol = tgs[0]["symbol"]
    port = tgs[0]["type"]

    # match the supply levels with the transaction prices
    ss = []
    ys = []
    dxs = []
    tvs = []
    for i, ta in enumerate(tas):
        tg = tgs[i]
        if tg[f"{action}Price"] != ta["pricePerUnit"]:
            if DEBUG:
                logger.debug(
                    f"Outside factors influenced the {symbol} transaction "
                    f"at {waypoint_symbol} (prices changed: "
                    f"tradeGood={tg[f"{action}Price"]:_} "
                    f"transaction={ta["pricePerUnit"]:_})"
                )
            return A_VALUES[0], 100.0
        ss.append(tg["supply"])  # supply level before the transaction
        ys.append(ta["pricePerUnit"])  # price at the transaction
        dxs.append(ta["units"] / tg["tradeVolume"])  # supply change of the transaction
        tvs.append(tg["tradeVolume"])  # tradeVolume before the transaction
    ys.append(tgs[-1][f"{action}Price"])  # price after all transactions
    ss.append(tgs[-1]["supply"])  # supply level after all transactions
    if DEBUG and len(set(tvs)) != 1:
        logger.debug(
            f"The tradeVolume for {symbol} increased at {waypoint_symbol} "
            f"from {min(tvs)} to {max(tvs)}!"
        )

    # find the value of a where the supply levels match the inferred value of x
    # and look for the lowest difference between the observed and inferred dx.
    best = A_VALUES[0], 100.0
    for a in A_VALUES:
        # infer values for x
        xs = []
        for i, y in enumerate(ys):
            x = y2x(y, a, base_price, port, action)
            if ss[i] != x2supply(x):
                break  # inferred x not contained in supply level
            xs.append(x)
        if len(xs) != len(ys):
            continue  # next value of a

        # lowest difference between the observed and inferred dx
        diff = 0
        for i, dx_obs in enumerate(dxs):
            dx_inf = abs(xs[i + 1] - xs[i])
            diff += abs(dx_obs - dx_inf) / dx_obs
        if diff < best[1]:
            best = a, float(diff)
    if best[1] == float("inf"):
        logger.warning(
            f"The {base_price=:_} for {symbol}, the values for `a`, or the {port} market functions, are incorrect!"
        )
    return best
