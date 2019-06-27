import os, json
import networkx as nx

from mesa import Agent, Model
from mesa.time import RandomActivation
from mesa.datacollection import DataCollector
from mesa.space import NetworkGrid


class SPQRisiko(Model):
    """A SPQRisiko model with some number of players"""

    def __init__(self, n_players=2):

        self.n_players = n_players if n_players <= 5 else 5
        self.territories = {}
        # Initialize map
        self.G, self.territories_dict = self.create_graph_map()
        self.grid = NetworkGrid(self.G)
        self.schedule = RandomActivation(self)

        # Connect nodes to territories
        for i, node in enumerate(self.G.nodes()):
            t = Territory(self.territories_dict["territories"][i])

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
        # collect data
        self.datacollector.collect(self)

    def run_model(self, n):
        for i in range(n):
            self.step()


class Player(Agent):

    def __init__(self, unique_id, model=SPQRisiko):
        super().__init__(unique_id,  model)


class Territory(Agent):

    def __init__(self, territory_dict, model=SPQRisiko):
        self.dict = territory_dict
        self.name = territory_dict["name"]
        self.type = territory_dict["type"]
        self.armies = 2
        super().__init__(territory_dict["id"], model)

    def __hash__(self):
        return self.unique_id

    def toJSON(self):
        return json.dumps(self, default=lambda o: o.__dict__,
                          sort_keys=True, indent=4)
