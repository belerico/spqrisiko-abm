import os, json
import networkx as nx

from .constants import *
from operator import itemgetter

from mesa import Agent, Model
from mesa.time import RandomActivation
from mesa.datacollection import DataCollector
from mesa.space import NetworkGrid


class SPQRisiko(Model):
    """A SPQRisiko model with some number of players"""

    def __init__(self, n_players, points_limit):
        self.n_players = n_players if n_players <= MAX_PLAYERS else MAX_PLAYERS
        self.points_limit = points_limit  # limit at which one player wins
        self.territories = {}
        # Initialize map
        self.G, self.territories_dict = self.create_graph_map()
        self.grid = NetworkGrid(self.G)
        # self.schedule = RandomActivation(self)

        # Connect nodes to territories
        for i, node in enumerate(self.G.nodes()):
            t = Territory(*itemgetter("id", "name", "type", "coords")(self.territories_dict["territories"][i]))

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
        self.color = COLORS[unique_id % MAX_PLAYERS]  # one color per id
        super().__init__(unique_id,  model)


class Territory(Agent):

    def __init__(self, unique_id, name, type, coords, model=SPQRisiko):
        self.owner = None  # player or list of players (sea territory can be occupied by multiple players)
        self.name = name
        self.type = type
        self.coords = coords
        self.armies = 2
        super().__init__(unique_id, model)

    def __hash__(self):
        return self.unique_id

