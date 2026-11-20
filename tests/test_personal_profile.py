import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'linux'))
from profile_store import ProfileStore, MatchRecorder

class PersonalProfileTests(unittest.TestCase):
    def test_fresh_persistent_isolated_results(self):
        with tempfile.TemporaryDirectory() as directory:
            path = 'o/player_stats/id'
            template = json.dumps({'kills': 100, 'deaths': 40, 'gamesPlayed': 22, 'gameWins': 11})
            first, other = ProfileStore(directory, 'first'), ProfileStore(directory, 'other')
            for profile in (first, other):
                profile.register(path, template)
                self.assertEqual(json.loads(profile.handle('GET', path, b''))['kills'], 0)
            log = Path(directory) / 'results.json'
            recorder = MatchRecorder(str(log), first, lambda message: self.fail(message))
            report = {'info': {'MatchId': 'match-1'}, 'result': {'MatchResult': 0, 'StatsAmount': [{'StatName': 'Kills', 'Amount': 4}]}}
            log.write_text(json.dumps(report) + '\n', encoding='utf-8')
            recorder.poll()
            with log.open('a', encoding='utf-8') as output:
                output.write(json.dumps(report) + '\n')
            recorder.poll()
            reloaded = ProfileStore(directory, 'first')
            reloaded.register(path, template)
            stats = json.loads(reloaded.handle('GET', path, b''))
            self.assertEqual((stats['kills'], stats['gameWins'], stats['gamesPlayed']), (4, 1, 1))
            self.assertEqual(json.loads(other.handle('GET', path, b''))['kills'], 0)

if __name__ == '__main__':
    unittest.main()
