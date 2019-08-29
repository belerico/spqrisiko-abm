from mesa.visualization.ModularVisualization import ModularServer
from mesa.visualization.UserParam import UserSettableParameter
from mesa.visualization.modules import NetworkModule, ChartModule, BarChartModule, TextElement
import os
from .model import SPQRisiko
from .territory import GroundArea, SeaArea


def network_portrayal(G):
    # The model ensures there is always 1 agent per node

    def node_size(agent):
        if isinstance(agent, GroundArea):
            return min(20, agent.armies + 3)
        else:
            return min(20, max(agent.trireme) + 3)

    def node_color(agent):
        if isinstance(agent, GroundArea):
            return agent.owner.color
        else:
            max_owner = agent.trireme.index(max(agent.trireme))
            return agent.model.players[max_owner].color
            # return '#0000ee'

    def border_color(agent):
        if isinstance(agent, GroundArea):
            if agent.power_place:
                return "white"
        return "transparent"

    def get_info(agent):
        if isinstance(agent, GroundArea):
            s = "{}<br/>{} armies: {}".format(agent.name, agent.owner.color ,agent.armies)
            if agent.power_place > 0:
                s += "<br/>Power place here!"
        else:
            s = "{}<br/>".format(agent.name)
            for player in agent.model.players:
                if agent.trireme[player.unique_id] > 0:
                    s += "{} triremes: {}<br/>".format(player.color, agent.trireme[player.unique_id])
        return s

    def edge_color(agent1, agent2):
        return 'white'

    def edge_width(agent1, agent2):
        return 2

    def get_agents(source, target):
        return G.node[source]['agent'][0], G.node[target]['agent'][0]

    portrayal = dict()
    portrayal['nodes'] = [{'size': node_size(territories[0]),
                           'color': node_color(territories[0]),
                           'border': border_color(territories[0]),
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


class JournalElement(TextElement):
    def __init__(self):
        pass

    def render(self, model):
        return "<h3>Journal</h3>" + "<br/>".join(model.journal)


network = NetworkModule(network_portrayal, 500, 889, canvas_background="/assets/images/map889x500.jpg", library='d3')
journal = JournalElement()
# armies_line = ChartModule([{"Label": "Armies", "Color": "Black"}, {"Label": "Cards", "Color": "Red"}, {"Label": "Trash", "Color": "Green"}])
# cards_bar = BarChartModule([{"Label": "PlayerCards", "Color": "Black"}], scope="agent")

model_params = {
    'n_players': UserSettableParameter('slider', 'Number of players', 4, 3, 5, 1,
                                       description='How many players should play the game?'),
    'points_limit': UserSettableParameter('slider', 'Points limit', 50, 50, 500, 5,
                                       description='How many points should a player reach to win the war?'),
    'strategy': UserSettableParameter('choice', "Which strategy should players play?",
                                          value="Random", choices=["Aggressive", "Defensive", "Neutral", "Random"])
}

server = ModularServer(SPQRisiko, [network, journal], 'S.P.Q.Risiko',
                       os.path.join(os.path.dirname(__file__), "assets/"), model_params)
server.port = 8521

