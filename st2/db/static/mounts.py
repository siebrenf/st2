MOUNTS = {
    "MOUNT_GAS_SIPHON_I": {
        "symbol": "MOUNT_GAS_SIPHON_I",
        "name": "Gas Siphon I",
        "description": "A basic gas siphon that can extract gas from gas giants and other gas-rich bodies.",
        "strength": 10,
        "requirements": {"crew": 0, "power": 1},
    },
    "MOUNT_GAS_SIPHON_II": {
        "symbol": "MOUNT_GAS_SIPHON_II",
        "name": "Gas Siphon II",
        "description": "An advanced gas siphon that can extract gas from gas giants and other gas-rich bodies more efficiently and at a higher rate.",
        "strength": 20,
        "requirements": {"crew": 2, "power": 2},
    },
    "MOUNT_GAS_SIPHON_III": None,
    "MOUNT_LASER_CANNON_I": None,
    "MOUNT_MINING_LASER_I": {
        "symbol": "MOUNT_MINING_LASER_I",
        "name": "Mining Laser I",
        "description": "A basic mining laser that can be used to extract valuable minerals from asteroids and other space objects.",
        "strength": 3,
        "requirements": {"crew": 1, "power": 1},
    },
    "MOUNT_MINING_LASER_II": {
        "symbol": "MOUNT_MINING_LASER_II",
        "name": "Mining Laser II",
        "description": "An advanced mining laser that is more efficient and effective at extracting valuable minerals from asteroids and other space objects.",
        "strength": 5,
        "requirements": {"crew": 2, "power": 2},
    },
    "MOUNT_MINING_LASER_III": None,
    "MOUNT_MISSILE_LAUNCHER_I": {
        "symbol": "MOUNT_MISSILE_LAUNCHER_I",
        "name": "Missile Launcher",
        "description": "A basic missile launcher that fires guided missiles with a variety of warheads for different targets.",
        "requirements": {"power": 1, "crew": 2},
    },
    "MOUNT_SENSOR_ARRAY_I": None,
    "MOUNT_SENSOR_ARRAY_II": {
        "symbol": "MOUNT_SENSOR_ARRAY_II",
        "name": "Sensor Array II",
        "description": "An advanced sensor array that improves a ship's ability to detect and track other objects in space with greater accuracy and range.",
        "strength": 4,
        "requirements": {"crew": 2, "power": 2},
    },
    "MOUNT_SENSOR_ARRAY_III": None,
    "MOUNT_SURVEYOR_I": {
        "symbol": "MOUNT_SURVEYOR_I",
        "name": "Surveyor I",
        "description": "A basic survey probe that can be used to gather information about a mineral deposit.",
        "strength": 1,
        "deposits": [
            "QUARTZ_SAND",
            "SILICON_CRYSTALS",
            "PRECIOUS_STONES",
            "ICE_WATER",
            "AMMONIA_ICE",
            "IRON_ORE",
            "COPPER_ORE",
            "SILVER_ORE",
            "ALUMINUM_ORE",
            "GOLD_ORE",
            "PLATINUM_ORE",
        ],
        "requirements": {"crew": 1, "power": 1},
    },
    "MOUNT_SURVEYOR_II": {
        "symbol": "MOUNT_SURVEYOR_II",
        "name": "Surveyor II",
        "description": "An advanced survey probe that can be used to gather information about a mineral deposit with greater accuracy.",
        "strength": 2,
        "deposits": [
            "QUARTZ_SAND",
            "SILICON_CRYSTALS",
            "PRECIOUS_STONES",
            "ICE_WATER",
            "AMMONIA_ICE",
            "IRON_ORE",
            "COPPER_ORE",
            "SILVER_ORE",
            "ALUMINUM_ORE",
            "GOLD_ORE",
            "PLATINUM_ORE",
            "DIAMONDS",
            "URANITE_ORE",
        ],
        "requirements": {"crew": 4, "power": 3},
    },
    "MOUNT_SURVEYOR_III": None,
    "MOUNT_TURRET_I": {
        "symbol": "MOUNT_TURRET_I",
        "name": "Rotary Cannon",
        "description": "A rotary cannon is a type of mounted turret that is designed to fire a high volume of rounds in rapid succession.",
        "requirements": {"power": 1, "crew": 1},
    },
}
