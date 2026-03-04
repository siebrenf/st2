from fractions import Fraction


def excav_chances(traits=None):
    """Return a dictionary with drop/survey chances for each good"""
    # list all goods that can be extracted/siphoned
    if traits in [None, []]:
        goods = sorted(SIPHON)  # siphon
    else:
        goods = []  # extract/survey
        if isinstance(traits, str) or isinstance(traits, dict):
            traits = [traits]
        for trait in traits:
            if isinstance(trait, dict):
                trait = trait["symbol"]
            if trait not in TRAIT2EXTRACT:
                continue
            goods.extend(TRAIT2EXTRACT[trait])
        goods = sorted(set(goods))

    # get the common denominator for all ratios
    seen = []
    fractions = []
    for frac in _EXCAV_RATIO2GOOD:
        d = frac.denominator
        if d in seen:
            continue
        fractions.append(Fraction(1, d))
    shared_denominator = sum(fractions).denominator

    # express all ratios with the common denominator
    #   and store all numerators
    new_denominator = 0
    new_numerators = {}
    for good in goods:
        frac = _GOOD2EXCAV_RATIO[good]
        multiplier = shared_denominator / frac.denominator
        shared_numerator = frac.numerator * multiplier
        new_denominator += shared_numerator
        new_numerators[good] = shared_numerator

    # drop chances are the numerators over the sum of the numerators
    drop_chances = {}
    for good, new_numerator in new_numerators.items():
        drop_chances[good] = Fraction(int(new_numerator), int(new_denominator))
    return drop_chances


def survey2extract_chance(survey=None, deposits=None):
    """Return a dictionary with survey-extract drop chances for each good"""
    if survey:
        if isinstance(survey, list):
            survey = survey[0]
        deposits = survey["deposits"]
    if isinstance(deposits, str):
        deposits = [deposits]
    elif isinstance(deposits[0], dict):
        deposits = [d["symbol"] for d in deposits]
    goods = sorted(deposits)
    n = len(goods)
    chances = {g: Fraction(goods.count(g), n) for g in goods}
    return chances


# manually curated list of extractable goods
EXTRACT = [
    "ALUMINUM_ORE",
    "AMMONIA_ICE",
    "COPPER_ORE",
    "DIAMONDS",
    "GOLD_ORE",
    "ICE_WATER",
    "IRON_ORE",
    "MERITIUM_ORE",
    "PLATINUM_ORE",
    "PRECIOUS_STONES",
    "QUARTZ_SAND",
    "SILICON_CRYSTALS",
    "SILVER_ORE",
    "URANITE_ORE",
]

# manually curated list of siphonable goods
SIPHON = [
    "HYDROCARBON",
    "LIQUID_HYDROGEN",
    "LIQUID_NITROGEN",
]

# waypoint type required for excavation
EXCAV2TYPE = {
    "extract": ["ASTEROID", "ASTEROID_FIELD", "ENGINEERED_ASTEROID"],
    "siphon": ["GAS_GIANT"],
}

# waypoint traits relating to extraction tradeGoods
TRAIT2EXTRACT = {
    "COMMON_METAL_DEPOSITS": [
        "ALUMINUM_ORE",
        "COPPER_ORE",
        "ICE_WATER",
        "IRON_ORE",
        "QUARTZ_SAND",
        "SILICON_CRYSTALS",
    ],
    "MINERAL_DEPOSITS": [
        "AMMONIA_ICE",
        "DIAMONDS",
        "ICE_WATER",
        "IRON_ORE",
        "PRECIOUS_STONES",
        "QUARTZ_SAND",
        "SILICON_CRYSTALS",
    ],
    "PRECIOUS_METAL_DEPOSITS": [
        "ALUMINUM_ORE",
        "COPPER_ORE",
        "GOLD_ORE",
        "ICE_WATER",
        "PLATINUM_ORE",
        "QUARTZ_SAND",
        "SILICON_CRYSTALS",
        "SILVER_ORE",
    ],
    "RARE_METAL_DEPOSITS": [
        "ALUMINUM_ORE",
        "COPPER_ORE",
        "GOLD_ORE",
        "ICE_WATER",
        "MERITIUM_ORE",
        "PLATINUM_ORE",
        "QUARTZ_SAND",
        "SILICON_CRYSTALS",
        "URANITE_ORE",
    ],
}
EXTRACT2TRAIT = {}
for t, es in TRAIT2EXTRACT.items():
    for e in es:
        EXTRACT2TRAIT.setdefault(e, []).append(t)
del e, es, t


# These traits are found with deposit traits (in any combination)
# The Changelog suggests traits impact extract yield (can apply to goods, units or both)
#   - units are *not* impacted by specific traits
#   - goods are *not* be impacted by specific traits
#   - good/unit combinations are *not* impacted by specific traits
#   - individual waypoints *do* seem to have unique distributions, regardless of traits
# Last update: SpacetradersAPI v2.2 (07-2024)
TRAIT2MODIFIER = [
    "DEBRIS_CLUSTER",
    "DEEP_CRATERS",
    "EXPLOSIVE_GASES",
    "HOLLOWED_INTERIOR",
    "MICRO_GRAVITY_ANOMALIES",
    "RADIOACTIVE",
    "SHALLOW_CRATERS",
    "UNSTABLE_COMPOSITION",
]

# excavation unit yield, by action & mount
EXCAV_UNITS = {
    # Yield is normally distributed, with minima and maxima applied afterward.
    # Surveys overrule STRIPPED trait
    # Last update: SpacetradersAPI v2.2 (07-2024)
    "extract": {
        "MOUNT_MINING_LASER_I": {"min": 1, "max": 7, "mean": 3.0, "std": 1.0},
        "MOUNT_MINING_LASER_II": {"min": 1, "max": 10, "mean": 5.0, "std": 1.0},
        # "MOUNT_MINING_LASER_III": {},
    },
    "siphon": {
        "MOUNT_GAS_SIPHON_I": {"min": 1, "max": 15, "mean": 9, "std": 4},
        # "MOUNT_GAS_SIPHON_II": {},
        # "MOUNT_GAS_SIPHON_III": {},
    },
    "stripped": {
        "MOUNT_MINING_LASER_I": {"min": 1, "max": 3, "mean": 1.7, "std": 0.6},
        # "MOUNT_MINING_LASER_II": {},
        # "MOUNT_MINING_LASER_III": {},
    },
    "survey": {
        "MOUNT_MINING_LASER_I": {"min": 0, "max": 7, "mean": 3.0, "std": 1.0},
        # "MOUNT_MINING_LASER_II": {},
        # "MOUNT_MINING_LASER_III": {},
    },
}

# drop chance of each extract good, as a ratio to the drop chance of ICE_WATER
#   for example: IRON_ORE drop chance = ICE_WATER drop chance/2
_EXCAV_RATIO2GOOD = {
    Fraction(1, 1): [
        "AMMONIA_ICE",
        "HYDROCARBON",  # siphon
        "ICE_WATER",
        "QUARTZ_SAND",
        "SILICON_CRYSTALS",
    ],
    Fraction(1, 2): [
        "ALUMINUM_ORE",
        "COPPER_ORE",
        "IRON_ORE",
        "LIQUID_HYDROGEN",  # siphon
        "LIQUID_NITROGEN",  # siphon
        "PRECIOUS_STONES",
        "SILVER_ORE",
    ],
    Fraction(3, 20): [
        "GOLD_ORE",
        "PLATINUM_ORE",
        "URANITE_ORE",
    ],
    Fraction(1, 30): ["MERITIUM_ORE"],
    Fraction(1, 125): ["DIAMONDS"],
}
_GOOD2EXCAV_RATIO = {g: r for r, gs in _EXCAV_RATIO2GOOD.items() for g in gs}
