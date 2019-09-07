probs_win = {
    "Passive": 0.65,
    "Neutral": 0.6,
    "Aggressive": 0.5,
    "Very Aggressive": 0.4
}

# "tris": list of reinforcements weights, in order legionaries, triremes and power places
strategies = {
    "PP": {  # PP = Control as many Power Places as possible
        "tris": [1, 1, 10],
        "power_places_multiplier": 1.3,  # or we can make it as a multiplier,
        # so territories with power places are more frequently attacked than others
        "armies_on_weakest_power_place": 0.2
    },
    "BE": {  # BE = Biggest Empire (adjacent ground areas)
        "tris": [2, 1, 1],
        "power_places_multiplier": 1.1

    },
    "LA": {  # LA = Control Largest number of Areas
        "tris": [2, 2, 1],
        "power_places_multiplier": 1.1
    }
}