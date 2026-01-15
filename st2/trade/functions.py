import numpy as np


def x2y(x, a, base_price, port, action):
    if port == "EXPORT":
        y = x2y_export(x, a, base_price, action)
    elif port == "IMPORT":
        y = x2y_import(x, a, base_price, action)
    elif port == "EXCHANGE":
        y = x2y_exchange(x, a, base_price, action)
    else:
        raise ValueError
    return y


def y2x(y, a, base_price, port, action):
    if port == "EXPORT":
        x = y2x_export(y, a, base_price, action)
    elif port == "IMPORT":
        x = y2x_import(y, a, base_price, action)
    elif port == "EXCHANGE":
        x = y2x_exchange(y, a, base_price, action)
    else:
        raise ValueError
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
    if supply == "SCARCE":
        return -float("inf"), -4
    if supply == "LIMITED":
        return -4, -2
    if supply == "MODERATE":
        return -2, 2
    if supply == "HIGH":
        return 2, 4
    if supply == "ABUNDANT":
        return 4, float("inf")
    raise NotImplementedError


def supply2x_x2(s0, s1, units, tv, action):
    """return the possible ranges of x before and after a transaction"""
    dx = units / tv
    x_min0, x_max0 = supply2x(s0)
    x_min1, x_max1 = supply2x(s1)
    if s0 == s1:
        if action == "sell":
            x_max0 -= dx
            x_min1 += dx
        else:
            x_min0 += dx
            x_max1 -= dx
    else:
        s2i = {"ABUNDANT": 4, "HIGH": 3, "MODERATE": 2, "LIMITED": 1, "SCARCE": 0}
        if abs(s2i[s0] - s2i[s1]) > 1:
            raise NotImplementedError("Supply levels must be adjacent")

        if action == "sell":
            # the supply level increased between transactions
            # range = (x_min1, x_min1 + dx)
            x_min0 = x_max0 - dx
            x_max1 = x_min1 + dx
        else:
            # the supply level decreased between transactions:
            # range = (x_max1 - dx, x_max1)
            x_max0 = x_min0 + dx
            x_min1 = x_max1 - dx
    return x_min0, x_max0, x_min1, x_max1


def a_prior(y, supply, base_price, port, action):
    """
    Returns the highest value of the waypoint modifier (a) that can yield the
    given price (y) within the supply level, and the matching value of x.
    """
    x_min, x_max = supply2x(supply)
    # TODO: are these all possible values of a?
    for a in [0.6, 0.55, 0.5, 0.45, 0.4, 0.35, 0.3, 0.25, 0.2]:
        x = y2x(y, a, base_price, port, action)
        if x_max >= round(x, 4) >= x_min:
            return a
    # this function might break when meeting real world values
    raise ValueError(
        f"{y=} not found within {supply=} (based on {base_price=} and {action=})"
    )


def a_posterior(y0, s0, y1, s1, units, tv, port, action, base_price):
    """Find the value of a that best matches the difference in price (y)"""
    x_min0, x_max0, x_min1, x_max1 = supply2x_x2(s0, s1, units, tv, action)
    for a in [0.6, 0.55, 0.5, 0.45, 0.4, 0.35, 0.3, 0.25, 0.2]:
        x0 = y2x(y0, a, base_price, port, action)
        x1 = y2x(y1, a, base_price, port, action)
        if x_max0 >= round(x0, 4) >= x_min0 and x_max1 >= round(x1, 4) >= x_min1:
            return a
    # this function might break when meeting real world values
    raise ValueError(
        f"y={y1} not found within supply={s1} (based on {base_price=} and {action=})"
    )
