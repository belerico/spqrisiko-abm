import os
import json
import networkx as nx
import random

from . import constants
from operator import itemgetter

from mesa import Agent, Model
from mesa.time import RandomActivation
from mesa.datacollection import DataCollector
from mesa.space import NetworkGrid


class SPQRisiko(Model):
    """A SPQRisiko model with some number of players"""

    def __init__(self, n_players, points_limit):
        # How many agent players wiil be
        self.n_players = n_players if n_players <= constants.MAX_PLAYERS else constants.MAX_PLAYERS
        # How many computer players will be
        self.n_computers = constants.MAX_PLAYERS - n_players
        # Creation of player and computer agents
        self.players = [Player(i, computer=False)
                        for i in range(self.n_players)]
        self.computers = [
            Player(i, computer=True)
            for i in range(self.n_players, self.n_players + self.n_computers)]
        self.points_limit = points_limit  # limit at which one player wins
        self.territories = {}
        # self.deck = self.random.shuffle(self.create_deck())
        self.thrashed_cards = []
        # Initialize map
        self.G, self.territories_dict = self.create_graph_map()
        self.grid = NetworkGrid(self.G)
        # self.schedule = RandomActivation(self)

        territories = list(range(45))
        random.shuffle(territories)

        """
        If there're 4 players, Italia must be owned by the only computer player
        """
        if self.n_players == 4:
            territories.remove(15)  # Remove Italia from the territories
            t = Territory(*itemgetter("id", "name", "type", "coords")
                          (self.territories_dict["territories"][15]))
            t.armies = 7
            t.owner = self.computers[0]
            self.grid.place_agent(t, 15)

        """ 
        Connect nodes to territories and assign them to players
        """
        for i, node in enumerate(territories):
            t = Territory(*itemgetter("id", "name", "type", "coords")
                          (self.territories_dict["territories"][node]))
            if i < 9 * self.n_players:
                if node == 15 and self.n_players == 4:
                    continue
                t.armies = 2
                t.owner = self.players[i % self.n_players]
            else:
                t.armies = 7
                t.owner = self.computers[i % self.n_computers]
            self.grid.place_agent(t, node)

    @staticmethod
    def create_graph_map():
        # Read map configuration from file
        with open(os.path.join(os.path.dirname(__file__), "config/territories.json"), "r") as f:
            territories_dict = json.load(f)

        graph_map = nx.Graph()
        for territory in territories_dict["territories"]:
            graph_map.add_node(territory["id"])

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

    def step(self):
        self.schedule.step()

    def run_model(self, n):
        for i in range(n):
            self.step()


class Player(Agent):

    def __init__(self, unique_id, computer, model=SPQRisiko):
        # computer: boolean, human or artificial player
        # artificial players are passive-only
        self.computer = computer
        self.color = constants.COLORS[unique_id %
                                      constants.MAX_PLAYERS]  # one color per id
        super().__init__(unique_id,  model)


class Territory(Agent):

    def __init__(self, unique_id, name, type, coords, model=SPQRisiko):
        # player or list of players (sea territory can be occupied by multiple players)
        self.owner = None
        self.name = name
        self.type = type
        self.coords = coords
        self.armies = 2
        super().__init__(unique_id, model)

    def __hash__(self):
        return self.unique_id
