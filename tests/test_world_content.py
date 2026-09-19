"""Local scenarios for authored cross-domain lifecycles, not reachability proofs."""
import unittest

from game.world import _apply, _eligible, load_catalog, new_world


class WorldContentLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.events = {event["id"]: event for event in load_catalog()["events"]}
        self.state = new_world(0, 1)

    def perform(self, event_id, year):
        event = self.events[event_id]
        self.assertTrue(_eligible(self.state, event, year), event_id)
        _apply(self.state, event["effects"])
        self.state["history"].append({"event_id": event_id, "year": year})

    def test_second_algorithm_incident_can_be_audited_and_repaired_again(self):
        self.state["flags"]["automation_services_alive"] = True
        for year in (3, 23):
            self.perform("technology.algorithm_incident", year)
            self.assertFalse(self.state["flags"]["automation_services_alive"])
            self.assertFalse(_eligible(self.state, self.events["technology.audited_restart"], year + 2))
            self.perform("rights.algorithm_appeals", year + 2)
            self.perform("technology.audited_restart", year + 4)
            self.assertTrue(self.state["flags"]["automation_services_alive"])
            self.assertFalse(self.state["flags"]["algorithm_incident_active"])

    def test_orbital_failure_blocks_forecasts_until_repair_and_reconnection(self):
        self.state["flags"].update(orbital_station_alive=True, orbital_station_ever_built=True,
                                   shared_alerts_ready=True)
        self.state["metrics"].update(technology=80, energy_security=75, institutional_capacity=70)
        self.perform("space.orbital_service_failure", 3)
        self.assertFalse(self.state["flags"]["orbital_station_alive"])
        self.assertFalse(self.state["flags"]["shared_alerts_ready"])
        self.assertFalse(_eligible(self.state, self.events["climate.shared_forecasts"], 5))
        self.perform("space.orbital_service_rebuild", 5)
        self.assertFalse(self.state["flags"]["shared_alerts_ready"])
        self.perform("climate.shared_forecasts", 7)
        self.assertTrue(self.state["flags"]["shared_alerts_ready"])

    def test_outpost_construction_reserves_energy_before_withdrawal_risk(self):
        self.state["flags"].update(closed_loop_tested=True, orbital_station_alive=True,
                                   advanced_energy_verified=True, advanced_energy_site_alive=True)
        self.state["metrics"].update(technology=90, energy_security=80, food_security=80,
                                     prosperity=80, international_tension=30)
        self.perform("space.research_outpost", 3)
        self.assertFalse(_eligible(self.state, self.events["space.outpost_withdrawal"], 5))
        self.state["metrics"]["energy_security"] = 60
        self.perform("space.outpost_withdrawal", 7)
        self.assertFalse(self.state["flags"]["research_outpost_alive"])


if __name__ == "__main__":
    unittest.main()
