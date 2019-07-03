import os
import json
import networkx as nx
import random
import math

from . import constants
from operator import itemgetter

from mesa import Agent, Model
from mesa.time import RandomActivation
from mesa.datacollection import DataCollector
from mesa.space import NetworkGrid


class SPQRisiko(Model):
    """A SPQRisiko model with some number of players"""

    def __init__(self, n_players, points_limit):
        super().__init__()
        # How many agent players wiil be
        self.n_players = n_players if n_players <= constants.MAX_PLAYERS else constants.MAX_PLAYERS
        # How many computer players will be
        self.n_computers = constants.MAX_PLAYERS - n_players
        # Creation of player and computer agents
        self.players = [Player(i, computer=False, model=self)
                        for i in range(self.n_players)]
        self.computers = [
            Player(i, computer=True, model=self)
            for i in range(self.n_players, self.n_players + self.n_computers)]
        self.points_limit = points_limit  # limit at which one player wins
        # self.deck = self.random.shuffle(self.create_deck())
        self.thrashed_cards = []
        # Initialize map
        self.G, self.territories_dict = self.create_graph_map()
        self.grid = NetworkGrid(self.G)
        self.schedule = RandomActivation(self)

        territories = list(range(45))
        random.shuffle(territories)

        """
        If there're 4 players, Italia must be owned by the only computer player
        """
        if self.n_players == 4:
            territories.remove(15)  # Remove Italia from the territories
            t = GroundArea(*itemgetter("id", "name", "type", "coords")
                           (self.territories_dict["territories"][15]), model=self)
            t.armies = 7
            t.owner = self.computers[0]
            self.grid.place_agent(t, 15)

        """ 
        Connect nodes to territories and assign them to players
        """
        for i, node in enumerate(territories):
            t = GroundArea(*itemgetter("id", "name", "type", "coords")
                           (self.territories_dict["territories"][node]), model=self)
            if i < 9 * self.n_players:
                t.armies = 2
                t.owner = self.players[i % self.n_players]
            else:
                t.armies = 7
                t.owner = self.computers[i % self.n_computers]
            self.grid.place_agent(t, node)

        """
        Add sea area
        """
        for i, node in enumerate(range(45, 57)):
            t = SeaArea(*itemgetter("id", "name", "type", "coords")
                        (self.territories_dict["sea_areas"][i]), model=self)
            self.grid.place_agent(t, node)

    @staticmethod
    def create_graph_map():
        # Read map configuration from file
        with open(os.path.join(os.path.dirname(__file__), "config/territories.json"), "r") as f:
            territories_dict = json.load(f)

        graph_map = nx.Graph()

        for territory in territories_dict["territories"]:
            graph_map.add_node(territory["id"])
        for sea in territories_dict['sea_areas']:
            graph_map.add_node(sea['id'])
        for edges in territories_dict["edges"]:
            graph_map.add_edge(edges[0], edges[1])

        return graph_map, territories_dict

    @staticmethod
    def create_deck(custom_numbers=None):
        # Read deck from configuration file
        deck = []
        with open(os.path.join(os.path.dirname(__file__), "config/cards.json"), "r") as f:
            cards = json.load(f)

        # custom cards' numbers
        if custom_numbers:
            # do something
            return deck
        for card in cards:
            c = {
                "type": card["type"],
                "adds_on_tris": card["adds_on_tris"],
                "image": card["image"]
            }
            for _ in range(card["number_in_deck"]):
                deck.append(c)

        return deck

    def draw_a_card(self):
        # if deck is empty, refill from thrashed cards
        if len(self.deck) == 0:
            if len(self.thrashed_cards) == 0:
                # We finished cards, players must do some tris to refill deck!
                return None
            self.deck.extend(self.thrashed_cards)

        # return last card from deck
        return self.deck.pop()

    @staticmethod
    def reinforces_from_tris(cards):
        assert len(cards) == 3, "Wrong number of cards given to 'tris' method"
        cards_in_tris = set([card["type"] for card in cards])
        assert len(cards_in_tris) == 3 or len(cards_in_tris) == 1, \
            "Tris must be composed of three different cards or three of the same type"
        reinforces = {
            "legionaries": 8 if len(cards_in_tris) == 1 else 10,
            "centers": 0,
            "trireme": 0
        }
        for card in cards:
            for key, value in card["adds_on_tris"].items():
                reinforces[key] += value
        return reinforces

    def count_players_sea_areas(self):
        sea_areas = [0] * self.n_players

        for sea in self.territories_dict['sea_areas']:
            sea = self.grid.get_cell_list_contents([sea['id']])[0]
            m = max(sea.trireme)
            players_max_trireme = [player for player, n_trireme in enumerate(sea.trireme) if n_trireme == m]
            if len(players_max_trireme) == 1:
                sea_areas[players_max_trireme] += 1

        return sea_areas

    def count_players_territories_power_places(self):
        territories = [0] * self.n_players
        power_places = [0] * self.n_players

        # for territory in self.grid.get_all_cell_contents():
        for territory in self.territories_dict['territories']:
            territory = self.grid.get_cell_list_contents([territory['id']])[0]
            # if isinstance(territory, GroundArea):
            if not territory.owner.computer:
                territories[territory.owner.unique_id] += 1
                if territory.power_place:
                    power_places[territory.owner.unique_id] += 1
        
        return territories, power_places

    def maximum_empires(self):
        # It's a DFS visit in which we account for
        # the length of every connected components
        
        cc_lengths = [0] * self.n_players
        
        for territory in self.territories_dict['territories']:
            territory = self.grid.get_cell_list_contents([territory['id']])[0]
            territory.found = 0
        
        for territory in self.territories_dict['territories']:
            territory = self.grid.get_cell_list_contents([territory['id']])[0]
            if not territory.owner.computer and territory.found == 0:
                distance = self.__dfs_visit__(territory, 0)
                if distance > cc_lengths[territory.owner.unique_id]:
                    cc_lengths[territory.owner.unique_id] = distance
        
        return cc_lengths

    def __dfs_visit__(self, territory, d):
        territory.found = 1
        for neighbor in self.grid.get_neighbors(territory.unique_id):
            neighbor = self.grid.get_cell_list_contents([neighbor])[0]
            if isinstance(neighbor, GroundArea) and neighbor.found == 0 and neighbor.owner.unique_id == territory.owner.unique_id:
                d = self.__dfs_visit__(neighbor, d)
        return d + 1

    def step(self):
        """ 
        territories, power_places = self.count_players_territories_power_places()
        empires = self.maximum_empires()
        for player in range(self.n_players):
            self.players[player].update_victory_points(empires, territories, power_places)
        """

        for player in self.players:
            territories, power_places = self.count_players_territories_power_places()
            sea_areas = self.count_players_sea_areas()
            empires = self.maximum_empires()

            # 1) Aggiornamento del punteggio
            player.update_victory_points(empires, territories, sea_areas, power_places)

            # 2) Fase dei rinforzi
            player.update_ground_reinforces_power_places()
            ground_reinforces = player.get_ground_reinforces(territories)
            # player.sacrifice_trireme(sea_area_from, ground_area_to)

            # TODO
            # use card combination
            # displace ground, naval and/or power places on the ground

            # 3) Movimento navale
            # player.naval_movement(sea_area_from, sea_area_to, n_trireme)

            # 4) Combattimento navale

            # 5) Attacchi via mare

            # 6) Attacchi terrestri

            # 7) Spostamento strategico di fine turno

            # 8) Presa della carta
        self.schedule.step()

    def run_model(self, n):
        for i in range(n):
            self.step()


class Player(Agent):
    
    def __init__(
        self, 
        unique_id, 
        computer, 
        model=SPQRisiko):

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
        sea_area_from, 
        ground_area_to):

        sea_area_from.trireme[self.unique_id] -= 1
        ground_area_to.armies[self.unique_id] += 2

    def naval_movement(
        self,
        sea_area_from,
        sea_area_to,
        n_trireme: int):

        sea_area_from.trireme[self.unique_id] -= n_trireme
        sea_area_to.trireme[self.unique_id] += n_trireme

class Territory(Agent):

    def __init__(
        self, 
        unique_id, 
        name, 
        type, 
        coords, 
        model=SPQRisiko):

        # player or list of players (sea territory can be occupied by multiple players)
        self.name = name
        self.type = type
        self.coords = coords
        # BFS stats
        self.found = 0
        super().__init__(unique_id, model)

    def __hash__(self):
        return self.unique_id


class GroundArea(Territory):

    def __init__(
        self, 
        unique_id, 
        name, 
        type, 
        coords, 
        model=SPQRisiko):

        Territory.__init__(self, unique_id, name, type, coords, model)
        self.owner = None
        self.armies = 2
        self.power_place = False


class SeaArea(Territory):

    def __init__(
        self, 
        unique_id, 
        name, 
        type, 
        coords, 
        model=SPQRisiko):
    
        Territory.__init__(self, unique_id, name, type, coords, model)
        # Each position is a player
        # self.owners = [None] * model.n_players
        self.trireme = [0] * model.n_players 
