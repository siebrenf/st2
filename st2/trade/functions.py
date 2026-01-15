import math

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
    return max(round(y), 1)


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
    if action == "sell":
        x = x + 1
    else:
        x = x - 1
    y = base_price * (-a / 1000 * x**3 + 1)
    value = max(2, round(base_price / 100))
    if action == "sell":
        y = y - value
    else:
        y = y + value
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
        y = y + value
    else:
        y = y - value
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


def supply2x_minmax(supply, tv=180):
    """returns the range of x based on the supply level of one transaction."""
    if supply == "ABUNDANT":
        x_min = -float("inf")
        x_max = -4 - 1 / tv
    elif supply == "HIGH":
        x_min = -4
        x_max = -2 - 1 / tv
    elif supply == "MODERATE":
        x_min = -2
        x_max = 2 - 1 / tv
    elif supply == "LIMITED":
        x_min = 2
        x_max = 4 - 1 / tv
    elif supply == "SCARCE":
        x_min = 4
        x_max = float("inf")
    else:
        raise NotImplementedError
    return x_min, x_max


def supply2x_minmax2(s0, s1, units, tv, action):
    """return the range of x based on the supply levels of two transaction
    with a known number of units between."""
    dx = units / tv
    if action == "sell":
        if s0 == s1:
            x_min, x_max = supply2x_minmax(s0, tv)
            x_max -= dx
        else:
            x_min0, x_max0 = supply2x_minmax(s0, tv)
            x_min1, x_max1 = supply2x_minmax(s1, tv)
            x_min = x_min0 - dx
            x_max = x_max1
    else:
        if s0 == s1:
            x_min, x_max = supply2x_minmax(s0, tv)
            x_min += dx
        else:
            x_min0, x_max0 = supply2x_minmax(s0, tv)
            x_min1, x_max1 = supply2x_minmax(s1, tv)
            x_min = x_min1
            x_max = x_max0 + dx
    return x_min, x_max


def a_prior(y, supply, tv, port, base_price, action):
    """returns the highest value of a that can yield the given price (y)
    within the supply level, and the matching value of x."""
    best = 0.4, float("inf")
    y_min, y_max = -float("inf"), float("inf")
    x_min, x_max = supply2x_minmax(supply, tv)
    for a in [0.55, 0.5, 0.45, 0.4, 0.35, 0.3, 0.25, 0.2]:
        if x_min != -float("inf"):
            y_min = x2y(x_min, a, base_price, port, action)
        if x_max != float("inf"):
            y_max = x2y(x_max, a, base_price, port, action)
        diff = min(abs(y_min - y), abs(y_max - y))
        if diff < best[1]:
            best = a, diff

    return best[0]


def a_posterior(y0, s0, y1, s1, tv, port, units, action, base_price, x=False):
    """Find the value of a that best matches the difference in price (y)"""
    best = "a", "x", float("inf")
    dx = units / tv
    if action == "sell":
        dx *= -1
    for a in [0.55, 0.5, 0.45, 0.4, 0.35, 0.3, 0.25, 0.2]:
        x1 = y2x(y1, a, base_price, port, action)
        x0 = x1 - dx
        y0_inf = x2y(x0, a, base_price, port, action)
        diff = abs(y0 - y0_inf)
        if diff < best[2]:
            best = a, x1, diff

    a, x1 = best[:2]
    if x:
        return a, x1
    return a
