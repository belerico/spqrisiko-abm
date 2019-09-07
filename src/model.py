import os
import math
import json
import networkx as nx
import random
import collections, itertools

from . import constants, strategies
from .markov import get_probabilities_ground_combact, get_probabilities_combact_by_sea
from .territory import GroundArea, SeaArea
from .player import Player
from . import markov

from operator import itemgetter
from functools import cmp_to_key

from mesa import Agent, Model
from mesa.time import RandomActivation
from mesa.datacollection import DataCollector
from mesa.space import NetworkGrid


class SPQRisiko(Model):
    """A SPQRisiko model with some number of players"""

    def __init__(self, n_players, points_limit, strategy, goal):
        super().__init__()
        self.players_goals = ["BE", "LA", "PP"]  # Definition of acronyms on `strategies.py`
        self.current_turn = 0
        self.journal = []  # Keep track of main events
        self.reinforces_by_goal = {}
        self.tris_by_goal = {}
        # How many agent players wiil be
        self.n_players = n_players if n_players <= constants.MAX_PLAYERS else constants.MAX_PLAYERS
        # How many computer players will be
        self.n_computers = constants.MAX_PLAYERS - n_players
        # Creation of player, goals and computer agents
        goals = []
        if goal == "Random":
            for player in range(n_players):
                goals.append(self.random.choice(self.players_goals))
        else:
            goals = [goal for i in range(self.n_players)]

        self.players = [Player(i, computer=False, strategy=self.get_strategy_setup(strategy),
                               goal=goals[i], model=self)
                        for i in range(self.n_players)]
        for player in self.players:
            self.log("{} follows {} goal with a {} strategy".format(player.color, player.goal, player.strategy))
        self.computers = [
            Player(i, computer=True, strategy="Neutral", goal=self.random.choice(self.players_goals), model=self)
            for i in range(self.n_players, self.n_players + self.n_computers)]
        self.points_limit = points_limit  # limit at which one player wins
        self.deck = self.create_deck()
        self.random.shuffle(self.deck)
        self.trashed_cards = []
        self.precompute_tris_reinforces_by_goal()
        # Initialize map
        self.G, self.territories_dict = self.create_graph_map()
        self.grid = NetworkGrid(self.G)
        self.datacollector = DataCollector(model_reporters={
                                              "Armies": SPQRisiko.get_n_armies_by_player,
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
                t.armies = 2
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

        self.ground_areas.sort(key=lambda x: x.unique_id)
        self.sea_areas.sort(key=lambda x: x.unique_id)

        self.running = True
        self.datacollector.collect(self)

    def get_strategy_setup(self, strategy):
        strats = ["Aggressive", "Passive", "Neutral"]
        if strategy == "Random":
            strategy = self.random.choice(strats)
        return strategy

    @staticmethod
    def get_movable_armies_by_strategy(strategy, minimum, maximum):
        nomads_percentage = {
            "Passive": 0,
            "Neutral": 0.4,
            "Aggressive": 0.8
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
        # Tris must be composed of three different cards or three of the same type
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

    def precompute_tris_reinforces_by_goal(self):
        # precompute tris and assign points based on strategy
        all_possible_tris = [list(t) for t in itertools.combinations(self.deck, 3)]
        all_reinforces = [SPQRisiko.reinforces_from_tris(tris) for tris in all_possible_tris]
        # Remove None from list
        real_tris = [all_possible_tris[i] for i in range(len(all_reinforces)) if all_reinforces[i]]
        all_reinforces = [i for i in all_reinforces if i]
        named_tris = {}
        for i, tris in enumerate(real_tris):
            name = self.get_tris_name(tris)
            named_tris[name] = all_reinforces[i]
            self.reinforces_by_goal[name] = {}
            for goal, value in strategies.strategies.items():
                self.reinforces_by_goal[name][goal] = self.get_reinforcements_score(all_reinforces[i], value["tris"])

        # order tris name by score
        for goal, value in strategies.strategies.items():
            self.tris_by_goal[goal] = []
            for tris in real_tris:
                name = self.get_tris_name(tris)
                if name not in self.tris_by_goal[goal]:
                    self.tris_by_goal[goal].append(name)
            self.tris_by_goal[goal] = sorted(self.tris_by_goal[goal], key=cmp_to_key(lambda a, b: self.reinforces_by_goal[b][goal] - self.reinforces_by_goal[a][goal]))

        self.reinforces_by_goal["average"] = {}
        for goal, value in strategies.strategies.items():
            sum, count = 0, 0
            for tris in real_tris:
                count += 1
                sum += self.reinforces_by_goal[self.get_tris_name(tris)][goal]
            self.reinforces_by_goal["average"][goal] = float(sum) / count

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

    def get_weakest_power_place(self, player):
        weakest = None
        for territory in self.ground_areas:
            if not territory.owner.computer and territory.owner.unique_id == player.unique_id:
                if territory.power_place:
                    if not weakest or territory.armies < weakest.armies:
                        weakest = territory
        return weakest

    def get_weakest_adversary_power_place(self, player):
        weakest = None
        for territory in self.ground_areas:
            if territory.owner.computer or territory.owner.unique_id != player.unique_id:
                if territory.power_place:
                    if not weakest or territory.armies < weakest.armies:
                        weakest = territory
        return weakest

    def find_nearest(self, territory, player):
        # It's a BFS visit to get the node whose distance from territory is the lesser than any other
        for ground_area in self.ground_areas:
            ground_area.found = 0
        for sea_area in self.sea_areas:
            sea_area.found = 0

        territory.found = 1
        visited = [territory]
        distances = [0] * 57

        while len(visited) > 0:
            t = visited.pop(0)
            if distances[t.unique_id] > 4:
                break
            for neighbor in self.grid.get_neighbors(t.unique_id):
                neighbor = self.grid.get_cell_list_contents([neighbor])[0]
                if neighbor.found == 0:
                    neighbor.found = 1
                    distances[neighbor.unique_id] = distances[t.unique_id] + 1
                    visited.append(neighbor)
                    if neighbor.type == "ground" and neighbor.owner.unique_id == player.unique_id:
                        return neighbor

        return None

    def get_largest_empire(self, player):
        # It's another DFS visit in which we account for the membership of a node to a connected component
        def __dfs_visit__(territory, ground_areas, cc_num):
                territory.found = 1
                ground_areas[territory.unique_id] = cc_num
                for neighbor in self.grid.get_neighbors(territory.unique_id):
                    neighbor = self.grid.get_cell_list_contents([neighbor])[0]
                    if  neighbor.type == "ground" and \
                        neighbor.found == 0 and \
                        neighbor.owner.unique_id == player.unique_id:
                        
                        __dfs_visit__(neighbor, ground_areas, cc_num)

        cc_num = 0
        ground_areas = [-1] * 45

        for territory in self.ground_areas:
            territory.found = 0

        for territory in self.ground_areas:
            if territory.type == "ground" and territory.found == 0 and territory.owner.unique_id == player.unique_id:
                __dfs_visit__(territory, ground_areas, cc_num)
                cc_num += 1
        
        stats = list(collections.Counter([t for t in ground_areas if t != -1]).most_common())
        if stats != []:
            return [self.ground_areas[idx] for idx, cc in enumerate(ground_areas) if cc == stats[0][0]]
        return stats

    def maximum_empires(self):
        # It's a DFS visit in which we account for
        # the length of every connected components
        def __dfs_visit__(territory, d):
            territory.found = 1
            for neighbor in self.grid.get_neighbors(territory.unique_id):
                neighbor = self.grid.get_cell_list_contents([neighbor])[0]
                if  neighbor.type == "ground" and \
                    neighbor.found == 0 and \
                    neighbor.owner.unique_id == territory.owner.unique_id:
                    
                    d = __dfs_visit__(neighbor, d)
            return d + 1
        
        cc_lengths = [0] * self.n_players

        for territory in self.ground_areas:
            territory.found = 0

        for territory in self.ground_areas:
            if not territory.owner.computer and territory.found == 0:
                distance = __dfs_visit__(territory, 0)
                if distance > cc_lengths[territory.owner.unique_id]:
                    cc_lengths[territory.owner.unique_id] = distance
        
        return cc_lengths

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
                self.atta_wins_combact_by_sea, _, _ = get_probabilities_combact_by_sea(attacker_armies, defender_armies)
            elif attacker_armies > self.atta_wins_combact_by_sea.shape[0]:
                self.atta_wins_combact_by_sea, _, _ = get_probabilities_combact_by_sea(attacker_armies, self.atta_wins_combact_by_sea.shape[1])
            elif defender_armies > self.atta_wins_combact_by_sea.shape[1]:
                self.atta_wins_combact_by_sea, _, _ = get_probabilities_combact_by_sea(self.atta_wins_combact_by_sea.shape[0], defender_armies)

    def step(self):
        self.current_turn += 1
        for player in self.players:

            can_draw = False
            territories, power_places = self.count_players_territories_power_places()
            player_territories = self.get_territories_by_player(player, "ground")
            sea_areas = self.count_players_sea_areas()
            empires = self.maximum_empires()

            # 1) Aggiornamento del punteggio
            player.update_victory_points(empires, territories, sea_areas, power_places)

            # 1.1) Controllo vittoria
            if self.winner(player):
                self.running = False
                self.log("{} has won!".format(player.color))
                return True

            # 2) Fase dei rinforzi
            print('\n\nREINFORCES')
            player.update_ground_reinforces_power_places()
            reinforces = Player.get_ground_reinforces(player_territories)
            self.log("{} earns {} legionaries (he owns {} territories)".format(player.color, reinforces, territories[player.unique_id]))
            player.put_reinforces(self, reinforces)
            # player.sacrifice_trireme(sea_area_from, ground_area_to)

            # use card combination
            # displace ground, naval and/or power places on the ground
            tris = player.get_best_tris(self)

            if tris:
                reinforces = player.play_tris(self, tris)
                self.log("{} play tris {}".format(player.color, self.get_tris_name(tris)))
                player.put_reinforces(self, reinforces)
                # TODO: log where reinforces are put

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
                    if  player.unique_id != adv_min_trireme and \
                        self.atta_wins_combact[sea_area.trireme[player.unique_id], sea_area.trireme[adv_min_trireme]] >= strategies.probs_win[player.strategy]:
                        
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
                player.naval_combact(
                    sea_area, 
                    adv, 
                    attacker_trireme, 
                    strategies.probs_win[player.strategy],
                    self.atta_wins_combact
                )

            # 5) Attacchi via mare
            print('\n\nCOMBACT BY SEA!!')
            
            for ground_area in self.ground_areas:
                ground_area.already_attacked_by_sea = False

            attacks = self.get_attackable_ground_areas_by_sea(player)
            attacks.sort(key=lambda x: x["prob_win"], reverse=True)

            while 0 < len(attacks):
                attack = attacks[0]
                # if not attack['defender'].already_attacked_by_sea:
                attack['defender'].already_attacked_by_sea = True
                attacker_armies = attack["attacker"].armies - attack["armies_to_leave"]            
                print('Battle: {} (player {}) with {} VS {} (player {}) with {}'.format(
                        attack["attacker"].name, player.unique_id, attacker_armies,
                        attack["defender"].name, attack["defender"].owner.unique_id, attack["defender"].armies
                ))
                conquered, min_moveable_armies = player.combact_by_sea(
                                                    attack["attacker"], 
                                                    attack["defender"], 
                                                    attacker_armies
                                                 )
                if conquered:
                    # Move armies from attacker area to conquered
                    max_moveable_armies = attack["attacker"].armies - attack["armies_to_leave"]
                    nomads = SPQRisiko.get_movable_armies_by_strategy(player.strategy, min_moveable_armies, max_moveable_armies)
                    attack["attacker"].armies -= nomads
                    attack["defender"].armies = nomads
                    can_draw = True
                # Remove from possible attacks all of those containing as defender the conquered territory
                # and update the probability
                attacks = self.update_attacks_by_sea(player, attacks)


            # 6) Attacchi terrestri
            print('\n\nGROUND COMBACT!!')
            
            attacks = []
            attacks = self.get_attackable_ground_areas(player)
            # attacks.sort(key=lambda x: x["prob_win"], reverse=True)

            while 0 < len(attacks):
                attack = attacks[0]
                attacker_armies = attack["attacker"].armies - 1                
                print('Battle: {} (player {}) with {} VS {} (player {}) with {}'.format(
                        attack["attacker"].name, player.unique_id, attacker_armies,
                        attack["defender"].name, attack["defender"].owner.unique_id, attack["defender"].armies
                ))
                conquered, min_moveable_armies = player.combact(
                                                        attack["attacker"], 
                                                        attack["defender"], 
                                                        attacker_armies, 
                                                        strategies.probs_win[player.strategy],
                                                        self.atta_wins_combact
                                                 )
                if conquered:
                    # Move armies from attacker area to conquered
                    max_moveable_armies = attack["attacker"].armies - 1
                    nomads = SPQRisiko.get_movable_armies_by_strategy(player.strategy, min_moveable_armies, max_moveable_armies)
                    attack["attacker"].armies -= nomads
                    attack["defender"].armies = nomads
                    can_draw = True
                    self.log("{} conquered {} from {} and it moves {} armies there out of {}".format(
                        player.color, attack["defender"].name, attack["attacker"].name, nomads, max_moveable_armies))
                # Re-sort newly attackable areas with newer probabilities
                attacks = self.get_attackable_ground_areas(player)
                # attacks.sort(key=lambda x: x["prob_win"], reverse=True)
            
            # Controllo se qualche giocatore è stato eliminato
            for adv in self.players:
                if adv.unique_id != player.unique_id:
                    territories = self.get_territories_by_player(adv)
                    if territories == []:
                        self.log("{} has been eliminated by {}".format(adv.color, player.color))
                        player.cards.append(adv.cards)
                        for sea_area in self.get_territories_by_player(adv, ground_type="sea"):
                            sea_area.trireme = 0

            # 7) Spostamento strategico di fine turno
            player.move_armies_by_goal(self)

            # 8) Presa della carta
            # Il giocatore può dimenticarsi di pescare la carta ahah sarebbe bello fare i giocatori smemorati
            if can_draw and random.random() <= 1:
                card = self.draw_a_card()
                if card:
                    player.cards.append(card)
            else: 
                print('Fuck it: I forgot to draw the card!')
            can_draw = False

        self.schedule.step()
        self.datacollector.collect(self)
        return False

    def update_attacks_by_sea(self, player, future_attacks):
        attack_num = 0
        last_attacker = future_attacks[0]['attacker']
        del future_attacks[0]
        while attack_num < len(future_attacks):
            attack = future_attacks[attack_num]
            if attack['defender'].owner.unique_id == last_attacker.owner.unique_id:
                print('Since the defender has been conquered, I delete it')
                del future_attacks[attack_num]
            elif attack['defender'].already_attacked_by_sea:
                print('Since the defender has already been attacked by sea, I delete it')
                del future_attacks[attack_num]
            elif attack['attacker'].unique_id == last_attacker.unique_id:
                print('The attacker may attack again')
                # Maybe it could change the armies to leave due to garrisons
                armies_to_leave = self.get_armies_to_leave(attack['attacker'])
                if attack['attacker'].armies - armies_to_leave >= min(3, attack['defender'].armies):
                    prob_win = self.atta_wins_combact_by_sea[attack['attacker'].armies - armies_to_leave - 1, attack['defender'].armies - 1]
                    if prob_win >= strategies.probs_win[player.strategy]:
                        print('The attacker can attack again')
                        attack['prob_win'] = prob_win
                        attack_num += 1
                    else:
                        print('Since the attacker has a lower prob to win, I delete it')
                        del future_attacks[attack_num]
                else:
                    print('Since the attacker hasn\'t the min required armies, I delete it')
                    del future_attacks[attack_num]
            else:
                attack_num += 1    
        future_attacks.sort(key=lambda x: x["prob_win"], reverse=True)

        return future_attacks
                
    def get_attackable_ground_areas_by_sea(self, player):
        attacks = []
        for ground_area in self.get_territories_by_player(player):
            for neighbor in self.grid.get_neighbors(ground_area.unique_id):
                neighbor = self.grid.get_cell_list_contents([neighbor])[0]
                # A player can attack a ground area through sea, only if it posesses a number of
                # trireme greater than the possible adversary. 
                if isinstance(neighbor, SeaArea) and neighbor.trireme[player.unique_id] > min(neighbor.trireme):
                    for sea_area_neighbor in self.grid.get_neighbors(neighbor.unique_id):
                        sea_area_neighbor = self.grid.get_cell_list_contents([sea_area_neighbor])[0]
                        if isinstance(sea_area_neighbor, GroundArea) and \
                            ground_area.unique_id != sea_area_neighbor.unique_id and \
                            sea_area_neighbor.owner.unique_id != player.unique_id and \
                            (sea_area_neighbor.owner.computer or neighbor.trireme[player.unique_id] > neighbor.trireme[sea_area_neighbor.owner.unique_id]):
                            
                            armies_to_leave = self.get_armies_to_leave(ground_area)
                            if ground_area.armies - armies_to_leave >= min(3, sea_area_neighbor.armies):
                                self.update_atta_wins_combact_matrix(ground_area.armies - armies_to_leave, sea_area_neighbor.armies, mat_type='combact_by_sea')
                                prob_win = self.atta_wins_combact_by_sea[ground_area.armies - armies_to_leave - 1, sea_area_neighbor.armies - 1]
                                if prob_win >= strategies.probs_win[player.strategy]:
                                    attacks.append({
                                        "defender": sea_area_neighbor,
                                        "attacker": ground_area,
                                        "armies_to_leave": armies_to_leave,
                                        "prob_win": prob_win
                                    })
        return attacks

    def get_armies_to_leave(self, ground_area):
        ground_area_neighbors = self.grid.get_neighbors(ground_area.unique_id)
        for ground_area_neighbor in ground_area_neighbors:
            ground_area_neighbor = self.grid.get_cell_list_contents([ground_area_neighbor])[0]
            if  isinstance(ground_area_neighbor, GroundArea) and \
                ground_area_neighbor.owner.unique_id != ground_area.owner.unique_id:
                
                return 2
        
        return 1
    
    def get_attackable_ground_areas_from(self, ground_area):
        attacks = []
        if ground_area.armies > 1:
            for neighbor in self.grid.get_neighbors(ground_area.unique_id):
                neighbor = self.grid.get_cell_list_contents([neighbor])[0]
                if neighbor.type == "ground" and \
                    neighbor.owner.unique_id != ground_area.owner.unique_id and \
                    ground_area.armies - 1 >= min(3, neighbor.armies):
                    
                    self.update_atta_wins_combact_matrix(ground_area.armies - 1, neighbor.armies)
                    prob_win = self.atta_wins_combact[ground_area.armies - 2, neighbor.armies - 1]
                    if prob_win >= strategies.probs_win[ground_area.owner.strategy]:
                        attacks.append({
                            "defender": neighbor,
                            "attacker": ground_area,
                            "prob_win": prob_win
                        })
        return attacks
    
    def get_attackable_ground_areas(self, player):
        attacks = []
        for ground_area in self.get_territories_by_player(player):
            attackables = self.get_attackable_ground_areas_from(ground_area)
            if attackables != []:
                for attackable in attackables:
                    attacks.append(attackable)
        if player.goal == "PP":
            attacks.sort(key=lambda x: (x['defender'].power_place, x['prob_win']), reverse=True)
        else: 
            attacks.sort(key=lambda x: x['prob_win'], reverse=True)
        return attacks

    # Get non attackable areas wiht at least 2 armies and with an ally neighbor
    def non_attackable_areas(self, player, territories=None):
        non_attackables = []
        if not territories:
            territories = self.get_territories_by_player(player)
        for ground_area in territories:
            if ground_area.armies > 1:
                attackable, has_ally_neighbor = False, False
                for neighbor in self.grid.get_neighbors(ground_area.unique_id):
                    neighbor = self.grid.get_cell_list_contents([neighbor])[0]
                    if neighbor.type == "ground" and neighbor.owner.unique_id != player.unique_id:
                        attackable = True
                        break
                    has_ally_neighbor = True

                if not attackable and has_ally_neighbor:
                    non_attackables.append(ground_area)

        return non_attackables

    def is_not_attackable(self, area):
        for neighbor in self.grid.get_neighbors(area.unique_id):
            neighbor = self.grid.get_cell_list_contents([neighbor])[0]
            if isinstance(neighbor, GroundArea) and neighbor.owner.unique_id != area.owner.unique_id:
                return False
        return True

    def get_strongest_ally_neighbor(self, area):
        strongest = None
        for neighbor in self.grid.get_neighbors(area.unique_id):
            neighbor = self.grid.get_cell_list_contents([neighbor])[0]
            if isinstance(neighbor, GroundArea) and (not strongest or strongest.armies < neighbor.armies):
                strongest = neighbor
        return strongest

    def is_neighbor_of(self, area1, area2):
        for neighbor in self.grid.get_neighbors(area1.unique_id):
            neighbor = self.grid.get_cell_list_contents([neighbor])[0]
            if neighbor.owner.unique_id == area2.unique_id:
                return True

        return False

    def log(self, log):
        self.journal.append("Turn {}: ".format(self.current_turn) + log)

    def run_model(self, n):
        for _ in range(n):
            self.step()

    # Tris name is the ordered initial letters of cards type
    def get_tris_name(self, tris):
        if len(tris) != 3:
            raise Exception("tris name parameter error")
        return "-".join([card[0] for card in sorted(set([card["type"] for card in tris]))])

    def get_reinforcements_score(self, reinforces, multipliers):
        m, r = multipliers, reinforces
        return m[0]*r["legionaries"] + m[1]*r["triremes"] + m[2]*r["centers"]

    def get_n_armies_by_player(self, player=None):
        if player is not None:
            return sum([t.armies for t in self.get_territories_by_player(player)])
        else:
            sum_a = 0
            for player in self.players:
                sum_a += sum([t.armies for t in self.get_territories_by_player(player)])
            return sum_a / len(self.players)