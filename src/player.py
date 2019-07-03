import math
import random
import operator
from . import constants
# from .model import SPQRisiko
from .territory import GroundArea, SeaArea
from mesa import Agent

class Player(Agent):
    
    def __init__(
        self, 
        unique_id, 
        computer, 
        model):

        # computer: boolean, human or artificial player
        # artificial players are passive-only
        self.computer = computer
        self.victory_points = 0
        self.color = constants.COLORS[unique_id %
                                      constants.MAX_PLAYERS]  # one color per id
        super().__init__(unique_id,  model)

    def update_victory_points(
            self, 
            cc_lengths: list, 
            territories_per_players: list,
            sea_areas_per_players: list,
            power_places: list):

        print('cc_lengths: ', cc_lengths)
        print('territories_per_players: ', territories_per_players)
        print('sea_areas_per_players', sea_areas_per_players)
        print('power_places: ', power_places)

        m = max(cc_lengths)
        players_max_empire = [
            player for player, n_territories
            in enumerate(cc_lengths) if n_territories == m]
        if len(players_max_empire) == 1 and players_max_empire[0] == self.unique_id:
            self.victory_points += 1

        m = max(territories_per_players)
        players_max_territories = [
            player for player, n_territories
            in enumerate(territories_per_players) if n_territories == m]
        if len(players_max_territories) == 1 and players_max_territories[0] == self.unique_id:
            self.victory_points += 1

        m = max(sea_areas_per_players)
        players_max_sea_areas = [
            player for player, n_sea_areas
            in enumerate(sea_areas_per_players) if n_sea_areas == m]
        if len(players_max_sea_areas) == 1 and players_max_sea_areas[0] == self.unique_id:
            self.victory_points += 1

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
        for territory in self.model.territories_dict['territories']:
            territory = self.model.grid.get_cell_list_contents([territory['id']])[0]
            if territory.owner == self.unique_id and territory.power_place:
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

    def naval_combact(self, sea_area: SeaArea, adversary, n_attack_trireme, n_defense_trireme):
        attacker_dice_outcome = sorted([random.randint(1,6) for _ in range(n_attack_trireme)], reverse=True)
        defender_dice_outcome = sorted([random.randint(1,6) for _ in range(n_defense_trireme)], reverse=True)
        print('Attacker outcome: ', attacker_dice_outcome)
        print('Defender outcome; ', defender_dice_outcome)
        # outcome = list(map(operator.gt, attacker_dice_outcome, defender_dice_outcome))
        if len(attacker_dice_outcome) > len(defender_dice_outcome):
            for i, def_outcome in enumerate(defender_dice_outcome):
                if attacker_dice_outcome[i] > def_outcome:
                    sea_area.trireme[adversary.unique_id] -= 1
                    print('Defender lose one trireme')
                elif attacker_dice_outcome[i] < def_outcome:
                    sea_area.trireme[self.unique_id] -= 1
                    print('Attacker lose one trireme')
                else:
                    print('No one loses trireme')
        else:
            for i, att_outcome in enumerate(attacker_dice_outcome):
                if att_outcome > defender_dice_outcome[i]:
                    sea_area.trireme[adversary.unique_id] -= 1
                    print('Defender lose one trireme')
                elif att_outcome < defender_dice_outcome[i]:
                    sea_area.trireme[self.unique_id] -= 1
                    print('Attacker lose one trireme')
                else:
                    print('No one loses trireme')