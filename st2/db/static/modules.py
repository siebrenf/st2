MODULES = {
    "MODULE_CARGO_HOLD_I": {
        "symbol": "MODULE_CARGO_HOLD_I",
        "name": "Cargo Hold",
        "description": "A module that increases a ship's cargo capacity.",
        "capacity": 15,
        "requirements": {"crew": 0, "power": 1, "slots": 1},
    },
    "MODULE_CARGO_HOLD_II": {
        "symbol": "MODULE_CARGO_HOLD_II",
        "name": "Expanded Cargo Hold",
        "description": "An expanded cargo hold module that provides more efficient storage space for a ship's cargo.",
        "capacity": 40,
        "requirements": {"crew": 2, "power": 2, "slots": 2},
    },
    "MODULE_CARGO_HOLD_III": {
        "symbol": "MODULE_CARGO_HOLD_III",
        "name": "Advanced Cargo Hold",
        "description": "A large cargo hold module with advanced robotics that provides more efficient storage space for a ship's cargo.",
        "capacity": 75,
        "requirements": {"crew": 6, "power": 4, "slots": 3},
    },
    "MODULE_CREW_QUARTERS_I": {
        "symbol": "MODULE_CREW_QUARTERS_I",
        "name": "Crew Quarters",
        "description": "A module that provides living space and amenities for the crew.",
        "capacity": 40,
        "requirements": {"crew": 2, "power": 1, "slots": 1},
    },
    "MODULE_ENVOY_QUARTERS_I": None,
    "MODULE_FUEL_REFINERY_I": None,
    "MODULE_GAS_PROCESSOR_I": {
        "symbol": "MODULE_GAS_PROCESSOR_I",
        "name": "Gas Processor",
        "description": "Filters and processes extracted gases into their component parts, filters out impurities, and containerizes them into raw storage units.",
        "requirements": {"crew": 0, "power": 1, "slots": 2},
    },
    "MODULE_JUMP_DRIVE_I": {
        "symbol": "MODULE_JUMP_DRIVE_I",
        "name": "Jump Drive I",
        "description": "A basic antimatter jump drive that allows for instantaneous short-range interdimensional travel.",
        "range": 500,
        "requirements": {"power": 4, "crew": 10, "slots": 1},
    },
    "MODULE_JUMP_DRIVE_II": None,
    "MODULE_JUMP_DRIVE_III": None,
    "MODULE_MICRO_REFINERY_I": None,
    "MODULE_MINERAL_PROCESSOR_I": {
        "symbol": "MODULE_MINERAL_PROCESSOR_I",
        "name": "Mineral Processor",
        "description": "Crushes and processes extracted minerals and ores into their component parts, filters out impurities, and containerizes them into raw storage units.",
        "requirements": {"crew": 0, "power": 1, "slots": 2},
    },
    "MODULE_ORE_REFINERY_I": {
        "symbol": "MODULE_ORE_REFINERY_I",
        "name": "Ore Refinery",
        "description": "A specialized module that can refine raw ores into usable metals and other materials.",
        "production": [
            "IRON",
            "COPPER",
            "SILVER",
            "GOLD",
            "ALUMINUM",
            "PLATINUM",
            "URANITE",
            "MERITIUM",
        ],
        "requirements": {"crew": 15, "power": 9, "slots": 3},
    },
    "MODULE_PASSENGER_CABIN_I": None,
    "MODULE_SCIENCE_LAB_I": None,
    "MODULE_SHIELD_GENERATOR_I": None,
    "MODULE_SHIELD_GENERATOR_II": None,
    "MODULE_WARP_DRIVE_I": {
        "symbol": "MODULE_WARP_DRIVE_I",
        "name": "Warp Drive I",
        "description": "A basic warp drive that allows for short-range interstellar travel.",
        "range": 2000,
        "requirements": {"crew": 2, "power": 3, "slots": 1},
    },
    "MODULE_WARP_DRIVE_II": {
        "symbol": "MODULE_WARP_DRIVE_II",
        "name": "Warp Drive II",
        "description": "An advanced warp drive that allows for longer-range interstellar travel with improved reliability.",
        "range": 6000,
        "requirements": {"power": 5, "crew": 8, "slots": 2},
    },
    "MODULE_WARP_DRIVE_III": None,
}
