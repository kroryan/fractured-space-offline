"""Persistent personal statistics; recorded inventory and experience stay intact."""
import copy
import json
import os
import threading

STATS = {'player_stats', 'player_mode_stats', 'ship_stats', 'combo_stats'}

def kind(path):
    parts = path.split('/')
    return parts[1] if len(parts) > 1 and parts[0] == 'o' else ''

def clear(value):
    if isinstance(value, list):
        for child in value:
            clear(child)
    elif isinstance(value, dict):
        for key, child in list(value.items()):
            if key.startswith('_') or key in ('page', 'mmrVersion'):
                continue
            if isinstance(child, (int, float)) and not isinstance(child, bool):
                value[key] = 0
            elif key in ('lastCompletedMatches', 'topMasteries'):
                value[key] = []
            elif key.startswith('last') and isinstance(child, str) and child.endswith('GMT'):
                value[key] = 'Mon, 01 Jan 2001 00:00:00 GMT'
            else:
                clear(child)
        value.pop('next_page', None)

class ProfileStore:
    def __init__(self, directory, identity):
        if '/' in identity or '\\' in identity or identity in ('.', '..'):
            raise ValueError('Invalid player identity')
        os.makedirs(directory, exist_ok=True)
        self.file = os.path.join(directory, identity + '.json')
        self.defaults = {}
        self.lock = threading.Lock()
        try:
            with open(self.file, encoding='utf-8-sig') as fh:
                self.saved = json.load(fh)
        except FileNotFoundError:
            self.saved = {}

    def register(self, path, body):
        category = kind(path)
        if category not in STATS and category != 'player_wallet':
            return
        value = json.loads(body)
        if category in STATS:
            clear(value)
        else:
            value['sp_games_played'] = 0
        self.defaults[path] = value

    def handle(self, method, path, body):
        with self.lock:
            key = path
            if key not in self.defaults:
                key = next((p for p in self.defaults if kind(p) == kind(path) and
                            len(p.split('/')) == len(path.split('/'))), None)
            if key not in self.defaults:
                return None
            value = copy.deepcopy(self.saved.get(key, self.defaults[key]))
            if method in ('PUT', 'PATCH'):
                patch = json.loads(body)
                if not isinstance(patch, dict) or not isinstance(value, dict):
                    raise ValueError('Invalid profile update')
                value.update({k: v for k, v in patch.items() if not k.startswith('_') and k != 'owner'})
                self.saved[key] = value
                temp = self.file + '.tmp'
                with open(temp, 'w', encoding='utf-8') as fh:
                    json.dump(self.saved, fh)
                os.replace(temp, self.file)
            return json.dumps(value).encode()

    def record_match(self, report):
        with self.lock:
            info, result = report['info'], report['result']
            ident = info.get('MatchId')
            matches = self.saved.setdefault('_matches', [])
            if not ident or ident in matches:
                return
            stats = {s['StatName']: max(0, int(s['Amount'])) for s in result.get('StatsAmount', [])}
            won = result.get('MatchResult') == 0 if 'MatchResult' in result else result.get('bDidWin', False)
            for key, template in self.defaults.items():
                if kind(key) != 'player_stats':
                    continue
                value = copy.deepcopy(self.saved.get(key, template))
                updates = {'gamesPlayed': 1, 'gamesCompleted': 1, 'gameWins': int(won)}
                for source, target in {'Deaths': 'deaths', 'Kills': 'kills', 'Captures': 'captures',
                                       'InflictedDamage': 'damageInflicted', 'DamageReceived': 'damageReceived'}.items():
                    if source in stats:
                        updates[target] = stats[source]
                for name, amount in updates.items():
                    value[name] = value.get(name, 0) + amount
                self.saved[key] = value
            matches.append(ident)
            self.saved.setdefault('_reports', {})[ident] = report
            temp = self.file + '.tmp'
            with open(temp, 'w', encoding='utf-8') as fh:
                json.dump(self.saved, fh)
            os.replace(temp, self.file)

class MatchRecorder:
    def __init__(self, path, profile, logger):
        self.path, self.profile, self.log = path, profile, logger
        self.offset = os.path.getsize(path) if os.path.exists(path) else 0
        self.pending = b''

    def poll(self):
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path, 'rb') as fh:
                if os.path.getsize(self.path) < self.offset:
                    self.offset = 0
                fh.seek(self.offset)
                self.pending += fh.read()
                self.offset = fh.tell()
            while b'\n' in self.pending:
                line, self.pending = self.pending.split(b'\n', 1)
                if line.strip():
                    self.profile.record_match(json.loads(line.decode('utf-8-sig')))
        except (ValueError, OSError, KeyError) as error:
            self.log('Match statistics: %s' % error)
