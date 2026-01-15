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


def y2x(y, a, base_price, port, action, x_guess=0):  # TODO
    if port == "EXPORT":
        if action == "sell":
            y *= 2
        x = y2x_export(y, a, base_price)
        if action == "sell":
            x += 2
        else:
            x += 1

    elif port == "IMPORT":
        if action != "sell":
            y /= 2
        x = y2x_import(y, a, base_price, x_guess)
        if action == "sell":
            x -= 1
        else:
            x -= 2

    elif port == "EXCHANGE":
        if action == "sell":
            base_price -= max(2, 0.01 * base_price)
        else:
            base_price += max(2, 0.01 * base_price)
        x = y2x_exchange(y, a, base_price, x_guess)
        if action == "sell":
            x += 1
        else:
            x -= 1

    else:
        raise ValueError

    return x


def x2y_export(x, a, base_price, action):
    if action == "sell":
        raise NotImplementedError
    x = x + 1
    y = base_price * (a * 2 ** (-0.3 * x) - a + 1)
    return y


def y2x_export(y, a, base_price):
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


def y2x_import(y, a, base_price):
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
    y / base_price - 1 = -a / 1000 * x ** 3

    # TODO: breaks
    (1 / -a / 1000) * (y / base_price - 1) = x ** 3
    ((1 / -a / 1000) * (y / base_price - 1)) ** (1/3) = x

    # TODO: this one breaks at x<=0
    (1000 / -a) * (y / base_price - 1) = x ** 3
    ((1000 / -a) * (y / base_price - 1)) ** (1/3) = x

    # TODO: this one breaks at x<-2
    y = base_price * (-a / 1000 * x ** 3 + 1)
    y / base_price = -a / 1000 * x ** 3 + 1
    a / 1000 * x ** 3 = 1 - y / base_price
    x ** 3 = 1000 / a * (1 - y / base_price)
    x = (1000 / a * (1 - y / base_price)) ** (1/3)
    """
    value = max(2, round(base_price / 100))
    if action == "sell":
        y = y + value
    else:
        y = y - value
    # x = ((1 / -a / 1000) * (y / base_price - 1)) ** (1/3)
    # x = ((1000 / -a) * (y / base_price - 1)) ** (1/3)
    x = (1000 / a * (1 - y / base_price)) ** (1 / 3)
    if action == "sell":
        x = x - 1
    else:
        x = x + 1
    return x


# def x2y_exchange(x, a, base_price):
#     """imperfect approximation of the EXCHANGE price"""
#     x = x - 2
#
#     a = a / 100
#     b = a / 2
#     c = a / 12.5
#     y = base_price * (c * x**3 + b * x**2 + a * x + 1)
#     return max(round(y), 1)
#
#
# def y2x_exchange(y, a, base_price, x_guess=0):
#     a = a / 100
#     b = a / 2
#     c = a / 12.5
#
#     def polynomial(x):
#         """x2y_exchange() - y"""
#         return base_price * (c * x**3 + b * x**2 + a * x + 1) - y
#
#     def fprime(x):
#         return base_price * (3 * c * x**2 + 2 * b * x + a)
#
#     def fprime2(x):
#         return base_price * (6 * c * x + 2 * b)
#
#     x = newton(polynomial, x0=x_guess, fprime=fprime, fprime2=fprime2)
#     x = x + 2
#     return x


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
    x_min, x_max = supply2x_minmax2(s0, s1, units, tv, action="purchase")
    x_guess = _x_guess(x_min, x_max)
    for a in [0.55, 0.5, 0.45, 0.4, 0.35, 0.3, 0.25, 0.2]:
        x1 = y2x(y1, a, base_price, port, action, x_guess)
        x0 = x1 - dx
        y0_inf = x2y(x0, a, base_price, port, action)
        diff = abs(y0 - y0_inf)
        if diff < best[2]:
            best = a, x1, diff

    a, x1 = best[:2]
    if x:
        return a, x1
    return a


def _x_guess(x_min, x_max):
    if math.isfinite(x_min):
        if math.isfinite(x_max):
            x_guess = (x_min + x_max) / 2
        else:
            x_guess = x_min - 1
    else:
        x_guess = x_max + 1
    return x_guess
