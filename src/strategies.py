probs_win = {
    "Passive": 0.7,
    "Neutral": 0.6,
    "Aggressive": 0.5
}

nomads_percentage = {
    "Passive": 0,
    "Neutral": 0.4,
    "Aggressive": 0.8
}

# "tris": list of reinforcements weights, in order legionaries, triremes and power places
strategies = {
    "PP": {  # PP = Control as many Power Places as possible
        "tris": [1, 1, 10],
        "armies_on_weakest_power_place": 0.2
    },
    "BE": {  # BE = Biggest Empire (adjacent ground areas)
        "tris": [2, 1, 1]

    },
    "LA": {  # LA = Control Largest number of Areas
        "tris": [2, 3, 1]
    }
}