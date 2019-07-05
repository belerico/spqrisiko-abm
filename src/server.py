from mesa.visualization.ModularVisualization import ModularServer
from mesa.visualization.UserParam import UserSettableParameter
from mesa.visualization.modules import NetworkModule, ChartModule
import os
from .model import SPQRisiko
from .territory import GroundArea, SeaArea


def network_portrayal(G):
    # The model ensures there is always 1 agent per node

    def node_size(agent):
        if isinstance(agent, GroundArea):
            return agent.armies + 3
        else:
            return max(agent.trireme) + 3

    def node_color(agent):
        if isinstance(agent, GroundArea):
            return agent.owner.color
        else:
            max_owner = agent.trireme.index(max(agent.trireme))
            return agent.model.players[max_owner].color
            # return '#0000ee'

    def get_info(agent):
        if isinstance(agent, GroundArea):
            return "{}<br/>N. armies: {}".format(agent.name, agent.armies)
        else:
            s = "{}<br/>".format(agent.name)
            for player in range(agent.model.n_players):
                s += "N. trireme player {}: {}<br/>".format(player, agent.trireme[player])
            return s

    def edge_color(agent1, agent2):
        return '#e8e8e8'

    def edge_width(agent1, agent2):
        return 2

    def get_agents(source, target):
        return G.node[source]['agent'][0], G.node[target]['agent'][0]

    portrayal = dict()
    portrayal['nodes'] = [{'size': node_size(territories[0]),
                           'color': node_color(territories[0]),
                           'tooltip': get_info(territories[0]),
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
armies_line = ChartModule([{"Label": "Armies", "Color": "Black"}])

model_params = {
    'n_players': UserSettableParameter('slider', 'Number of players', 4, 3, 5, 1,
                                       description='Choose how many players should play the game'),
    'points_limit': UserSettableParameter('slider', 'Points limit', 50, 50, 500, 5,
                                       description='How many points should a player reach to win the war?'),
}

server = ModularServer(SPQRisiko, [network, armies_line], 'S.P.Q.Risiko',
                       os.path.join(os.path.dirname(__file__), "assets/"), model_params)
server.port = 8521

