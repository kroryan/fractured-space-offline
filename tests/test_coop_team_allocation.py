import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "linux"))
import fso_linux


class CoopTeamAllocationTests(unittest.TestCase):
    def allocate(self, party_size, host_team_size):
        admission = object.__new__(fso_linux.AdmissionServer)
        admission.party_size = party_size
        admission.host_team_size = host_team_size
        admission.session_teams = {}
        admission.pending_teams = {}
        assigned = []
        for index in range(party_size + 1):
            team = admission._reserve_team(str(index))
            if not team:
                break
            assigned.append(team)
        return assigned

    def test_every_host_team_split_for_two_to_four_players(self):
        for party_size in range(2, 5):
            for host_team_size in range(1, party_size + 1):
                with self.subTest(party_size=party_size, host_team_size=host_team_size):
                    teams = self.allocate(party_size, host_team_size)
                    self.assertEqual(len(teams), party_size - 1)
                    self.assertEqual(teams.count(1), host_team_size - 1)
                    self.assertEqual(teams.count(2), party_size - host_team_size)


if __name__ == "__main__":
    unittest.main()
