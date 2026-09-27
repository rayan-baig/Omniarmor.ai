import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from omni_armor_platform import BLOCKED, CLEARED, WARNING, OmniArmorPortal  # noqa: E402


class PortalTestCase(unittest.TestCase):
    def setUp(self):
        self.p = OmniArmorPortal(verbose=False)

    def assertLevel(self, result, level):
        self.assertEqual(result.level, level, result.message)


class TestPortal(PortalTestCase):
    def test_run_portal_covers_all_25_modules(self):
        results = self.p.run_portal()
        self.assertEqual(sorted(r.module_id for r in results), list(range(1, 26)))
        self.assertEqual(self.p.tracker.total_api_calls, 25)
        self.assertTrue(all(r.rule for r in results))

    def test_audit_log_exports_json(self):
        self.p.bank_armor_ctr_monitor(500)
        data = json.loads(self.p.export_audit_log())
        self.assertEqual(data[0]["module_id"], 18)
        self.assertEqual(data[0]["level"], CLEARED)

    def test_negative_input_rejected(self):
        with self.assertRaises(ValueError):
            self.p.fleet_armor_hos_timer(-1)

    def test_every_module_has_hex_color(self):
        for module in self.p.theme.INDUSTRIES.values():
            self.assertRegex(module["hex"], r"^#[0-9A-F]{6}$")


class TestModules(PortalTestCase):
    def test_01_fleet(self):
        self.assertLevel(self.p.fleet_armor_hos_timer(8), CLEARED)
        self.assertLevel(self.p.fleet_armor_hos_timer(10.5), WARNING)
        self.assertLevel(self.p.fleet_armor_hos_timer(11), BLOCKED)
        self.assertLevel(self.p.fleet_armor_hos_timer(11.5), BLOCKED)
        self.assertLevel(self.p.fleet_armor_hos_timer(6, on_duty_window_hours=14), BLOCKED)
        self.assertLevel(self.p.fleet_armor_hos_timer(8, driving_since_break_hours=8), BLOCKED)

    def test_02_resto(self):
        self.assertLevel(self.p.resto_armor_temp_check(38), CLEARED)
        self.assertLevel(self.p.resto_armor_temp_check(41), WARNING)
        self.assertLevel(self.p.resto_armor_temp_check(41.5), BLOCKED)

    def test_03_yacht(self):
        self.assertLevel(self.p.yacht_armor_marpol_sentry(1, False), CLEARED)
        self.assertLevel(self.p.yacht_armor_marpol_sentry(5, True), BLOCKED)
        self.assertLevel(self.p.yacht_armor_marpol_sentry(12, True), CLEARED)
        self.assertLevel(self.p.yacht_armor_marpol_sentry(5, True, "sewage_treated"), CLEARED)
        self.assertLevel(self.p.yacht_armor_marpol_sentry(200, True, "plastic"), BLOCKED)
        with self.assertRaises(ValueError):
            self.p.yacht_armor_marpol_sentry(5, True, "bilge")

    def test_04_aero(self):
        self.assertLevel(self.p.aero_armor_faa_logger(50), CLEARED)
        self.assertLevel(self.p.aero_armor_faa_logger(95), WARNING)
        self.assertLevel(self.p.aero_armor_faa_logger(100), BLOCKED)
        self.assertLevel(self.p.aero_armor_faa_logger(105, ferrying_to_inspection=True), WARNING)
        self.assertLevel(self.p.aero_armor_faa_logger(111, ferrying_to_inspection=True), BLOCKED)

    def test_05_hospital(self):
        self.assertLevel(self.p.hospital_armor_patient_gate(5, 20), CLEARED)
        self.assertLevel(self.p.hospital_armor_patient_gate(5, 25), WARNING)
        self.assertLevel(self.p.hospital_armor_patient_gate(5, 26), BLOCKED)
        self.assertLevel(self.p.hospital_armor_patient_gate(2, 5, unit="icu"), BLOCKED)
        self.assertLevel(self.p.hospital_armor_patient_gate(0, 3), BLOCKED)
        self.assertLevel(self.p.hospital_armor_patient_gate(0, 0), CLEARED)
        self.assertLevel(self.p.hospital_armor_patient_gate(2, 7, max_patients_per_nurse=4), CLEARED)
        with self.assertRaises(ValueError):
            self.p.hospital_armor_patient_gate(2, 5, unit="unknown")

    def test_06_ai(self):
        self.assertLevel(self.p.ai_armor_eu_act_monitor(0.05), CLEARED)
        self.assertLevel(self.p.ai_armor_eu_act_monitor(0.13), WARNING)
        self.assertLevel(self.p.ai_armor_eu_act_monitor(0.18), BLOCKED)
        self.assertLevel(self.p.ai_armor_eu_act_monitor(0.18, policy_threshold=0.3), CLEARED)

    def test_07_library(self):
        self.assertLevel(self.p.library_armor_cipa_filter("http://a.org", False), CLEARED)
        self.assertLevel(self.p.library_armor_cipa_filter("http://b.org", True), BLOCKED)
        self.assertLevel(self.p.library_armor_cipa_filter("http://b.org", True, adult_research_override=True), CLEARED)

    def test_08_school(self):
        self.assertLevel(self.p.school_armor_ferpa_block("school_official", True), CLEARED)
        self.assertLevel(self.p.school_armor_ferpa_block("school_official", False), BLOCKED)
        self.assertLevel(self.p.school_armor_ferpa_block("vendor"), BLOCKED)
        self.assertLevel(self.p.school_armor_ferpa_block("employer", written_consent_on_file=True), CLEARED)

    def test_09_prop(self):
        self.assertLevel(self.p.prop_armor_escrow_isolation(True), CLEARED)
        self.assertLevel(self.p.prop_armor_escrow_isolation(False), BLOCKED)

    def test_10_auto(self):
        self.assertLevel(self.p.auto_armor_ftc_sticker_check(True), CLEARED)
        self.assertLevel(self.p.auto_armor_ftc_sticker_check(False), BLOCKED)

    def test_11_luxury(self):
        self.assertLevel(self.p.luxury_armor_cites_gate(False, False), CLEARED)
        self.assertLevel(self.p.luxury_armor_cites_gate(True, True), CLEARED)
        self.assertLevel(self.p.luxury_armor_cites_gate(True, False), BLOCKED)

    def test_12_agri(self):
        self.assertLevel(self.p.agri_armor_withholding_clock(4, 7), BLOCKED)
        self.assertLevel(self.p.agri_armor_withholding_clock(7, 7), CLEARED)

    def test_13_cop(self):
        self.assertLevel(self.p.cop_armor_evidence_timer(100), CLEARED)
        self.assertLevel(self.p.cop_armor_evidence_timer(170), WARNING)
        self.assertLevel(self.p.cop_armor_evidence_timer(280), BLOCKED)
        self.assertLevel(self.p.cop_armor_evidence_timer(280, max_days=365), CLEARED)

    def test_14_fire(self):
        self.assertLevel(self.p.fire_armor_scba_verification(True), CLEARED)
        self.assertLevel(self.p.fire_armor_scba_verification(True, cylinder_pressure_pct=95), CLEARED)
        self.assertLevel(self.p.fire_armor_scba_verification(True, cylinder_pressure_pct=85), BLOCKED)
        self.assertLevel(self.p.fire_armor_scba_verification(False), BLOCKED)

    def test_15_park(self):
        self.assertLevel(self.p.park_armor_ride_clearance(True), CLEARED)
        self.assertLevel(self.p.park_armor_ride_clearance(False), BLOCKED)

    def test_16_jail(self):
        self.assertLevel(self.p.jail_armor_wellness_timer(18), CLEARED)
        self.assertLevel(self.p.jail_armor_wellness_timer(25), WARNING)
        self.assertLevel(self.p.jail_armor_wellness_timer(31), BLOCKED)
        self.assertLevel(self.p.jail_armor_wellness_timer(18, max_interval_minutes=15), BLOCKED)

    def test_17_insure(self):
        self.assertLevel(self.p.insure_armor_tcpa_filter(True), BLOCKED)
        self.assertLevel(self.p.insure_armor_tcpa_filter(False), BLOCKED)
        self.assertLevel(self.p.insure_armor_tcpa_filter(False, autodialed_or_prerecorded=False), CLEARED)
        self.assertLevel(self.p.insure_armor_tcpa_filter(True, prior_express_written_consent=True), CLEARED)
        self.assertLevel(self.p.insure_armor_tcpa_filter(True, established_business_relationship=True,
                                                         autodialed_or_prerecorded=False), CLEARED)
        self.assertLevel(self.p.insure_armor_tcpa_filter(False, prior_express_written_consent=True, local_hour=21), BLOCKED)

    def test_18_bank(self):
        self.assertLevel(self.p.bank_armor_ctr_monitor(5000), CLEARED)
        self.assertLevel(self.p.bank_armor_ctr_monitor(9500), WARNING)
        self.assertLevel(self.p.bank_armor_ctr_monitor(10000), WARNING)
        result = self.p.bank_armor_ctr_monitor(10000.01)
        self.assertLevel(result, WARNING)
        self.assertEqual(result.status, "CTR FILING REQUIRED")

    def test_19_fintech(self):
        self.assertLevel(self.p.fintech_armor_adv_countdown(30), CLEARED)
        self.assertLevel(self.p.fintech_armor_adv_countdown(80), WARNING)
        self.assertLevel(self.p.fintech_armor_adv_countdown(90), WARNING)
        self.assertLevel(self.p.fintech_armor_adv_countdown(95), BLOCKED)

    def test_20_petro(self):
        self.assertLevel(self.p.petro_armor_valve_sentry(6), CLEARED)
        self.assertLevel(self.p.petro_armor_valve_sentry(14), WARNING)
        self.assertLevel(self.p.petro_armor_valve_sentry(6, inspected_this_calendar_year=False), WARNING)
        self.assertLevel(self.p.petro_armor_valve_sentry(15), WARNING)
        self.assertLevel(self.p.petro_armor_valve_sentry(16), BLOCKED)

    def test_21_factory(self):
        self.assertLevel(self.p.factory_armor_loto_gate(True), CLEARED)
        self.assertLevel(self.p.factory_armor_loto_gate(False), BLOCKED)
        self.assertLevel(self.p.factory_armor_loto_gate(True, every_worker_lock_applied=False), BLOCKED)

    def test_22_pharma(self):
        self.assertLevel(self.p.pharma_armor_cfr_signature(True), CLEARED)
        result = self.p.pharma_armor_cfr_signature(False, meaning_shown=False)
        self.assertLevel(result, BLOCKED)
        self.assertIn("printed name", result.message)
        self.assertIn("meaning", result.message)

    def test_23_mine(self):
        self.assertLevel(self.p.mine_armor_part46_gate(2), BLOCKED)
        self.assertLevel(self.p.mine_armor_part46_gate(8, days_on_job=30), WARNING)
        self.assertLevel(self.p.mine_armor_part46_gate(8, days_on_job=90), BLOCKED)
        self.assertLevel(self.p.mine_armor_part46_gate(24, days_on_job=120), CLEARED)

    def test_24_port(self):
        self.assertLevel(self.p.port_armor_twic_check(True), CLEARED)
        self.assertLevel(self.p.port_armor_twic_check(False, escorted=True), CLEARED)
        self.assertLevel(self.p.port_armor_twic_check(False), BLOCKED)

    def test_25_gene(self):
        self.assertLevel(self.p.gene_armor_nih_monitor(False), BLOCKED)
        self.assertLevel(self.p.gene_armor_nih_monitor(True), CLEARED)
        self.assertLevel(self.p.gene_armor_nih_monitor(False, "III-E"), WARNING)
        self.assertLevel(self.p.gene_armor_nih_monitor(True, "III-E"), CLEARED)
        self.assertLevel(self.p.gene_armor_nih_monitor(False, "III-F"), CLEARED)
        self.assertLevel(self.p.gene_armor_nih_monitor(True, "III-B"), WARNING)
        with self.assertRaises(ValueError):
            self.p.gene_armor_nih_monitor(True, "IV")


if __name__ == "__main__":
    unittest.main()
