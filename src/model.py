import os
import math
import json
import networkx as nx
import random
import collections, itertools

from . import constants
from .markov import get_probabilities_ground_combact, get_probabilities_combact_by_sea
from .territory import GroundArea, SeaArea
from .player import Player
from . import markov

from operator import itemgetter

from mesa import Agent, Model
from mesa.time import RandomActivation
from mesa.datacollection import DataCollector
from mesa.space import NetworkGrid


class SPQRisiko(Model):
    """A SPQRisiko model with some number of players"""

    def __init__(self, n_players, points_limit, strategy):
        super().__init__()
        # How many agent players wiil be
        self.n_players = n_players if n_players <= constants.MAX_PLAYERS else constants.MAX_PLAYERS
        # How many computer players will be
        self.n_computers = constants.MAX_PLAYERS - n_players
        # Creation of player and computer agents
        self.players = [Player(i, computer=False, strategy=self.get_strategy_setup(strategy), model=self)
                        for i in range(self.n_players)]
        self.computers = [
            Player(i, computer=True, strategy="Neutral", model=self)
            for i in range(self.n_players, self.n_players + self.n_computers)]
        self.points_limit = points_limit  # limit at which one player wins
        self.deck = self.create_deck()
        self.random.shuffle(self.deck)
        self.trashed_cards = []
        # Initialize map
        self.G, self.territories_dict = self.create_graph_map()
        self.grid = NetworkGrid(self.G)
        self.datacollector = DataCollector(model_reporters={
                                              "Armies": get_n_armies_by_player,
                                              "Cards": lambda m: len(m.deck),
                                              "Trash": lambda m: len(m.trashed_cards)
                                            },
                                           agent_reporters={
                                               "PlayerCards": lambda p: len(p.cards)
                                           })
        # Schedule
        self.schedule = RandomActivation(self)
        # Subgraphs
        self.ground_areas = []
        self.sea_areas = []
        # Probabilities that the attacker wins on a ground combact
        self.atta_wins_combact, _, _ = get_probabilities_ground_combact(10, 10)
        # Probabilities that the attacker wins on a combact by sea
        self.atta_wins_combact_by_sea, _, _ = get_probabilities_combact_by_sea(10, 10)

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

    def get_strategy_setup(self, strategy):
        strategies = ["Aggressive", "Passive", "Neutral"]
        if strategy == "Random":
            strategy = self.random.choice(strategies)
        return strategy

    @staticmethod
    def get_win_probability_threshold_from_strategy(strategy):
        probs = {
            "Passive": 0.8,
            "Neutral": 0.7,
            "Aggressive": 0.6
        }
        return probs[strategy]

    @staticmethod
    def get_movable_armies_by_strategy(strategy, minimum, maximum):
        nomads_percentage = {
            "Passive": 0,
            "Neutral": 0.5,
            "Aggressive": 1
        }
        return round((maximum - minimum) * nomads_percentage[strategy] + minimum)

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
        # if deck is empty, refill from trashed cards
        if len(self.deck) == 0:
            if len(self.trashed_cards) == 0:
                # We finished cards, players must do some tris to refill deck!
                return None
            self.deck.extend(self.trashed_cards)
            self.trashed_cards = []

        # return last card from deck
        return self.deck.pop()

    @staticmethod
    def reinforces_from_tris(cards):
        # assert len(cards) == 3, "Wrong number of cards given to 'tris' method"
        if len(cards) != 3:
            return None
        cards_in_tris = set([card["type"] for card in cards])
        # assert len(cards_in_tris) == 3 or len(cards_in_tris) == 1, \
        #     "Tris must be composed of three different cards or three of the same type"
        if len(cards_in_tris) != 3 and len(cards_in_tris) != 1:
            return None
        reinforces = {
            "legionaries": 8 if len(cards_in_tris) == 1 else 10,
            "centers": 0,
            "triremes": 0
        }
        for card in cards:
            for key, value in card["adds_on_tris"].items():
                reinforces[key] += value
        return reinforces

    @staticmethod
    def get_best_tris(cards):
        if len(cards) < 3:
            return None
        best_tris = None
        # Get all possible reinforces combination from tris from cards
        all_tris = [list(t) for t in itertools.combinations(cards, 3)]
        all_reinforces = [SPQRisiko.reinforces_from_tris(tris) for tris in all_tris]

        # Remove None from list
        real_tris = [all_tris[i] for i in range(len(all_reinforces)) if all_reinforces[i]]
        all_reinforces = [i for i in all_reinforces if i]
        if len(all_reinforces) == 0:
            return None
        # TODO: change 1,2,3 multiplier based on what we think it is better
        quantify_reinforces = [1*r["legionaries"] + 2*r["triremes"] + 3*r["centers"] for r in all_reinforces if r]
        index = quantify_reinforces.index(max(quantify_reinforces))
        best_tris = real_tris[index]
        return best_tris

    def play_tris(self, tris, player):
        reinforces = self.reinforces_from_tris(tris)
        # remove cards from player and put in trash deck
        for card in tris:
            card = player.cards.pop([i for i, n in enumerate(player.cards) if n["type"] == card["type"]][0])
            self.trashed_cards.append(card)
        return reinforces

    def count_players_sea_areas(self):
        sea_areas = [0] * self.n_players

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

    def put_reinforces(self, player, armies, reinforce_type="legionaries"):
        if isinstance(armies, dict):
            for key, value in armies.items():
                self.put_reinforces(player, value, key)
        elif reinforce_type == "triremes":
            territories = self.get_territories_by_player(player, "sea")
            if len(territories) > 0:
                random_territory = self.random.randint(0, len(territories) - 1)
                territories[random_territory].trireme[self.players.index(player)] += armies
                print('Player ' + str(player.unique_id) + ' gets ' + str(armies) + ' triremes')
        else:
            territories = self.get_territories_by_player(player, "ground")
            if len(territories) > 0:
                random_territory = self.random.randint(0, len(territories) - 1)
                if reinforce_type == "legionaries":
                    territories[random_territory].armies += armies
                    print('Player ' + str(player.unique_id) + ' gets ' + str(armies) + ' legionaries')
                else:
                    territories[random_territory].power_place = True
                    print('Player ' + str(player.unique_id) + ' gets a power place')

    def get_territories_by_player(self, player: Player, ground_type="ground"):
        if ground_type == "ground":
            return [t for t in self.ground_areas if t.owner.unique_id == player.unique_id]
        elif ground_type == "sea":
            return [t for t in self.sea_areas if t.trireme[self.players.index(player)] > 0]

    def update_atta_wins_combact_matrix(self, attacker_armies, defender_armies, mat_type='combact'):
        if mat_type == 'combact':
            if attacker_armies > self.atta_wins_combact.shape[0] and defender_armies > self.atta_wins_combact.shape[1]:
                self.atta_wins_combact, _, _ = get_probabilities_ground_combact(attacker_armies, defender_armies)
            elif attacker_armies > self.atta_wins_combact.shape[0]:
                self.atta_wins_combact, _, _ = get_probabilities_ground_combact(attacker_armies, self.atta_wins_combact.shape[1])
            elif defender_armies > self.atta_wins_combact.shape[1]:
                self.atta_wins_combact, _, _ = get_probabilities_ground_combact(self.atta_wins_combact.shape[0], defender_armies)
        elif mat_type == 'combact_by_sea':
            if attacker_armies > self.atta_wins_combact_by_sea.shape[0] and defender_armies > self.atta_wins_combact_by_sea.shape[1]:
                self.atta_wins_combact, _, _ = get_probabilities_ground_combact(attacker_armies, defender_armies)
            elif attacker_armies > self.atta_wins_combact_by_sea.shape[0]:
                self.atta_wins_combact, _, _ = get_probabilities_ground_combact(attacker_armies, self.atta_wins_combact_by_sea.shape[1])
            elif defender_armies > self.atta_wins_combact_by_sea.shape[1]:
                self.atta_wins_combact, _, _ = get_probabilities_ground_combact(self.atta_wins_combact_by_sea.shape[0], defender_armies)

    def step(self):
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
            print('\n\nREINFORCES')
            player.update_ground_reinforces_power_places()
            self.put_reinforces(player, player.get_ground_reinforces(territories))
            # player.sacrifice_trireme(sea_area_from, ground_area_to)

            # use card combination
            # displace ground, naval and/or power places on the ground
            tris = self.get_best_tris(player.cards)

            if tris:
                reinforces = self.play_tris(tris, player)
                self.put_reinforces(player, reinforces)

            # 3) Movimento navale
            # player.naval_movement(sea_area_from, sea_area_to, n_trireme)

            # 4) Combattimento navale
            print('\n\nNAVAL COMBACT!!')
            # Get all sea_areas that the current player can attack
            attackable_sea_areas = []
            for sea_area in self.get_territories_by_player(player, ground_type='sea'):
                # Choose the adversary that has the lower probability of winning the combact
                min_trireme = min(sea_area.trireme)
                if min_trireme > 0:
                    adv_min_trireme = sea_area.trireme.index(min_trireme)
                    # Check if the atta_wins_combact probabilities matrix needs to be recomputed 
                    self.update_atta_wins_combact_matrix(sea_area.trireme[player.unique_id], sea_area.trireme[adv_min_trireme])
                    if player.unique_id != adv_min_trireme and self.atta_wins_combact[sea_area.trireme[player.unique_id], sea_area.trireme[adv_min_trireme]] >= player.get_aggressivity():
                        attackable_sea_areas.append([sea_area, adv_min_trireme])

            for sea_area, adv in attackable_sea_areas:
                # Randomly select how many attack and defense trireme
                attacker_trireme = sea_area.trireme[player.unique_id]
                # The defender must always use the maximux number of armies to defend itself
                # n_defense_trireme = sea_area.trireme[adversary.unique_id] if sea_area.trireme[adversary.unique_id] <= 3 else 3
                # Let's combact biatch!!
                print('Start battle!')
                print('Trireme in ' + sea_area.name + ': ', sea_area.trireme)
                print('Player ' + str(player.unique_id) + ' attacks Player ' + str(adv) + ' on ' + sea_area.name)
                player.naval_combact(sea_area, adv, attacker_trireme, self.atta_wins_combact)

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
                            # print('Trireme in ' + neighbor.name + ': ', neighbor.trireme)
                            for sea_area_neighbor in self.grid.get_neighbors(neighbor.unique_id):
                                sea_area_neighbor = self.grid.get_cell_list_contents([sea_area_neighbor])[0]
                                if isinstance(sea_area_neighbor, GroundArea) and \
                                    ground_area.unique_id != sea_area_neighbor.unique_id and \
                                    sea_area_neighbor.owner.unique_id != player.unique_id and \
                                    (sea_area_neighbor.owner.computer or neighbor.trireme[player.unique_id] > neighbor.trireme[sea_area_neighbor.owner.unique_id]):
                                    
                                    has_enemies = False
                                    ground_area_neighbors = self.grid.get_neighbors(ground_area.unique_id)
                                    for ground_area_neighbor in ground_area_neighbors:
                                        ground_area_neighbor = self.grid.get_cell_list_contents([ground_area_neighbor])[0]
                                        if isinstance(ground_area_neighbor, GroundArea) and ground_area_neighbor.owner.unique_id != ground_area.owner.unique_id:
                                            has_enemies = True
                                            break
                                    if has_enemies and ground_area.armies - 2 >= min(3, sea_area_neighbor.armies):
                                        attackable_ground_areas.append([ground_area, sea_area_neighbor, 2])
                                    elif not has_enemies and ground_area.armies - 1 >= min(3, sea_area_neighbor.armies):
                                        attackable_ground_areas.append([ground_area, sea_area_neighbor, 1])

            for ground_area_from, ground_area_to, armies_to_left in attackable_ground_areas:
                if ground_area_from.armies - armies_to_left > armies_to_left and not ground_area_to.already_attacked_by_sea:
                    ground_area_to.already_attacked_by_sea = True

                    # Attacker always attacks with the maximum number of armies
                    # The defender must always use the maximux number of armies to defend itself
                    attacker_armies = ground_area_from.armies - armies_to_left

                    # Check if the atta_wins_combact_by_sea probabilities matrix needs to be recomputed                   
                    self.update_atta_wins_combact_matrix(attacker_armies, ground_area_to.armies, mat_type='combact_by_sea')

                    print('Start battle!')
                    print('Player ' + str(player.unique_id) + ' attacks on ' + ground_area_to.name + ' from ' + ground_area_from.name)
                    conquered = player.combact_by_sea(ground_area_from, ground_area_to, attacker_armies)
                    if conquered:
                        can_draw = True

            for ground_area in self.ground_areas:
                ground_area.already_attacked_by_sea = False

            # 6) Attacchi terrestri
            print('\n\nGROUND COMBACT!!')

            attacks = self.get_attackable_ground_areas(player)
            attacks.sort(key=lambda x: x["prob_win"], reverse=True)

            i = 0
            while len(attacks) > i:
                attack = attacks[i]
                n_attacker_armies = attack["attacker"].armies - 1
                # The defender must always use the maximux number of armies to defend itself
                # Check if the atta_wins_ground_combact probabilities matrix needs to be recomputed
                self.update_atta_wins_combact_matrix(n_attacker_armies, attack["defender"].armies)
                print('Battle: {} (player {}) with {} VS {} (player {}) with {}'.format(
                        attack["attacker"].name, player.unique_id, n_attacker_armies,
                        attack["defender"].name, attack["defender"].owner.unique_id, attack["defender"].armies
                ))
                conquered, min_moveable_armies = player.combact(attack["attacker"], attack["defender"], n_attacker_armies, self.atta_wins_combact)
                if conquered:
                    # Move armies from attacker area to conquered
                    max_moveable_armies = attack["attacker"].armies - 1
                    nomads = SPQRisiko.get_movable_armies_by_strategy(player.strategy, min_moveable_armies, max_moveable_armies)
                    attack["attacker"].armies -= nomads
                    attack["defender"].armies = nomads
                    can_draw = True
                    # Re-sort newly attackable areas with newer probabilities
                    attacks = self.get_attackable_ground_areas(player)
                    attacks.sort(key=lambda x: x["prob_win"], reverse=True)
                else:
                    i += 1

            # 7) Spostamento strategico di fine turno
            # Move armies from non-attackable ground area (if one) to another one
            # Get the first non-attackable ground area with > 1 armies
            non_attackables = self.non_attackable_areas(player)
            if len(non_attackables) > 0:
                i = 0
                moved = False
                while not moved and i < len(non_attackables):
                    non_attackable = non_attackables[i]
                    # Based on strategy move armies to neighbor to get higher units
                    moved = self.move_armies_strategy_based(player, non_attackable)
                    i += 1


            # 8) Presa della carta
            # Il giocatore può dimenticarsi di pescare la carta ahah sarebbe bello fare i giocatori smemorati
            if can_draw and random.random() <= .75:
                card = self.draw_a_card()
                if card:
                    player.cards.append(card)

        self.schedule.step()
        self.datacollector.collect(self)
        return False

    def get_attackable_ground_areas(self, player):
        attacks = []
        for ground_area in self.ground_areas:
            if ground_area.owner.unique_id == player.unique_id and ground_area.armies > 1:
                for neighbor in self.grid.get_neighbors(ground_area.unique_id):
                    neighbor = self.grid.get_cell_list_contents([neighbor])[0]
                    if isinstance(neighbor, GroundArea) and \
                        neighbor.owner.unique_id != player.unique_id and \
                            ground_area.armies - 1 >= min(3, neighbor.armies):
                        self.update_atta_wins_combact_matrix(ground_area.armies - 1, neighbor.armies)
                        prob_win = self.atta_wins_combact[ground_area.armies - 2, neighbor.armies - 1]
                        if prob_win >= SPQRisiko.get_win_probability_threshold_from_strategy(player.strategy):
                            attacks.append({
                                "defender": neighbor,
                                "attacker": ground_area,
                                "prob_win": prob_win
                            })

        return attacks

    # Get non attackable areas wiht at least 2 armies and with an ally neighbor
    def non_attackable_areas(self, player):
        non_attackables = []
        for ground_area in self.ground_areas:
            if ground_area.owner.unique_id == player.unique_id and ground_area.armies > 1:
                attackable, has_ally_neighbor = False, False
                for neighbor in self.grid.get_neighbors(ground_area.unique_id):
                    neighbor = self.grid.get_cell_list_contents([neighbor])[0]
                    if isinstance(neighbor, GroundArea) and neighbor.owner.unique_id != player.unique_id:
                        attackable = True
                        break
                    has_ally_neighbor = True

                if not attackable and has_ally_neighbor:
                    non_attackables.append(ground_area)

        return non_attackables

    def is_not_attackable(self, area, player):
        for neighbor in self.grid.get_neighbors(area.unique_id):
            neighbor = self.grid.get_cell_list_contents([neighbor])[0]
            if neighbor.owner.unique_id != player.unique_id:
                return False

        return True

    def is_neighbor_of(self, area1, area2):
        for neighbor in self.grid.get_neighbors(area1.unique_id):
            neighbor = self.grid.get_cell_list_contents([neighbor])[0]
            if neighbor.owner.unique_id == area2.unique_id:
                return True

        return False

    # Move armies from non attackable area to attackable neighbor based on armies:
    # "Aggressive" -> higher # of armies
    # "Passive" -> lower # of armies
    # "Neutral" -> random
    def move_armies_strategy_based(self, player, area_from):
        attackable_neighbors = []
        for neighbor in self.grid.get_neighbors(area_from.unique_id):
            neighbor = self.grid.get_cell_list_contents([neighbor])[0]
            if isinstance(neighbor, GroundArea) and neighbor.owner.unique_id != area_from.owner.unique_id:
                if not self.is_not_attackable(neighbor, player):
                    attackable_neighbors.append(neighbor)
        if len(attackable_neighbors) == 0:
            return False

        attackable_neighbors.sort(key=lambda x: x.armies, reverse=True)
        if player.strategy == "Aggressive":
            area_to = attackable_neighbors[0]
        elif player.strategy == "Neutral":
            area_to = random.choice(attackable_neighbors)
        else:
            area_to = attackable_neighbors[-1]

        area_to.armies += area_from.armies - 1
        area_from.armies = 1
        return True


    def run_model(self, n):
        for _ in range(n):
            self.step()


def get_n_armies_by_player(model, player=None):
    if player is not None:
        return sum([t.armies for t in model.get_territories_by_player(player)])
    else:
        sum_a = 0
        for player in model.players:
            sum_a += sum([t.armies for t in model.get_territories_by_player(player)])
        return sum_a / len(model.players)