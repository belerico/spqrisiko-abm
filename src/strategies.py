probs_win = {
    "Passive": 0.7,
    "Neutral": 0.62,
    "Aggressive": 0.55,
    "Very Aggressive": 0.5
}

# "tris": list of reinforcements weights, in order legionaries, triremes and power places
strategies = {
    "PP": {  # PP = Control as many Power Places as possible
        "tris": [1, 1, 10],
        "power_places_multiplier": 1.3  # or we can make it as a multiplier,
        # so territories with power places are more frequently attacked than others
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