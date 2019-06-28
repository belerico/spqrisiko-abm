from mesa.visualization.ModularVisualization import ModularServer
from mesa.visualization.UserParam import UserSettableParameter
from mesa.visualization.modules import NetworkModule
import os
from .model import SPQRisiko


def network_portrayal(G):
    # The model ensures there is always 1 agent per node

    def node_size(agent):
        return agent.armies + 3

    def node_color(agent):
        if agent.owner is None:
            return '#FF0000'
        return agent.owner.color
        # return '#FF0000'

    def edge_color(agent1, agent2):
        return '#e8e8e8'

    def edge_width(agent1, agent2):
        return 2

    def get_agents(source, target):
        return G.node[source]['agent'][0], G.node[target]['agent'][0]

    portrayal = dict()
    portrayal['nodes'] = [{'size': node_size(territories[0]),
                           'color': node_color(territories[0]),
                           'tooltip': "{}: {}<br/>coords: {}, {}".format(territories[0].unique_id,
                                                                         territories[0].name,
                                                                         territories[0].coords["x"],
                                                                         territories[0].coords["y"]),
                           "xx": territories[0].coords["x"],
                           "yy": territories[0].coords["y"],
                           }
                          for (_, territories) in G.nodes.data('agent')]

    portrayal['edges'] = [{'source': source,
                           'target': target,
                           'color': edge_color(*get_agents(source, target)),
                           'width': edge_width(*get_agents(source, target)),
                           }
                          for (source, target) in G.edges]

    return portrayal


network = NetworkModule(network_portrayal, 500, 889, canvas_background="/assets/images/map889x500.jpg", library='d3')

model_params = {
    'n_players': UserSettableParameter('slider', 'Number of players', 4, 3, 5, 1,
                                       description='Choose how many players should play the game'),
    'points_limit': UserSettableParameter('slider', 'Points limit', 100, 100, 500, 5,
                                       description='How many points should a player reach to win the war?'),
}

server = ModularServer(SPQRisiko, [network], 'S.P.Q.Risiko',
                       os.path.join(os.path.dirname(__file__), "assets/"), model_params)
server.port = 8521

