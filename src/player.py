import math
import random
import operator
import itertools

from .strategies import strategies
from . import constants
from .markov import get_probabilities_ground_combact
from .territory import GroundArea, SeaArea
from mesa import Agent

class Player(Agent):
    
    def __init__(self, unique_id, computer, strategy, goal, model):

        # computer: boolean, human or artificial player
        # artificial players are passive-only
        self.eliminated = False
        self.computer = computer
        self.victory_points = 0
        self.color = constants.COLORS[unique_id %
                                      constants.MAX_PLAYERS]  # one color per id
        self.goal = goal
        self.cards = []
        self.strategy = strategy
        super().__init__(unique_id,  model)

    def get_aggressivity(self):
        if self.strategy == 'Aggressive':
            return .6
        elif self.strategy == 'Neutral':
            return .7
        else:
            return .8

    def update_victory_points(
            self, 
            cc_lengths: list, 
            territories_per_players: list,
            sea_areas_per_players: list,
            power_places: list):

        # print('cc_lengths: ', cc_lengths)
        # print('territories_per_players: ', territories_per_players)
        # print('sea_areas_per_players', sea_areas_per_players)
        # print('power_places: ', power_places)

        m = max(cc_lengths)
        if m >= 4:
            players_max_empire = [
                player for player, n_territories
                in enumerate(cc_lengths) if n_territories == m]
            if len(players_max_empire) == 1 and players_max_empire[0] == self.unique_id:
                print('Player ' + str(self.unique_id) + ' gets one victory point for having the maximum empire')
                self.victory_points += 1

        m = max(territories_per_players)
        players_max_territories = [
            player for player, n_territories
            in enumerate(territories_per_players) if n_territories == m]
        if len(players_max_territories) == 1 and players_max_territories[0] == self.unique_id:
            print('Player ' + str(self.unique_id) + ' gets one victory point for having the max number of ground areas')
            self.victory_points += 1

        m = max(sea_areas_per_players)
        players_max_sea_areas = [
            player for player, n_sea_areas
            in enumerate(sea_areas_per_players) if n_sea_areas == m]
        if len(players_max_sea_areas) == 1 and players_max_sea_areas[0] == self.unique_id:
            print('Player ' + str(self.unique_id) + ' gets one victory point for having the max number of sea areas')
            self.victory_points += 1

        if power_places[self.unique_id] > 0:
            print('Player ' + str(self.unique_id) + ' gets ' + str(power_places[self.unique_id]) + ' victory points from power places')
        
        self.victory_points += power_places[self.unique_id]
        print('Victory points: ', self.victory_points)

    @staticmethod
    def get_ground_reinforces(territories):
        if len(territories) > 11:
            ground_reinforces = math.floor(len(territories) / 3)
        elif len(territories) >= 3:
            ground_reinforces = 3
        else:
            ground_reinforces = 1

        return ground_reinforces

    def update_ground_reinforces_power_places(self):
        for territory in self.model.ground_areas:
            # territory = self.model.grid.get_cell_list_contents([territory['id']])[0]
            if territory.owner == self.unique_id and territory.power_place:
                print('Player ' + str(self.unique_id) + ' got one legionary for power place in ' + territory.name)
                territory.armies += 1

    def sacrifice_trireme(
        self, 
        sea_area_from: SeaArea, 
        ground_area_to: GroundArea):

        sea_area_from.trireme[self.unique_id] -= 1
        ground_area_to.armies[self.unique_id] += 2

    def naval_movement(
        self,
        sea_area_from: SeaArea,
        sea_area_to: SeaArea,
        n_trireme: int):

        sea_area_from.trireme[self.unique_id] -= n_trireme
        sea_area_to.trireme[self.unique_id] += n_trireme

    def naval_combact(self, 
        sea_area: SeaArea, 
        adv, 
        attacker_trireme, 
        aggressivity,
        atta_wins):

        while min(3, attacker_trireme) >= min(3, sea_area.trireme[adv]) and \
                atta_wins[attacker_trireme - 1, sea_area.trireme[adv] - 1] >= aggressivity and \
                attacker_trireme > 0 and \
                sea_area.trireme[adv] > 0:
            
            attacker_dice_outcome = sorted([random.randint(1,6) for _ in range(min(3, attacker_trireme))], reverse=True)
            defender_dice_outcome = sorted([random.randint(1,6) for _ in range(min(3, sea_area.trireme[adv]))], reverse=True)

            print('Player ' + str(self.unique_id) + ' attacks with ' + str(attacker_trireme) + ' trireme.')
            print('Player ' + str(adv) + ' defends with ' + str(sea_area.trireme[adv]) + ' trireme.')
            print('Attacker outcome: ', attacker_dice_outcome)
            print('Defender outcome: ', defender_dice_outcome)
            
            outcomes = list(map(operator.gt, attacker_dice_outcome, defender_dice_outcome))
            for outcome in outcomes:
                if outcome:
                    sea_area.trireme[adv] -= 1
                    print('Defender lose one army')
                else:
                    sea_area.trireme[self.unique_id] -= 1
                    attacker_trireme -= 1
                    print('Attacker lose one army')

        if sea_area.trireme[adv] <= 0:
            print('Defender has lost all of its trireme!')
        elif attacker_trireme <= 0:
            print('Attacker lost the battle!')
        elif atta_wins[attacker_trireme - 1, sea_area.trireme[adv] - 1] < aggressivity:
            print('The attacker has a probability of ' + str(atta_wins[attacker_trireme - 1, sea_area.trireme[adv] - 1]) + ', and is less than ' + str(aggressivity))
        elif min(3, attacker_trireme) < min(3, sea_area.trireme[adv]):
            print('Attacker must attack with a number of trireme that are greater or equal to the number of defender\'s trireme. Combact done!')
    
    def combact_by_sea(
        self, 
        ground_area_from:GroundArea,
        ground_area_to: GroundArea,
        attacker_armies: int):

        conquered = False

        while attacker_armies > 0 and ground_area_to.armies > 0:
            
            attacker_dice_outcome = sorted([random.randint(1,6) for _ in range(min(3, attacker_armies))], reverse=True)
            defender_dice_outcome = sorted([random.randint(1,6) for _ in range(min(3, ground_area_to.armies))], reverse=True)

            print('Player ' + str(self.unique_id) + ' attacks with ' + str(attacker_armies) + ' armies. Maximux armies: ' + str(ground_area_from.armies))
            print('Player ' + str(ground_area_to.owner.unique_id) + ' defends with ' + str(ground_area_to.armies) + ' armies.')
            print('Attacker outcome: ', attacker_dice_outcome)
            print('Defender outcome: ', defender_dice_outcome)
            
            outcomes = list(map(operator.gt, attacker_dice_outcome, defender_dice_outcome))
            for outcome in outcomes:
                if outcome:
                    ground_area_to.armies -= 1
                    print('Defender lose one army')
                else:
                    ground_area_from.armies -= 1
                    attacker_armies -= 1
                    print('Attacker lose one army')

        if ground_area_to.armies <= 0:
            print('Defender has lost the area!')
            ground_area_to.owner = ground_area_from.owner
            conquered = True
        elif attacker_armies <= 0:
            print('Attacker lost the battle!')

        return conquered, min(3, attacker_armies)

    def combact(
        self, 
        ground_area_from:GroundArea,
        ground_area_to: GroundArea,
        attacker_armies: int,
        aggressivity,
        atta_wins):

        conquered = False

        while min(3, attacker_armies) >= min(3, ground_area_to.armies) and \
                atta_wins[attacker_armies - 1, ground_area_to.armies - 1] >= aggressivity and \
                attacker_armies > 0 and \
                ground_area_to.armies > 0:
            
            attacker_dice_outcome = sorted([random.randint(1,6) for _ in range(min(3, attacker_armies))], reverse=True)
            defender_dice_outcome = sorted([random.randint(1,6) for _ in range(min(3, ground_area_to.armies))], reverse=True)

            print('Player ' + str(self.unique_id) + ' attacks with ' + str(attacker_armies) + ' armies. Maximux armies: ' + str(ground_area_from.armies))
            print('Player ' + str(ground_area_to.owner.unique_id) + ' defends with ' + str(ground_area_to.armies) + ' armies.')
            print('Attacker outcome: ', attacker_dice_outcome)
            print('Defender outcome: ', defender_dice_outcome)
            
            outcomes = list(map(operator.gt, attacker_dice_outcome, defender_dice_outcome))
            for outcome in outcomes:
                if outcome:
                    ground_area_to.armies -= 1
                    print('Defender lose one army')
                else:
                    ground_area_from.armies -= 1
                    attacker_armies -= 1
                    print('Attacker lose one army')

        if ground_area_to.armies <= 0:
            print('Defender has lost the area!')
            ground_area_to.owner = ground_area_from.owner
            conquered = True
        elif attacker_armies <= 0:
            print('Attacker lost the battle!')
        elif atta_wins[attacker_armies - 1, ground_area_to.armies - 1] < aggressivity:
            print('The attacker has a probability of ' + str(atta_wins[attacker_armies - 1, ground_area_to.armies - 1]) + ', and is less than ' + str(aggressivity))
        elif min(3, attacker_armies) < min(3, ground_area_to.armies):
            print('Attacker must attack with a number of armies that are greater or equal to the number of defender\'s armies. Combact done!')

        return conquered, min(3, attacker_armies)

    def play_tris(self, model, tris):
        reinforces = model.reinforces_from_tris(tris)
        # remove cards from player and put in trash deck
        for card in tris:
            card = self.cards.pop([i for i, n in enumerate(self.cards) if n["type"] == card["type"]][0])
            model.trashed_cards.append(card)
        return reinforces

    def get_best_tris(self, model):
        if len(self.cards) < 3:
            return None
        best_tris = None
        # Get all possible reinforces combination from tris from cards
        all_tris = [list(t) for t in itertools.combinations(self.cards, 3)]
        all_reinforces = [model.reinforces_from_tris(tris) for tris in all_tris]

        # Remove None from list
        real_tris = [all_tris[i] for i in range(len(all_reinforces)) if all_reinforces[i]]
        all_reinforces = [i for i in all_reinforces if i]
        if len(all_reinforces) == 0:
            return None

        named_tris = []
        for tris in real_tris:
            named_tris.append(model.get_tris_name(tris))
        highest_score = 0
        i = -1
        for i, name in enumerate(named_tris):
            score = model.reinforces_by_goal[name][self.goal]
            if highest_score < score:
                index = i
                highest_score = score

        best_tris = real_tris[i]
        # Play tris if it is a convenient tris (it is in the first half of tris ordered by score)
        return best_tris if model.tris_by_goal[self.goal].index(model.get_tris_name(tris)) <= len(model.tris_by_goal[self.goal]) / 2 else None

    def move_armies_by_goal(self, model):
        if self.goal == "PP":  # Reinforce power place territory by moving armies to it
            pp = model.get_weakest_power_place(self)
            if pp and not model.is_not_attackable(pp):
                # Find neighbor who can reinforce it
                neighbor = model.get_strongest_ally_neighbor(pp)
                if neighbor:
                    if neighbor.armies > 1:
                        armies_to_move = round(max((neighbor.armies - 1) * strategies["PP"]["armies_on_weakest_power_place"], 1))
                        neighbor.armies -= armies_to_move
                        pp.armies += armies_to_move
                        model.log("{} moved {} armies from {} to {}".format(self.color, armies_to_move, neighbor.name, pp.name))

        elif self.goal == "LA":
            # Move armies from non-attackable ground area (if one) to another one
            # Get the first non-attackable ground area with > 1 armies
            non_attackables = model.non_attackable_areas(self)
            if len(non_attackables) > 0:
                i = 0
                moved = False
                while not moved and i < len(non_attackables):
                    non_attackable = non_attackables[i]
                    # Based on strategy move armies to neighbor to get higher units
                    moved = self.move_armies_strategy_based(model, non_attackable)
                    i += 1

        else:  # self.goal == "BE"
            max_empire = model.get_largest_empire(self)
            non_attackables = model.non_attackable_areas(self, max_empire)
            if len(non_attackables) > 0:
                i = 0
                moved = False
                while not moved and i < len(non_attackables):
                    non_attackable = non_attackables[i]
                    # Based on strategy move armies to neighbor to get higher units
                    moved = self.move_armies_strategy_based(model, non_attackable)
                    i += 1

    # Move armies from non attackable area to attackable neighbor based on armies:
    # "Aggressive" -> higher # of armies
    # "Passive" -> lower # of armies
    # "Neutral" -> random
    def move_armies_strategy_based(self, model, area_from):
        attackable_neighbors = []
        for neighbor in model.grid.get_neighbors(area_from.unique_id):
            neighbor = model.grid.get_cell_list_contents([neighbor])[0]
            if isinstance(neighbor, GroundArea) and neighbor.owner.unique_id != area_from.owner.unique_id:
                if not model.is_not_attackable(neighbor, self):
                    attackable_neighbors.append(neighbor)
        if len(attackable_neighbors) == 0:
            return False

        attackable_neighbors.sort(key=lambda x: x.armies, reverse=True)
        if self.strategy == "Aggressive":
            area_to = attackable_neighbors[0]
        elif self.strategy == "Neutral":
            area_to = random.choice(attackable_neighbors)
        else:
            area_to = attackable_neighbors[-1]

        area_to.armies += area_from.armies - 1
        area_from.armies = 1
        return True

    def put_reinforces(self, model, armies, reinforce_type="legionaries"):
        if isinstance(armies, dict):
            for key, value in armies.items():
                self.put_reinforces(model, value, key)
        # TODO: put by goals
        elif reinforce_type == "triremes":
            territories = model.get_territories_by_player(self, "sea")
            if len(territories) > 0:
                if self.goal != "LA":
                    random_territory = model.random.randint(0, len(territories) - 1)
                    territories[random_territory].trireme[model.players.index(self)] += armies
                else:  # Put reinforces on sea area with the lowest number of armies
                    lowest_territory = None
                    low = 0
                    for sea in territories:
                        if not lowest_territory or low > sea.trireme[model.players.index(self)]:
                            low = sea.trireme[model.players.index(self)]
                            lowest_territory = sea
                    if lowest_territory:
                        lowest_territory.trireme[model.players.index(self)] += armies
                print('Player ' + str(self.unique_id) + ' gets ' + str(armies) + ' triremes')
        else:
            territories = model.get_territories_by_player(self, "ground")
            if len(territories) > 0:
                if reinforce_type == "legionaries":
                    # Play legionaries by strategy
                    if self.goal == "PP":
                        # Reinforce (if existing) the weakest power place territory
                        pp = model.get_weakest_power_place(self)
                        if pp:
                            pp_armies = round(max(strategies["PP"]["armies_on_weakest_power_place"] * armies, 1))
                            armies -= pp_armies
                            pp.armies += pp_armies
                        # Reinforce territory near adversary power_place
                        pp = model.get_weakest_adversary_power_place(self)
                        if not pp:
                            idx = model.random.randint(0, len(territories) - 1)
                            territories[idx].armies += armies
                        else:
                            # Find nearest territory to that power place and reinforce it
                            nearest = model.find_nearest(pp, self)
                            if nearest is not None:
                                nearest.armies += armies

                    elif self.goal == "LA":
                        if self.strategy == "Passive" or self.strategy == "Neutral":  # Reinforce weakest territory
                            lowest_territory = None
                            low = 0
                            for ground in territories:
                                if not lowest_territory or low > ground.armies:
                                    low = ground.armies
                                    lowest_territory = ground
                            if lowest_territory:
                                if self.strategy == "Neutral":
                                    add = round(armies / 2)
                                    armies -= add
                                    lowest_territory.armies += add
                                else:
                                    lowest_territory.armies += armies
                        if self.strategy == "Aggressive" or self.strategy == "Neutral":  # Reinforce strongest territory
                            strongest = None
                            strong = 0
                            for ground in territories:
                                if not strongest or strong < ground.armies:
                                    strong = ground.armies
                                    strongest = ground
                            if strongest:
                                strongest.armies += armies
                    elif self.goal == "BE":
                        """
                        If the player goal is to gain victory points based on having the biggest empire, then:
                        - if the strategy is Aggressive, then it'll be reinforced the territory on the border with the largest 
                          number of armies
                        - if the strategy is Passive, then it'll be reinforced the territory on the border with the lesser number
                          of armies
                        - if the strategy is Neutral, both will be reinforced
                        """
                        max_empire = model.get_largest_empire(self)
                        border = []
                        # Get all the territories on the border
                        for ground_area in max_empire:
                            for neighbor in model.grid.get_neighbors(ground_area.unique_id):
                                neighbor = model.grid.get_cell_list_contents([neighbor])[0]
                                if isinstance(neighbor, GroundArea) and neighbor.owner.unique_id != self.unique_id:
                                    border.append(neighbor)
                                    break
                        if border != []:
                            border.sort(key=lambda x: x.armies, reverse=False)
                            if self.strategy == "Aggressive":
                                border[-1].armies += armies
                            elif self.strategy == "Passive":
                                border[0].armies += armies
                            else:
                                i = 0
                                armies_per_territory = math.floor(armies / len(border))
                                while armies > 0:
                                    border[i % len(border)].armies += armies_per_territory
                                    armies -= armies_per_territory
                                    i += 1

                    print('Player ' + str(self.unique_id) + ' gets ' + str(armies) + ' armies')
                else:  # Put Power place by goal
                    # at max 12 power places
                    if model.n_power_places() >= 12:
                        return
                    if self.goal != "PP":
                        idx = model.random.randint(0, len(territories) - 1)
                        territories[idx].power_place = True
                    else:
                        non_attackables = model.non_attackable_areas(self)
                        if len(non_attackables) > 0:
                            idx = 0  # Put power place in the first non attackable ground area
                            non_attackables[idx].power_place = True
                        else:
                            highest_armies_territory = None
                            high = 0
                            for terr in territories:
                                if terr.armies > high or (highest_armies_territory and highest_armies_territory.power_place == False):
                                    high = terr.armies
                                    highest_armies_territory = terr
                            if highest_armies_territory:
                                highest_armies_territory.power_place = True
                    print('Player ' + str(self.unique_id) + ' gets a power place')