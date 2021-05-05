import requests
import time
import logging


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.StreamHandler())


class GameEnded(Exception):
    pass


class Announcer(object):
    def __init__(self):
        self.api_endpoint = 'https://127.0.0.1:2999/liveclientdata'
        self.team_map = {'ORDER': 'T1', 'CHAOS': 'T2'}

        self.processed_events = {}
        self.player = ''
        self.player_side = ''
        self.player_team = []
        self.enemy__team = []
        self.first_blood = False

        self.event_map = {
            'GameStart': self.pe_passthrough,
            'MinionsSpawning': self.pe_passthrough,
            'ChampionKill': self.pe_champ_kill,
            'Ace': self.pe_ace,
            'DragonKill': self.pe_objective_kill,
            'HeraldKill': self.pe_objective_kill,
            'BaronKill': self.pe_objective_kill,
            'TurretKilled': self.pe_structure_event,
            'InhibKilled': self.pe_structure_event,
            'InhibRespawningSoon': self.pe_structure_event,
            'InhibRespawned': self.pe_structure_event,
            'GameEnd': self.pe_passthrough
        }

    def reset(self):
        self.processed_events = {}
        self.player = ''
        self.player_side = ''
        self.player_team = []
        self.enemy__team = []
        self.first_blood = False

    def wait_for_game(self):
        logger.info("Waiting for game to start...")
        while True:
            try:
                r = requests.get(f'{self.api_endpoint}/activeplayername', verify=False)
                if r.status_code != 200:
                    logger.debug('Endpoint up. Waiting for data.')
                    time.sleep(1)
                    continue
                logger.info('Game Started.')
                return
            except requests.exceptions.ConnectionError:
                time.sleep(10)

    def load_game_metadata(self):
        self.player = requests.get(f'{self.api_endpoint}/activeplayername', verify=False).json()
        player_list = requests.get(f'{self.api_endpoint}/playerlist', verify=False).json()
        logger.debug(player_list)
        teams = {'ORDER': [], 'CHAOS': []}
        for player in player_list:
            teams[player['team']].append(player['summonerName'])
        self.player_team, self.enemy__team = (teams['ORDER'], teams['CHAOS']) if self.player in teams['ORDER'] else (teams['CHAOS'], teams['ORDER'])
        self.player_side = 'T1' if self.player in teams['ORDER'] else 'T2'
        logger.info(self.player_team)
        logger.info(self.enemy__team)

    def process_events(self):
        try:
            r = requests.get(f'{self.api_endpoint}/eventdata', verify=False)
        except requests.exceptions.ConnectionError:
            logger.info('Game ended')
            raise GameEnded
        for event in r.json()['Events']:
            if event['EventID'] not in self.processed_events:
                self.process_event(event)

    def process_event(self, event):
        logger.info(f'Processing event {event["EventID"]}')
        logger.debug(event)
        self.processed_events[event['EventID']] = True
        try:
            self.event_map.get(event['EventName'], self.no_op)(event)
        except Exception as e:
            print(e)
            pass

    def no_op(self, event):
        logger.warning(f'Unknown event detected: {event}')
        
    # Event Processors
    def pe_passthrough(self, event):
        self.announce(event['EventName'])

    def pe_structure_event(self, event):
        if not self.player_side in ''.join((event.get('TurretKilled', ''), event.get('InhibKilled', ''), event.get('Inhib', ''))):
            self.announce('ally_' + event['EventName'])
        else:
            self.announce('enemy_' + event['EventName'])

    def pe_objective_kill(self, event):
        if event.get('KillerName') in self.player_team:
            self.announce('ally_' + event['EventName'])
        else:
            self.announce('enemy_' + event['EventName'])

    def pe_ace(self, event):
        if self.player_side == self.team_map[event['AcingTeam']]:
            self.announce('ally_' + event['EventName'])
        else:
            self.announce('enemy_' + event['EventName'])

    def pe_champ_kill(self, event):
        if not self.first_blood:
            self.first_blood = True
            self.announce('first_blood')
            return
        if self.player == event['VictimName']:
            self.announce('player_death')

    # Announcer function
    def announce(self, event):
        logger.debug(f'Announcing {event}')
        pass


def run_loop():
    announcer = Announcer()
    while True:
        announcer.wait_for_game()
        announcer.load_game_metadata()
        while True:
            try:
                announcer.process_events()
                time.sleep(1)
            except GameEnded:
                break


run_loop()
