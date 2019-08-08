import math
import random
import operator
from . import constants
from .markov import get_probabilities_ground_combact
from .territory import GroundArea, SeaArea
from mesa import Agent

class Player(Agent):
    
    def __init__(
        self, 
        unique_id, 
        computer,
        strategy,
        model):

        # computer: boolean, human or artificial player
        # artificial players are passive-only
        self.computer = computer
        self.victory_points = 0
        self.color = constants.COLORS[unique_id %
                                      constants.MAX_PLAYERS]  # one color per id
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

    def get_ground_reinforces(
            self, 
            territories_per_players: list):
        
        player_territories = territories_per_players[self.unique_id]
        if player_territories > 11:
            ground_reinforces = math.floor(player_territories / 3)
        elif player_territories >= 3 and player_territories <= 11:
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

    def naval_combact(self, sea_area: SeaArea, adv, attacker_trireme, atta_wins):
        aggressivity = self.get_aggressivity()

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
        atta_wins):

        conquered = False
        aggressivity = self.get_aggressivity()

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
