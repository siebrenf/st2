import numpy as np

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


# def supply2x_x2(s0, s1, units, tv, action):
#     """return the possible ranges of x before and after a transaction"""
#     dx = units / tv
#     x_min0, x_max0 = supply2x(s0)
#     x_min1, x_max1 = supply2x(s1)
#     if s0 == s1:
#         if action == "sell":
#             x_max0 -= dx
#             x_min1 += dx
#         else:
#             x_min0 += dx
#             x_max1 -= dx
#     else:
#         s2i = {"ABUNDANT": 4, "HIGH": 3, "MODERATE": 2, "LIMITED": 1, "SCARCE": 0}
#         if abs(s2i[s0] - s2i[s1]) > 1:
#             raise NotImplementedError("Supply levels must be adjacent")
#
#         if action == "sell":
#             # the supply level increased between transactions
#             # range = (x_min1, x_min1 + dx)
#             x_min0 = x_max0 - dx
#             x_max1 = x_min1 + dx
#         else:
#             # the supply level decreased between transactions:
#             # range = (x_max1 - dx, x_max1)
#             x_max0 = x_min0 + dx
#             x_min1 = x_max1 - dx
#     return x_min0, x_max0, x_min1, x_max1
#
#
# def a_prior(y, supply, base_price, port, action):
#     """
#     Returns the highest value of the waypoint modifier (a) that can yield the
#     given price (y) within the supply level, and the matching value of x.
#     """
#     best = None, float("inf")
#     x_min, x_max = supply2x(supply)
#     for a in A_VALUES:
#         x = y2x(y, a, base_price, port, action)
#         if x_max >= round(x, 4) >= x_min:
#             return a, 0.1
#
#         # approximation in case the exact calculations are off
#         x_avg = supply2x_avg(supply)
#         diff = abs(x_avg - x)
#         if diff < best[1]:
#             best = a, diff
#     if DEBUG:
#         logger.debug(
#             f"Returning approximation. {y=}, {base_price=}, "
#             f"{supply=}, {port=}, {action=}, a={best[0]}, diff={best[1]}"
#         )
#     return best[0], 0.01  # worst score
#
#
# def a_posterior(y0, s0, y1, s1, units, tv, port, action, base_price):
#     """Find the value of a that best matches the difference in price (y)"""
#     best = None, float("inf")
#     dx = units / tv
#     x_min0, x_max0, x_min1, x_max1 = supply2x_x2(s0, s1, units, tv, action)
#     for a in A_VALUES:
#         x0 = y2x(y0, a, base_price, port, action)
#         x1 = y2x(y1, a, base_price, port, action)
#         diff = abs(abs(x1 - x0) - dx)
#         if (
#             (x_max0 >= round(x0, 4) >= x_min0)
#             and (x_max1 >= round(x1, 4) >= x_min1)
#             and (diff < 1 / tv)
#         ):
#             return a, 1  # best score
#
#         # approximation in case the exact calculations are off
#         if diff < best[1]:
#             best = a, diff
#     if DEBUG:
#         logger.debug(
#             f"Returning approximation. {y0=}, {y1=}, {base_price=}, {s0=}, {s1=}, "
#             f"{units=}, {tv=}, {port=}, {action=}, a={best[0]}, diff={best[1]}"
#         )
#     # always better than a_prior, always worse than exact calculations
#     score = min(0.99, max(0.11, 1 - best[1]))
#     return best[0], score


def a_prior(y, supply, base_price, port, action):
    """
    Returns the highest value of the waypoint modifier (a) that can yield the
    given price (y) within the supply level.
    """
    best = A_VALUES[0], float("inf")
    x_min, x_max = supply2x(supply)
    x_max = x_max + 1 / 120  # compensate for floating point rounding errors
    x_min = x_min - 1 / 120
    for a in A_VALUES:
        x = y2x(y, a, base_price, port, action)
        if not x_max > x > x_min:
            continue
        x_avg = supply2x_avg(supply)
        diff = 10.0 + abs(x_avg - x)  # pseudovalue
        if diff < best[1]:
            best = a, diff
    return best


def a_posterior(y0, y1, s1, units, tv, port, action, base_price):
    """
    Returns the value of the waypoint modifier (a)
    that best matches the difference in price (y)
    """
    best = A_VALUES[0], float("inf")
    dx = units / tv
    x_min1, x_max1 = supply2x(s1)
    x_max1 = x_max1 + 1 / 120  # compensate for floating point rounding errors
    x_min1 = x_min1 - 1 / 120
    for a in A_VALUES:
        x0 = y2x(y0, a, base_price, port, action)
        x1 = y2x(y1, a, base_price, port, action)
        if not x_max1 > x1 > x_min1:
            continue
        diff = abs(abs(x1 - x0) - dx)
        if diff < best[1]:
            best = a, diff
    return best
