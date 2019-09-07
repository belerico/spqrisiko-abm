from . import constants
# from .model import SPQRisiko
from mesa import Agent

class Territory(Agent):

    def __init__(
        self, 
        unique_id, 
        name, 
        type, 
        coords, 
        model):

        # player or list of players (sea territory can be occupied by multiple players)
        self.name = name
        self.type = type
        self.coords = coords
        # BFS stats
        self.found = 0
        super().__init__(unique_id, model)

    def __hash__(self):
        return self.unique_id
    
    def __str__(self):
        return "Type: {}\nId: {}\nName: {}\n".format(type(self), self.unique_id, self.name)

    def __repr__(self):
        return self.__str__()


class GroundArea(Territory):

    def __init__(
        self, 
        unique_id, 
        name, 
        type, 
        coords, 
        model):

        Territory.__init__(self, unique_id, name, type, coords, model)
        self.owner = None
        self.armies = 2
        self.power_place = False
        self.already_attacked_by_sea = False

    def __str__(self):
        return super().__str__() + "Owner: {}\nArmies: {}\n".format(self.owner, self.armies)

    def __repr__(self):
        return self.__str__()

class SeaArea(Territory):

    def __init__(
        self, 
        unique_id, 
        name, 
        type, 
        coords, 
        model):
    
        Territory.__init__(self, unique_id, name, type, coords, model)
        # Each position is a player
        # self.owners = [None] * model.n_players
        # In every sea area there must be only one combact per round 
        self.already_fought = False
        self.trireme = [0] * model.n_players 
    
    def __str__(self):
        return super().__str__() + "Trireme: {}\n".format(self.trireme)
    
    def __repr__(self):
        return self.__str__()
