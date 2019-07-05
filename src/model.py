import os
import json
import networkx as nx
import random
import math

from . import constants
from .territory import GroundArea, SeaArea
from .player import Player

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
        self.deck = self.create_deck()
        self.random.shuffle(self.deck)
        self.thrashed_cards = []
        # Initialize map
        self.G, self.territories_dict = self.create_graph_map()
        self.grid = NetworkGrid(self.G)
        self.datacollector = DataCollector(model_reporters={
                                              "Armies": get_n_armies_by_player
                                            },
                                           agent_reporters={})
        # Schedule
        self.schedule = RandomActivation(self)
        # Subgraphs
        self.ground_areas = []
        self.sea_areas = []

        territories = list(range(45))
        random.shuffle(territories)

        """
        If there're 4 players, Italia must be owned by the only computer player
        """
        if self.n_players == 4:
            territories.remove(15)  # Remove Italia from the territories
            t = GroundArea(*itemgetter("id", "name", "type", "coords")
                           (self.territories_dict["territories"][15]), model=self)
            t.armies = 3
            t.owner = self.computers[0]
            self.grid.place_agent(t, 15)
            self.ground_areas.append(self.grid.get_cell_list_contents([15])[0])

        """ 
        Connect nodes to territories and assign them to players
        """
        for i, node in enumerate(territories):
            t = GroundArea(*itemgetter("id", "name", "type", "coords")
                           (self.territories_dict["territories"][node]), model=self)
            if i < 9 * self.n_players:
                t.armies = random.randint(2, 5)
                t.owner = self.players[i % self.n_players]
            else:
                t.armies = 3
                t.owner = self.computers[i % self.n_computers]
            self.grid.place_agent(t, node)
            self.ground_areas.append(self.grid.get_cell_list_contents([node])[0])

        """
        Add sea area
        """
        for i, node in enumerate(range(45, 57)):
            t = SeaArea(*itemgetter("id", "name", "type", "coords")
                        (self.territories_dict["sea_areas"][i]), model=self)
            t.trireme = [random.randint(0, 5) for _ in range(self.n_players)]
            self.grid.place_agent(t, node)
            self.sea_areas.append(self.grid.get_cell_list_contents([node])[0])

        self.running = True
        self.datacollector.collect(self)


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

        # for sea in self.territories_dict['sea_areas']:
        for sea in self.sea_areas:
            m = max(sea.trireme)
            players_max_trireme = [player for player, n_trireme in enumerate(sea.trireme) if n_trireme == m]
            if len(players_max_trireme) == 1:
                sea_areas[players_max_trireme[0]] += 1

        return sea_areas

    def count_players_territories_power_places(self):
        territories = [0] * self.n_players
        power_places = [0] * self.n_players

        for territory in self.ground_areas:
            if not territory.owner.computer:
                territories[territory.owner.unique_id] += 1
                if territory.power_place:
                    power_places[territory.owner.unique_id] += 1
        
        return territories, power_places

    def maximum_empires(self):
        # It's a DFS visit in which we account for
        # the length of every connected components
        
        cc_lengths = [0] * self.n_players

        for territory in self.ground_areas:
            territory.found = 0

        for territory in self.ground_areas:
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

    # Controlla se `player` ha vinto oppure se c'è un vincitore tra tutti
    def winner(self, player=None):
        if player is not None:
            if player.victory_points >= self.points_limit:
                return True
            return False

        for p in self.players:
            max_points = -1
            max_player = None
            if p.victory_points > max_points:
                max_points = p.victory_points
                max_player = p

        won = True if max_points > self.points_limit else False
        return max_player, won

    def put_reinforces(self, player, armies):
        territories = self.get_territories_by_player(player)
        random_territory = self.random.randint(0, len(territories) - 1)
        territories[random_territory].armies += armies

    def get_territories_by_player(self, player):
        return [t for t in self.ground_areas if t.owner.unique_id == player.unique_id]

    def step(self):
        """ 
        territories, power_places = self.count_players_territories_power_places()
        empires = self.maximum_empires()
        for player in range(self.n_players):
            self.players[player].update_victory_points(empires, territories, power_places)
        """

        # print(self.grid.get_cell_list_contents(15))
        for player in self.players:
            can_draw = False
            territories, power_places = self.count_players_territories_power_places()
            sea_areas = self.count_players_sea_areas()
            empires = self.maximum_empires()

            # 1) Aggiornamento del punteggio
            player.update_victory_points(empires, territories, sea_areas, power_places)

            # 1.1) Controllo vittoria
            if self.winner(player):
                print("{} - {} ha vinto!".format(player.unique_id, player.color))
                self.running = False
                return True

            # 2) Fase dei rinforzi
            player.update_ground_reinforces_power_places()
            self.put_reinforces(player, player.get_ground_reinforces(territories))
            # player.sacrifice_trireme(sea_area_from, ground_area_to)

            # TODO
            # use card combination
            # displace ground, naval and/or power places on the ground

            # 3) Movimento navale
            # player.naval_movement(sea_area_from, sea_area_to, n_trireme)

            # 4) Combattimento navale
            print('\n\nNAVAL COMBACT!!')
            # Get all sea_areas that the current player can attack
            player_sea_areas = [
                sea_area 
                for sea_area in self.sea_areas 
                if sea_area.trireme[player.unique_id] > 0
            ]
            
            """ and \
                len([
                    adv 
                    for adv, adv_n_trireme in enumerate(sea_area.trireme) 
                    if player.unique_id != adv and \
                        adv_n_trireme > 0 and \
                        sea_area.trireme[player.unique_id] >= min(3, adv_n_trireme)
                ]) > 0 """

            for sea_area in player_sea_areas:
                sea_area.already_fought = True
                possible_adversaries = [
                    adv 
                    for adv, adv_n_trireme in enumerate(sea_area.trireme) 
                    if player.unique_id != adv and \
                        adv_n_trireme > 0 and \
                        sea_area.trireme[player.unique_id] >= min(3, adv_n_trireme)
                ]
                if len(possible_adversaries) > 0:
                    # pick a random player to attack
                    adversary = self.random.randint(0, len(possible_adversaries) - 1)
                    adversary = self.players[possible_adversaries[adversary]]
                    # Randomly select how many attack and defense trireme
                    n_attacker_trireme = sea_area.trireme[player.unique_id]
                    # The defender must always use the maximux number of armies to defend itself
                    # n_defense_trireme = sea_area.trireme[adversary.unique_id] if sea_area.trireme[adversary.unique_id] <= 3 else 3
                    # Let's combact biatch!!
                    print('Start battle!')
                    print('Trireme in ' + sea_area.name + ': ', sea_area.trireme)
                    print('Player ' + str(player.unique_id) + ' attacks Player ' + str(adversary.unique_id) + ' on ' + sea_area.name)
                    player.naval_combact(sea_area, adversary, n_attacker_trireme)

            # 5) Attacchi via mare
            print('\n\nCOMBACT BY SEA!!')
            attackable_ground_areas = []
            for ground_area in self.ground_areas:
                if ground_area.owner.unique_id == player.unique_id  and ground_area.armies > 1:
                    for neighbor in self.grid.get_neighbors(ground_area.unique_id):
                        neighbor = self.grid.get_cell_list_contents([neighbor])[0]
                        # A player can attack a ground area through sea, only if it posesses a number of
                        # trireme greater than the possible adversary. In this random version I check only 
                        # if the current player posess a number of trireme that permits him
                        # to attack at least another player
                        if isinstance(neighbor, SeaArea) and neighbor.trireme[player.unique_id] > min(neighbor.trireme):
                            print('Trireme in ' + neighbor.name + ': ', neighbor.trireme)
                            for sea_area_neighbor in self.grid.get_neighbors(neighbor.unique_id):
                                sea_area_neighbor = self.grid.get_cell_list_contents([sea_area_neighbor])[0]
                                if isinstance(sea_area_neighbor, GroundArea) and \
                                    ground_area.unique_id != sea_area_neighbor.unique_id and \
                                    sea_area_neighbor.owner.unique_id != player.unique_id and \
                                    (sea_area_neighbor.owner.computer or neighbor.trireme[player.unique_id] > neighbor.trireme[sea_area_neighbor.owner.unique_id]) and \
                                    ground_area.armies - 1 >= min(3, sea_area_neighbor.armies):

                                    attackable_ground_areas.append([ground_area, sea_area_neighbor])

            for attackable_ground_area in attackable_ground_areas:
                if attackable_ground_area[0].armies > 1 and not attackable_ground_area[1].already_attacked_by_sea:
                    attackable_ground_area[1].already_attacked_by_sea = True
                    # Randomly select how many attack and defense trireme
                    n_attacker_armies = attackable_ground_area[0].armies - 1
                    # The defender must always use the maximux number of armies to defend itself
                    print('Start battle!')
                    print('Player ' + str(player.unique_id) + ' attacks on ' + attackable_ground_area[1].name + ' from ' + attackable_ground_area[0].name)
                    print('Player ' + str(player.unique_id) + ' attacks with ' + str(n_attacker_armies) + ' armies. Maximux armies: ' + str(attackable_ground_area[0].armies))
                    attackable_ground_area, conquered = player.ground_combact(attackable_ground_area[0], attackable_ground_area[1], n_attacker_armies)
                    if conquered:
                        can_draw = True

            # 6) Attacchi terrestri
            print('\n\nGROUND COMBACT!!')
            attackable_ground_areas = []
            for ground_area in self.ground_areas:
                if ground_area.owner.unique_id == player.unique_id  and ground_area.armies > 1:
                    for neighbor in self.grid.get_neighbors(ground_area.unique_id):
                        neighbor = self.grid.get_cell_list_contents([neighbor])[0]
                        if isinstance(neighbor, GroundArea) and \
                            neighbor.owner.unique_id != player.unique_id and \
                            ground_area.armies - 1 >= min(3, neighbor.armies):
                            
                            attackable_ground_areas.append([ground_area, neighbor])
            
            for attackable_ground_area in attackable_ground_areas:
                if attackable_ground_area[0].armies > 1:
                    attackable_ground_area[1].already_attacked_by_sea = True
                    # Randomly select how many attack and defense trireme
                    n_attacker_armies = attackable_ground_area[0].armies - 1
                    # The defender must always use the maximux number of armies to defend itself
                    print('Start battle!')
                    print('Player ' + str(player.unique_id) + ' attacks on ' + attackable_ground_area[1].name + ' from ' + attackable_ground_area[0].name)
                    print('Player ' + str(player.unique_id) + ' attacks with ' + str(n_attacker_armies) + ' armies. Maximux armies: ' + str(attackable_ground_area[0].armies))
                    attackable_ground_area, conquered = player.ground_combact(attackable_ground_area[0], attackable_ground_area[1], n_attacker_armies)
                    if conquered:
                        can_draw = True


            # 7) Spostamento strategico di fine turno

            # 8) Presa della carta
            # Il giocatore può dimenticarsi di pescare la carta ahah sarebbe bello fare i giocatori smemorati
            if can_draw and random.random() <= .75:
                print("{} can draw".format(player.unique_id))
                player.cards.append(self.draw_a_card())

        self.schedule.step()
        self.datacollector.collect(self)
        return False

    def run_model(self, n):
        for i in range(n):
            self.step()


def get_n_armies_by_player(model, player=None):
    if player is not None:
        return sum([t.armies for t in model.get_territories_by_player(player)])
    else:
        sum_a = 0
        for player in model.players:
            sum_a += sum([t.armies for t in model.get_territories_by_player(player)])
        return sum_a / len(model.players)