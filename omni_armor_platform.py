# -*- coding: utf-8 -*-
"""
OmniArmor.ai - 25-Industry Compliance Gatekeeper Platform

Every module check returns a ComplianceResult with one of three levels:
    CLEARED - within the rule
    WARNING - action needed soon, or a filing is required
    BLOCKED - the rule is broken; stop until it is fixed

Each result cites the rule it applies. Thresholds that come from company or
agency policy rather than law are parameters, and the message says so.
This is decision support, not legal advice: confirm each rule for your
jurisdiction and operation before relying on it.

Two layers of checks:
    - 25 detailed checks, one per industry (the *_armor_* methods below)
    - the rule catalog in omni_armor_rules: the ten costliest compliance
      risks per industry, 250 in all, run with check_rule / run_industry
"""

import datetime
import json
from dataclasses import dataclass, asdict

from omni_armor_rules import CATALOG, get_rule, evaluate
from omni_armor_rules.rule import BLOCKED, CLEARED, LEVELS, WARNING

SLOGAN = "Catch the fine before it catches you."


# =====================================================================
# 🌌 THE MEGAPOLIS THEME MATRIX: MOONSTONE LAVENDER GREY CORE
# =====================================================================
class MoonstoneThemeColors:
    BASE_THEME = "Moonstone Lavender Grey (#E6E6FA)"
    BRAND_PRIMARY = "Moonstone Silver-Violet (#B9B5CF)"
    LEVEL_COLORS = {CLEARED: "#2E7D32", WARNING: "#EF6C00", BLOCKED: "#C62828"}

    INDUSTRIES = {
        1:  {"name": "FleetArmor (Logistics)", "color": "Safety Neon Orange", "hex": "#FF5F1F"},
        2:  {"name": "RestoArmor (Restaurants)", "color": "Vibrant Tomato Red", "hex": "#FF6347"},
        3:  {"name": "YachtArmor (Superyachts)", "color": "Tropical Mint Teal", "hex": "#00F5D4"},
        4:  {"name": "AeroArmor (Aviation)", "color": "High-Altitude Electric Blue", "hex": "#00D2FF"},
        5:  {"name": "HospitalArmor (Hospitals)", "color": "Medical Neon Green", "hex": "#39FF14"},
        6:  {"name": "AIArmor (AI Platforms)", "color": "Glowing Cyber Purple", "hex": "#9D4EDD"},
        7:  {"name": "LibraryArmor (Libraries)", "color": "Vintage Amber Yellow", "hex": "#FFB703"},
        8:  {"name": "SchoolArmor (Schools)", "color": "Schoolhouse Crimson Gold", "hex": "#D4AF37"},
        9:  {"name": "PropArmor (Real Estate)", "color": "Luxury Copper Bronze", "hex": "#CD7F32"},
        10: {"name": "AutoArmor (Dealerships)", "color": "Racing Nitrous Yellow", "hex": "#FFEA00"},
        11: {"name": "LuxuryArmor (Luxury Brands)", "color": "Velvet Royal Magenta", "hex": "#CA0060"},
        12: {"name": "AgriArmor (Agriculture)", "color": "Harvest Emerald Olive", "hex": "#4B6043"},
        13: {"name": "CopArmor (Police Compliance)", "color": "Patrol Precinct Navy Blue", "hex": "#0A1128"},
        14: {"name": "FireArmor (Fire Departments)", "color": "Blazing Firehouse Red", "hex": "#D00000"},
        15: {"name": "ParkArmor (Amusement Parks)", "color": "Coaster Electric Lime", "hex": "#CCFF00"},
        16: {"name": "JailArmor (Prison Compliance)", "color": "Iron Vault Charcoal Grey", "hex": "#343A40"},
        # Was #E5E5E5, which vanished against the lavender base.
        17: {"name": "InsureArmor (Insurance)", "color": "Premium Gold Platinum", "hex": "#CFB53B"},
        18: {"name": "BankArmor (Banking Compliance)", "color": "Wall Street Emerald Jade", "hex": "#004B23"},
        # Was #E2EAFC, which vanished against the lavender base.
        19: {"name": "FintechArmor (Finance Compliance)", "color": "High-Frequency Silver Blue", "hex": "#78909C"},
        20: {"name": "PetroArmor (Oil & Gas Production)", "color": "Industrial Crude Gold", "hex": "#FF9F1C"},
        21: {"name": "FactoryArmor (Manufacturing)", "color": "Assembly Line Steel Grey-Blue", "hex": "#4A5759"},
        22: {"name": "PharmaArmor (Pharmaceuticals)", "color": "Bio-Hazard Warning Coral", "hex": "#FF70A6"},
        23: {"name": "MineArmor (Mining & Minerals)", "color": "Blasting Orange-Yellow", "hex": "#FF5A5F"},
        24: {"name": "PortArmor (Port Authorities)", "color": "Oceanic Deep Harbor Blue", "hex": "#03045E"},
        25: {"name": "GeneArmor (Biotech & Genetics)", "color": "Glowing Cyber Lab Ultraviolet", "hex": "#7209B7"},
        # Expansion industries 26-50: rule catalog only, no detailed check yet.
        26: {"name": "SeniorArmor (Nursing Homes & Assisted Living)", "color": "Heirloom Rose", "hex": "#C4577A"},
        27: {"name": "DentalArmor (Dental & Medical Practices)", "color": "Enamel Aqua", "hex": "#2BB3C0"},
        28: {"name": "PharmacyArmor (Pharmacies)", "color": "Apothecary Green", "hex": "#2F9E6E"},
        29: {"name": "BuildArmor (Construction)", "color": "Hi-Vis Hardhat Yellow", "hex": "#F5B700"},
        30: {"name": "HRArmor (Employers & HR)", "color": "Payroll Indigo", "hex": "#3F51B5"},
        31: {"name": "PrivacyArmor (Data Privacy & SaaS)", "color": "Encrypted Slate Violet", "hex": "#6C5B9E"},
        32: {"name": "PayArmor (Payments & Merchants)", "color": "Terminal Teal", "hex": "#008C8C"},
        33: {"name": "CryptoArmor (Crypto & Money Services)", "color": "Block Orange", "hex": "#F7931A"},
        34: {"name": "MortgageArmor (Mortgage Lending)", "color": "Deed Blue", "hex": "#1E5AA8"},
        35: {"name": "CollectArmor (Debt Collection)", "color": "Notice Burgundy", "hex": "#8C2F39"},
        36: {"name": "DefenseArmor (Defense Contractors)", "color": "Field Olive Drab", "hex": "#5B6B2E"},
        37: {"name": "FoodArmor (Food Manufacturing)", "color": "Harvest Wheat", "hex": "#D9A441"},
        38: {"name": "DeviceArmor (Medical Devices)", "color": "Sterile Steel Blue", "hex": "#4F7CAC"},
        39: {"name": "ChemArmor (Chemical Plants)", "color": "Reagent Chartreuse", "hex": "#9BC53D"},
        40: {"name": "WasteArmor (Hazardous Waste)", "color": "Drum Hazard Orange", "hex": "#E86A1C"},
        41: {"name": "GridArmor (Electric Utilities)", "color": "High-Voltage Cyan", "hex": "#00A6D6"},
        42: {"name": "WaterArmor (Water Utilities)", "color": "Reservoir Navy", "hex": "#16457A"},
        43: {"name": "LawArmor (Law Firms)", "color": "Counsel Oxblood", "hex": "#6D1A36"},
        44: {"name": "CampusArmor (Colleges & Universities)", "color": "Ivy Green", "hex": "#2E6B3A"},
        45: {"name": "ChildArmor (Child Care)", "color": "Crayon Sky Blue", "hex": "#5AB0F0"},
        46: {"name": "HotelArmor (Hotels & Lodging)", "color": "Concierge Plum", "hex": "#7B3F7E"},
        47: {"name": "BarArmor (Bars, Breweries & Liquor)", "color": "Amber Ale", "hex": "#C8792A"},
        48: {"name": "FirearmArmor (Firearms Dealers)", "color": "Gunmetal Grey", "hex": "#53565A"},
        49: {"name": "CasinoArmor (Casinos & Gaming)", "color": "Felt Table Green", "hex": "#0B7A3E"},
        50: {"name": "ShopArmor (E-commerce)", "color": "Cart Magenta", "hex": "#D63384"},
    }


# =====================================================================
# 🧮 BOOTSTRAPPED SOLOPRENEUR COST AND TELEMETRY ENGINE
# =====================================================================
class CostOptimizerTracker:
    def __init__(self):
        self.replit_core_hosting = 30.00
        self.api_call_cost = 0.000133  # Event-driven optimization configuration
        self.total_api_calls = 0

    def record_optimized_api_execution(self):
        self.total_api_calls += 1

    def calculate_total_out_of_pocket(self):
        variable_api_spend = self.total_api_calls * self.api_call_cost
        return self.replit_core_hosting + variable_api_spend

    def total_cost_tracker(self):
        return f"${self.calculate_total_out_of_pocket():.5f} / month"


# =====================================================================
# 📋 COMPLIANCE RESULT RECORD
# =====================================================================
@dataclass
class ComplianceResult:
    module_id: int
    module: str
    feature: str
    level: str
    status: str
    message: str
    rule: str
    timestamp: str

    @property
    def cleared(self):
        return self.level == CLEARED

    def to_dict(self):
        return asdict(self)


# =====================================================================
# 🌌 THE 25-INDUSTRY SYSTEM CORE MAIN ENGINE
# =====================================================================
class OmniArmorPortal:
    # MARPOL minimum distance from nearest land, in nautical miles, outside
    # special areas. None means the discharge is never allowed at sea.
    MARPOL_MIN_DISTANCE_NM = {
        "plastic": None,                 # Annex V reg. 3
        "food_waste_comminuted": 3,      # Annex V reg. 4 (ground to < 25 mm)
        "food_waste": 12,                # Annex V reg. 4
        "sewage_treated": 3,             # Annex IV reg. 11 (comminuted and disinfected)
        "sewage_untreated": 12,          # Annex IV reg. 11 (en route at >= 4 knots)
    }

    # Maximum patients per licensed nurse, Cal. Code Regs. tit. 22, 70217.
    CA_NURSE_RATIOS = {
        "icu": 2,
        "labor_delivery": 2,
        "step_down": 3,
        "emergency": 4,
        "telemetry": 4,
        "pediatrics": 4,
        "postpartum": 4,
        "med_surg": 5,
        "psychiatric": 6,
    }

    NIH_SECTIONS = ("III-A", "III-B", "III-C", "III-D", "III-E", "III-F")

    def __init__(self, verbose=True):
        self.theme = MoonstoneThemeColors()
        self.tracker = CostOptimizerTracker()
        self.verbose = verbose
        self.audit_log = []

    def _execute_gatekeeper_event(self, module_id, feature_name, level, status, log_message, rule):
        """Standardized enterprise-level event logging module to secure all systems."""
        if level not in LEVELS:
            raise ValueError(f"Unknown level {level!r}; expected one of {LEVELS}")
        self.tracker.record_optimized_api_execution()
        module = self.theme.INDUSTRIES[module_id]
        result = ComplianceResult(
            module_id=module_id,
            module=module["name"],
            feature=feature_name,
            level=level,
            status=status,
            message=log_message,
            rule=rule,
            timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        )
        self.audit_log.append(result)
        if self.verbose:
            print(f"\n⚡ [{module['name']}] - Feature: {feature_name}")
            print(f"🎨 UI Theme State: Border Color {module['color']} ({module['hex']})")
            print(f"🚦 Gateway Status: {level} - {status}")
            print(f"📋 Compliance Record: {log_message}")
            print(f"⚖️  Rule: {rule}")
        return result

    @staticmethod
    def _require_non_negative(**values):
        for name, value in values.items():
            if value is not None and value < 0:
                raise ValueError(f"{name} cannot be negative (got {value})")

    def export_audit_log(self):
        """Returns every result recorded so far as a JSON string."""
        return json.dumps([r.to_dict() for r in self.audit_log], indent=2, ensure_ascii=False)

    # ==========================================
    # 💸 COSTLIEST-RISK RULE CATALOG (10 PER INDUSTRY)
    # ==========================================
    def check_rule(self, module_id, rule_key, value):
        """Checks one catalog rule against one reading."""
        rule = get_rule(module_id, rule_key)
        level, status, message = evaluate(rule, value)
        citation = rule.citation + (" (policy setting)" if rule.policy else "")
        return self._execute_gatekeeper_event(module_id, rule.title, level, status, message, citation)

    def run_industry(self, module_id, readings=None):
        """Checks all ten rules for one industry. readings maps rule key to
        value; rules without a reading use their sample value."""
        readings = readings or {}
        unknown = set(readings) - {r.key for r in CATALOG[module_id]}
        if unknown:
            raise KeyError(f"Industry {module_id} has no rules {sorted(unknown)}")
        return [self.check_rule(module_id, r.key, readings.get(r.key, r.sample)) for r in CATALOG[module_id]]

    def run_full_catalog(self):
        """Checks all 250 rules with their sample values."""
        return {module_id: self.run_industry(module_id) for module_id in sorted(CATALOG)}

    # --- 1. FLEETARMOR (LOGISTICS) ---
    def fleet_armor_hos_timer(self, driving_hours, on_duty_window_hours=None, driving_since_break_hours=None):
        """FMCSA hours of service for property-carrying drivers."""
        self._require_non_negative(driving_hours=driving_hours, on_duty_window_hours=on_duty_window_hours,
                                   driving_since_break_hours=driving_since_break_hours)
        rule = "FMCSA 49 CFR 395.3(a) - 11 h driving and 14 h on-duty window after 10 h off; 30 min break after 8 h driving"
        feature = "HOS Drive Monitor"
        if driving_hours > 11:
            return self._execute_gatekeeper_event(1, feature, BLOCKED, "DRIVING LIMIT EXCEEDED",
                f"Driver has {driving_hours:g} h of driving, over the 11-hour limit. Stop now; 10 consecutive hours off duty required.", rule)
        if driving_hours == 11:
            return self._execute_gatekeeper_event(1, feature, BLOCKED, "DRIVING LIMIT REACHED",
                "Driver has used all 11 driving hours. No more driving until 10 consecutive hours off duty.", rule)
        if on_duty_window_hours is not None and on_duty_window_hours >= 14:
            return self._execute_gatekeeper_event(1, feature, BLOCKED, "14-HOUR WINDOW CLOSED",
                f"Driver is {on_duty_window_hours:g} h into the on-duty window. No driving after the 14th hour.", rule)
        if driving_since_break_hours is not None and driving_since_break_hours >= 8:
            return self._execute_gatekeeper_event(1, feature, BLOCKED, "30-MINUTE BREAK REQUIRED",
                f"{driving_since_break_hours:g} h of driving since the last break. Take a 30-minute break before driving on.", rule)
        remaining = 11 - driving_hours
        if on_duty_window_hours is not None:
            remaining = min(remaining, 14 - on_duty_window_hours)
        if remaining <= 1:
            return self._execute_gatekeeper_event(1, feature, WARNING, "LIMIT APPROACHING",
                f"Only {remaining:g} legal driving hour(s) left. Plan the stop now.", rule)
        return self._execute_gatekeeper_event(1, feature, CLEARED, "CLEARED",
            f"Driver has {remaining:g} legal driving hours remaining.", rule)

    # --- 2. RESTOARMOR (RESTAURANTS) ---
    def resto_armor_temp_check(self, current_temp_f, unit_name="Cold holding unit"):
        """Cold holding of time/temperature-control-for-safety (TCS) food."""
        rule = "FDA Food Code 3-501.16(A)(2) - cold-hold TCS food at 41°F (5°C) or below"
        feature = "HACCP Cold-Chain Guard"
        if current_temp_f > 41:
            return self._execute_gatekeeper_event(2, feature, BLOCKED, "HOLD FOOD - OUT OF TEMPERATURE",
                f"{unit_name} at {current_temp_f:g}°F is above 41°F. Hold TCS food and check how long it was out of temperature before serving or discarding.", rule)
        if current_temp_f > 39:
            return self._execute_gatekeeper_event(2, feature, WARNING, "NEAR LIMIT",
                f"{unit_name} at {current_temp_f:g}°F is within 2°F of the 41°F limit. Check the door seal and load.", rule)
        return self._execute_gatekeeper_event(2, feature, CLEARED, "CLEARED",
            f"{unit_name} holding safely at {current_temp_f:g}°F.", rule)

    # --- 3. YACHTARMOR (SUPERYACHTS) ---
    def yacht_armor_marpol_sentry(self, distance_from_land_nm, discharge_requested, waste_type="sewage_untreated"):
        """MARPOL discharge limits outside special areas. Annex IV covers ships of
        400 GT and above or certified for more than 15 persons."""
        self._require_non_negative(distance_from_land_nm=distance_from_land_nm)
        if waste_type not in self.MARPOL_MIN_DISTANCE_NM:
            raise ValueError(f"Unknown waste_type {waste_type!r}; expected one of {list(self.MARPOL_MIN_DISTANCE_NM)}")
        rule = "MARPOL Annex IV reg. 11 (sewage) and Annex V regs. 3-4 (garbage), outside special areas"
        feature = "MARPOL Waste Verifier"
        if not discharge_requested:
            return self._execute_gatekeeper_event(3, feature, CLEARED, "CLEARED",
                "No discharge requested. Waste retained on board.", rule)
        minimum = self.MARPOL_MIN_DISTANCE_NM[waste_type]
        if minimum is None:
            return self._execute_gatekeeper_event(3, feature, BLOCKED, "DISCHARGE PROHIBITED",
                "Plastics may never be discharged at sea. Land them ashore.", rule)
        if distance_from_land_nm < minimum:
            return self._execute_gatekeeper_event(3, feature, BLOCKED, "DISCHARGE PROHIBITED",
                f"{waste_type} needs at least {minimum} nm from nearest land; vessel is {distance_from_land_nm:g} nm out.", rule)
        extra = " Vessel must be en route at 4 knots or more." if waste_type == "sewage_untreated" else ""
        return self._execute_gatekeeper_event(3, feature, CLEARED, "CLEARED",
            f"{waste_type} discharge permitted at {distance_from_land_nm:g} nm.{extra} Not allowed in special areas or U.S. No Discharge Zones. Log it in the record book.", rule)

    # --- 4. AEROARMOR (AVIATION) ---
    def aero_armor_faa_logger(self, hours_since_inspection, ferrying_to_inspection=False):
        """100-hour inspection for aircraft used for hire, including Part 135
        aircraft with 9 or fewer passenger seats."""
        self._require_non_negative(hours_since_inspection=hours_since_inspection)
        rule = "14 CFR 91.409(b) and 135.411(a)(1) - 100-hour inspection; up to 10 h over only to reach the inspection"
        feature = "FAA Maintenance Tracking"
        h = hours_since_inspection
        if h > 110 or (h >= 100 and not ferrying_to_inspection):
            return self._execute_gatekeeper_event(4, feature, BLOCKED, "GROUNDED",
                f"{h:g} h since the last 100-hour inspection. Aircraft may not fly for hire until inspected.", rule)
        if h >= 100:
            return self._execute_gatekeeper_event(4, feature, WARNING, "FERRY TO INSPECTION ONLY",
                f"{h:g} h: within the 10-hour allowance to reach the inspection. The overage counts against the next 100 hours.", rule)
        if h >= 90:
            return self._execute_gatekeeper_event(4, feature, WARNING, "INSPECTION DUE SOON",
                f"{100 - h:g} h until the 100-hour inspection. Schedule it now.", rule)
        return self._execute_gatekeeper_event(4, feature, CLEARED, "CLEARED",
            f"{100 - h:g} h until the 100-hour inspection.", rule)

    # --- 5. HOSPITALARMOR (HOSPITALS) ---
    def hospital_armor_patient_gate(self, nurses_on_duty, patient_census, unit="med_surg", max_patients_per_nurse=None):
        """Nurse staffing ratios. CMS requires adequate staffing but sets no
        federal ratio, so the default table is California's."""
        self._require_non_negative(nurses_on_duty=nurses_on_duty, patient_census=patient_census)
        if max_patients_per_nurse is None:
            if unit not in self.CA_NURSE_RATIOS:
                raise ValueError(f"Unknown unit {unit!r}; pass max_patients_per_nurse or use one of {list(self.CA_NURSE_RATIOS)}")
            limit = self.CA_NURSE_RATIOS[unit]
            rule = f"Cal. Code Regs. tit. 22, 70217 ({unit} 1:{limit}); CMS 42 CFR 482.23(b) sets no federal ratio"
        else:
            limit = max_patients_per_nurse
            rule = f"Configured ratio 1:{limit}; CMS 42 CFR 482.23(b) requires adequate staffing but sets no federal ratio"
        feature = "Nurse Staffing Ratio Watch"
        if nurses_on_duty == 0:
            if patient_census == 0:
                return self._execute_gatekeeper_event(5, feature, CLEARED, "CLEARED", "No patients on the unit.", rule)
            return self._execute_gatekeeper_event(5, feature, BLOCKED, "UNSTAFFED",
                f"{patient_census} patients with no nurse on duty.", rule)
        ratio = patient_census / nurses_on_duty
        if ratio > limit:
            return self._execute_gatekeeper_event(5, feature, BLOCKED, "RATIO EXCEEDED",
                f"{ratio:.1f} patients per nurse is over the 1:{limit} limit. Call in staff or divert admissions.", rule)
        if ratio == limit:
            return self._execute_gatekeeper_event(5, feature, WARNING, "AT LIMIT",
                f"Exactly 1:{limit}. The next admission needs another nurse.", rule)
        return self._execute_gatekeeper_event(5, feature, CLEARED, "CLEARED",
            f"{ratio:.1f} patients per nurse, within 1:{limit}.", rule)

    # --- 6. AIARMOR (AI PLATFORMS) ---
    def ai_armor_eu_act_monitor(self, drift_score, policy_threshold=0.15):
        """Post-market monitoring for high-risk AI systems. The Act sets no
        numeric drift limit; policy_threshold comes from your risk-management plan."""
        self._require_non_negative(drift_score=drift_score, policy_threshold=policy_threshold)
        rule = "EU AI Act Art. 15 (accuracy, robustness) and Art. 72 (post-market monitoring); threshold is your own policy"
        feature = "EU AI Act Drift Monitor"
        if drift_score > policy_threshold:
            return self._execute_gatekeeper_event(6, feature, BLOCKED, "SUSPEND AND REVIEW",
                f"Drift {drift_score:g} exceeds your {policy_threshold:g} threshold. Pause the release and re-validate accuracy before redeploying.", rule)
        if drift_score >= 0.8 * policy_threshold:
            return self._execute_gatekeeper_event(6, feature, WARNING, "DRIFT RISING",
                f"Drift {drift_score:g} is within 20% of your {policy_threshold:g} threshold. Schedule a re-validation.", rule)
        return self._execute_gatekeeper_event(6, feature, CLEARED, "CLEARED",
            f"Drift {drift_score:g} is within your {policy_threshold:g} threshold.", rule)

    # --- 7. LIBRARYARMOR (LIBRARIES) ---
    def library_armor_cipa_filter(self, requested_url, flagged_by_filter, adult_research_override=False):
        """CIPA filtering for libraries that receive E-rate or LSTA funds."""
        rule = "CIPA, 47 U.S.C. 254(h)(6) - filter images that are obscene, child sexual abuse material or harmful to minors"
        feature = "CIPA Web Content Sentry"
        if not flagged_by_filter:
            return self._execute_gatekeeper_event(7, feature, CLEARED, "CLEARED",
                f"'{requested_url}' passed the filter.", rule)
        if adult_research_override:
            return self._execute_gatekeeper_event(7, feature, CLEARED, "FILTER DISABLED FOR ADULT",
                f"Staff disabled the filter for an adult's bona fide research or other lawful purpose (254(h)(6)(D)). Access to '{requested_url}' allowed.", rule)
        return self._execute_gatekeeper_event(7, feature, BLOCKED, "ACCESS BLOCKED",
            f"'{requested_url}' matched a CIPA filter category.", rule)

    # --- 8. SCHOOLARMOR (SCHOOLS) ---
    def school_armor_ferpa_block(self, requester_role, legitimate_educational_interest=False, written_consent_on_file=False):
        """Access to student education records."""
        rule = "FERPA 34 CFR 99.30 (written consent) and 99.31(a)(1) (school officials with legitimate educational interest)"
        feature = "FERPA Records Access Guard"
        if written_consent_on_file:
            return self._execute_gatekeeper_event(8, feature, CLEARED, "CLEARED",
                f"Disclosure to {requester_role} covered by signed written consent.", rule)
        if requester_role == "school_official" and legitimate_educational_interest:
            return self._execute_gatekeeper_event(8, feature, CLEARED, "CLEARED",
                "School official with a legitimate educational interest.", rule)
        return self._execute_gatekeeper_event(8, feature, BLOCKED, "ACCESS REJECTED",
            f"{requester_role} has no written consent and no 99.31 exception. Records withheld.", rule)

    # --- 9. PROPARMOR (REAL ESTATE) ---
    def prop_armor_escrow_isolation(self, deposit_in_separate_account):
        """Tenant deposits and client trust funds kept apart from operating cash."""
        rule = "State trust-account and security-deposit law (e.g., N.Y. Gen. Oblig. Law 7-103, Fla. Stat. 83.49)"
        feature = "Trust Funds Segregation Lock"
        if not deposit_in_separate_account:
            return self._execute_gatekeeper_event(9, feature, BLOCKED, "TRANSACTION FROZEN",
                "Tenant or client funds cannot be mixed with business operating cash. Move them to the trust or escrow account.", rule)
        return self._execute_gatekeeper_event(9, feature, CLEARED, "CLEARED",
            "Funds posted to a separate trust or escrow account.", rule)

    # --- 10. AUTOARMOR (DEALERSHIPS) ---
    def auto_armor_ftc_sticker_check(self, buyers_guide_displayed):
        """FTC Used Car Rule window sticker."""
        rule = "FTC Used Car Rule, 16 CFR 455.2 - Buyers Guide posted on every used vehicle offered for sale"
        feature = "FTC Used Car Rule Monitor"
        if not buyers_guide_displayed:
            return self._execute_gatekeeper_event(10, feature, BLOCKED, "HOLD FROM SALE",
                "Vehicle has no Buyers Guide in the window. Post it before showing or selling.", rule)
        return self._execute_gatekeeper_event(10, feature, CLEARED, "CLEARED",
            "Buyers Guide posted.", rule)

    # --- 11. LUXURYARMOR (LUXURY BRANDS) ---
    def luxury_armor_cites_gate(self, cites_listed_species, cites_permit_attached):
        """International trade in products from CITES-listed species."""
        rule = "CITES; U.S. rules 50 CFR Parts 14 and 23 (permits plus USFWS Form 3-177 declaration)"
        feature = "CITES Exotic Materials Permitting"
        if cites_listed_species and not cites_permit_attached:
            return self._execute_gatekeeper_event(11, feature, BLOCKED, "DISTRIBUTION FROZEN",
                "Batch contains a CITES-listed species with no permit attached. Hold at customs until permits are on file.", rule)
        if cites_listed_species:
            return self._execute_gatekeeper_event(11, feature, CLEARED, "CLEARED",
                "CITES permit on file for listed-species materials.", rule)
        return self._execute_gatekeeper_event(11, feature, CLEARED, "CLEARED",
            "No CITES-listed materials in this batch.", rule)

    # --- 12. AGRIARMOR (AGRICULTURE) ---
    def agri_armor_withholding_clock(self, days_since_application, phi_days):
        """Pesticide pre-harvest interval (PHI) from the product label."""
        self._require_non_negative(days_since_application=days_since_application, phi_days=phi_days)
        rule = "FIFRA 12(a)(2)(G) - use must follow the label, including its pre-harvest interval"
        feature = "Pre-Harvest Interval Clock"
        if days_since_application < phi_days:
            return self._execute_gatekeeper_event(12, feature, BLOCKED, "DO NOT HARVEST",
                f"{days_since_application:g} of {phi_days:g} PHI days elapsed. Wait {phi_days - days_since_application:g} more day(s).", rule)
        return self._execute_gatekeeper_event(12, feature, CLEARED, "CLEARED",
            f"PHI of {phi_days:g} days met. Harvest permitted.", rule)

    # --- 13. COPARMOR (POLICE COMPLIANCE) ---
    def cop_armor_evidence_timer(self, days_since_last_inspection, max_days=183):
        """Property and evidence room inspections. The default (semiannual)
        follows CALEA accreditation; set max_days to your agency policy."""
        self._require_non_negative(days_since_last_inspection=days_since_last_inspection, max_days=max_days)
        rule = "CALEA Standard 84.1.6 - semiannual property/evidence inspections (accredited agencies) or agency policy"
        feature = "Evidence Chain-of-Custody Audit Timer"
        d = days_since_last_inspection
        if d > max_days:
            return self._execute_gatekeeper_event(13, feature, BLOCKED, "INSPECTION OVERDUE",
                f"{d:g} days since the last evidence room inspection; limit is {max_days:g}. Inspect before the next court release.", rule)
        if d > max_days - 30:
            return self._execute_gatekeeper_event(13, feature, WARNING, "INSPECTION DUE SOON",
                f"Inspection due in {max_days - d:g} days.", rule)
        return self._execute_gatekeeper_event(13, feature, CLEARED, "CLEARED",
            f"Next inspection due in {max_days - d:g} days.", rule)

    # --- 14. FIREARMOR (FIRE DEPARTMENTS) ---
    def fire_armor_scba_verification(self, inspected_this_shift, cylinder_pressure_pct=None):
        """SCBA readiness. cylinder_pressure_pct is a percent of the maker's
        rated full pressure."""
        self._require_non_negative(cylinder_pressure_pct=cylinder_pressure_pct)
        rule = "OSHA 29 CFR 1910.134(h)(3) - SCBA checked before and after use and monthly; recharge below 90% pressure"
        feature = "SCBA Readiness Check"
        if not inspected_this_shift:
            return self._execute_gatekeeper_event(14, feature, BLOCKED, "OUT OF SERVICE",
                "SCBA has not been checked this shift. Do not assign it until inspected.", rule)
        if cylinder_pressure_pct is not None and cylinder_pressure_pct < 90:
            return self._execute_gatekeeper_event(14, feature, BLOCKED, "RECHARGE REQUIRED",
                f"Cylinder at {cylinder_pressure_pct:g}% of rated pressure. Recharge before use.", rule)
        return self._execute_gatekeeper_event(14, feature, CLEARED, "CLEARED",
            "SCBA inspected and cylinder charged.", rule)

    # --- 15. PARKARMOR (AMUSEMENT PARKS) ---
    def park_armor_ride_clearance(self, daily_inspection_completed):
        """Pre-opening ride inspection."""
        rule = "ASTM F770 - daily pre-opening inspection by the owner/operator; state ride laws adopt or add to it"
        feature = "Ride Opening Clearance"
        if not daily_inspection_completed:
            return self._execute_gatekeeper_event(15, feature, BLOCKED, "RIDE CLOSED",
                "Today's pre-opening inspection is not signed off. Ride stays closed.", rule)
        return self._execute_gatekeeper_event(15, feature, CLEARED, "CLEARED",
            "Daily inspection signed off. Ride may open.", rule)

    # --- 16. JAILARMOR (PRISON COMPLIANCE) ---
    def jail_armor_wellness_timer(self, minutes_since_last_check, max_interval_minutes=30):
        """Welfare checks in restrictive housing. 30 minutes is a common
        corrections standard; suicide watch is usually 15 minutes or constant."""
        self._require_non_negative(minutes_since_last_check=minutes_since_last_check,
                                   max_interval_minutes=max_interval_minutes)
        rule = "Corrections standards (e.g., ACA): restrictive-housing checks at least every 30 min at irregular times; set to your policy"
        feature = "Inmate Welfare Check Timer"
        m = minutes_since_last_check
        if m > max_interval_minutes:
            return self._execute_gatekeeper_event(16, feature, BLOCKED, "CHECK OVERDUE",
                f"{m:g} min since the last welfare check; limit is {max_interval_minutes:g}. Check the cell now.", rule)
        if m >= 0.8 * max_interval_minutes:
            return self._execute_gatekeeper_event(16, feature, WARNING, "CHECK DUE",
                f"Check due within {max_interval_minutes - m:g} min.", rule)
        return self._execute_gatekeeper_event(16, feature, CLEARED, "CLEARED",
            f"Last check {m:g} min ago.", rule)

    # --- 17. INSUREARMOR (INSURANCE) ---
    def insure_armor_tcpa_filter(self, on_do_not_call_list, prior_express_written_consent=False,
                                 established_business_relationship=False, autodialed_or_prerecorded=True,
                                 local_hour=None):
        """Telemarketing call gate. local_hour is the called party's local hour (0-23)."""
        rule = "TCPA 47 U.S.C. 227; 47 CFR 64.1200(a)(2)-(3) consent, (c)(1) 8 a.m.-9 p.m., (c)(2) National Do Not Call"
        feature = "TCPA Dialer Gate"
        problems = []
        if autodialed_or_prerecorded and not prior_express_written_consent:
            problems.append("autodialed or prerecorded marketing calls need prior express written consent")
        if on_do_not_call_list and not (prior_express_written_consent or established_business_relationship):
            problems.append("number is on the National Do Not Call Registry with no written consent or established business relationship")
        if local_hour is not None and not 8 <= local_hour < 21:
            problems.append("call would fall outside 8 a.m.-9 p.m. local time")
        if problems:
            return self._execute_gatekeeper_event(17, feature, BLOCKED, "CALL BLOCKED",
                "Do not dial: " + "; ".join(problems) + ".", rule)
        return self._execute_gatekeeper_event(17, feature, CLEARED, "CLEARED",
            "Consent and calling-time checks passed.", rule)

    # --- 18. BANKARMOR (BANKING COMPLIANCE) ---
    def bank_armor_ctr_monitor(self, cash_total_business_day):
        """Currency Transaction Report on a customer's aggregated cash for one business day."""
        self._require_non_negative(cash_total_business_day=cash_total_business_day)
        rule = "BSA 31 CFR 1010.311 and 1010.313 - CTR for cash over $10,000 per business day; file within 15 days (1010.306)"
        feature = "BSA CTR Monitor"
        amount = cash_total_business_day
        if amount > 10000:
            return self._execute_gatekeeper_event(18, feature, WARNING, "CTR FILING REQUIRED",
                f"${amount:,.2f} in cash today. File a FinCEN CTR within 15 calendar days. The transaction itself may proceed.", rule)
        if amount >= 9000:
            return self._execute_gatekeeper_event(18, feature, WARNING, "STRUCTURING REVIEW",
                f"${amount:,.2f} is just under the CTR threshold. Review recent activity for structuring (31 U.S.C. 5324).", rule)
        return self._execute_gatekeeper_event(18, feature, CLEARED, "CLEARED",
            f"${amount:,.2f} in cash today. No CTR required.", rule)

    # --- 19. FINTECHARMOR (FINANCE COMPLIANCE) ---
    def fintech_armor_adv_countdown(self, days_since_fiscal_year_end):
        """Form ADV annual updating amendment for registered investment advisers."""
        self._require_non_negative(days_since_fiscal_year_end=days_since_fiscal_year_end)
        rule = "SEC Advisers Act Rule 204-1(a)(1) - Form ADV annual updating amendment within 90 days of fiscal year-end"
        feature = "Form ADV Annual Amendment Countdown"
        d = days_since_fiscal_year_end
        if d > 90:
            return self._execute_gatekeeper_event(19, feature, BLOCKED, "FILING OVERDUE",
                f"{d:g} days since fiscal year-end. The amendment was due by day 90. File on IARD now.", rule)
        if d > 75:
            return self._execute_gatekeeper_event(19, feature, WARNING, "FILING DUE SOON",
                f"{90 - d:g} days left to file the annual amendment.", rule)
        return self._execute_gatekeeper_event(19, feature, CLEARED, "CLEARED",
            f"{90 - d:g} days left to file the annual amendment.", rule)

    # --- 20. PETROARMOR (OIL & GAS PRODUCTION) ---
    def petro_armor_valve_sentry(self, months_since_inspection, inspected_this_calendar_year=True):
        """Gas transmission valve inspections. Hazardous-liquid lines follow
        49 CFR 195.420 instead (twice a year, at most 7.5 months apart)."""
        self._require_non_negative(months_since_inspection=months_since_inspection)
        rule = "PHMSA 49 CFR 192.745(a) - transmission valves inspected at intervals not exceeding 15 months, at least once each calendar year"
        feature = "Valve Inspection Sentry"
        m = months_since_inspection
        if m > 15:
            return self._execute_gatekeeper_event(20, feature, BLOCKED, "INSPECTION OVERDUE",
                f"{m:g} months since the last inspection, over the 15-month limit. Inspect and partially operate the valve now.", rule)
        if not inspected_this_calendar_year:
            return self._execute_gatekeeper_event(20, feature, WARNING, "CALENDAR-YEAR INSPECTION DUE",
                "Not yet inspected this calendar year. Inspect before December 31.", rule)
        if m >= 13:
            return self._execute_gatekeeper_event(20, feature, WARNING, "INSPECTION DUE SOON",
                f"{15 - m:g} month(s) left before the 15-month limit.", rule)
        return self._execute_gatekeeper_event(20, feature, CLEARED, "CLEARED",
            f"{15 - m:g} months left before the 15-month limit.", rule)

    # --- 21. FACTORYARMOR (MANUFACTURING) ---
    def factory_armor_loto_gate(self, isolation_verified, every_worker_lock_applied=True):
        """Lockout/tagout before servicing machinery."""
        rule = "OSHA 29 CFR 1910.147(d)(6) verify isolation before servicing; (f)(3) each worker applies a personal lock in group lockout"
        feature = "LOTO Energy Sentry"
        if not isolation_verified:
            return self._execute_gatekeeper_event(21, feature, BLOCKED, "SERVICING BLOCKED",
                "Energy isolation has not been verified. Try the start controls and test for stored energy before work begins.", rule)
        if not every_worker_lock_applied:
            return self._execute_gatekeeper_event(21, feature, BLOCKED, "SERVICING BLOCKED",
                "At least one worker on the job has not applied a personal lock.", rule)
        return self._execute_gatekeeper_event(21, feature, CLEARED, "MAINTENANCE MODE READY",
            "Isolation verified and every worker's lock applied.", rule)

    # --- 22. PHARMAARMOR (PHARMACEUTICALS) ---
    def pharma_armor_cfr_signature(self, printed_name_shown, date_time_shown=True, meaning_shown=True,
                                   two_component_login=True):
        """Electronic signature checks on a regulated record."""
        rule = "FDA 21 CFR 11.50 (name, date/time and meaning shown) and 11.200(a)(1) (two distinct ID components)"
        feature = "21 CFR Part 11 Signature Validator"
        missing = []
        if not printed_name_shown:
            missing.append("signer's printed name")
        if not date_time_shown:
            missing.append("date and time of signing")
        if not meaning_shown:
            missing.append("meaning of the signature (e.g., review, approval)")
        if not two_component_login:
            missing.append("two distinct identification components at signing")
        if missing:
            return self._execute_gatekeeper_event(22, feature, BLOCKED, "RECORD NOT RELEASED",
                "Signature is missing: " + ", ".join(missing) + ".", rule)
        return self._execute_gatekeeper_event(22, feature, CLEARED, "CLEARED",
            "Signature manifestation and identity checks complete.", rule)

    # --- 23. MINEARMOR (MINING & MINERALS) ---
    def mine_armor_part46_gate(self, training_hours, days_on_job=0):
        """New-miner training at Part 46 mines (sand, gravel, surface stone and
        similar); other mines follow Part 48."""
        self._require_non_negative(training_hours=training_hours, days_on_job=days_on_job)
        rule = "MSHA 30 CFR 46.5 - new miners: 4 h before starting work, 24 h total within 90 days"
        feature = "Part 46 Training Gate"
        if training_hours < 4:
            return self._execute_gatekeeper_event(23, feature, BLOCKED, "SITE ACCESS DENIED",
                f"{training_hours:g} of the 4 required pre-work training hours completed. Worker may not start.", rule)
        if training_hours < 24 and days_on_job >= 90:
            return self._execute_gatekeeper_event(23, feature, BLOCKED, "TRAINING OVERDUE",
                f"{days_on_job:g} days on the job with {training_hours:g} of 24 training hours. Remove from work until complete.", rule)
        if training_hours < 24:
            return self._execute_gatekeeper_event(23, feature, WARNING, "TRAINING IN PROGRESS",
                f"{24 - training_hours:g} more hours needed within {90 - days_on_job:g} days.", rule)
        return self._execute_gatekeeper_event(23, feature, CLEARED, "CLEARED",
            "24-hour new-miner training complete.", rule)

    # --- 24. PORTARMOR (PORT AUTHORITIES) ---
    def port_armor_twic_check(self, has_valid_twic, escorted=False):
        """Access to MTSA secure areas."""
        rule = "MTSA, 33 CFR 101.514 - unescorted access to secure areas requires a valid TWIC"
        feature = "TWIC Access Gatekeeper"
        if has_valid_twic:
            return self._execute_gatekeeper_event(24, feature, CLEARED, "CLEARED",
                "Valid TWIC. Unescorted access granted.", rule)
        if escorted:
            return self._execute_gatekeeper_event(24, feature, CLEARED, "ESCORTED ACCESS",
                "No TWIC. Access allowed only with a TWIC-holding escort.", rule)
        return self._execute_gatekeeper_event(24, feature, BLOCKED, "ACCESS DENIED",
            "No valid TWIC and no escort. Gate stays closed.", rule)

    # --- 25. GENEARMOR (BIOTECH & GENETICS) ---
    def gene_armor_nih_monitor(self, ibc_approved, guidelines_section="III-D"):
        """Recombinant or synthetic nucleic acid experiments at institutions
        that receive NIH funding."""
        if guidelines_section not in self.NIH_SECTIONS:
            raise ValueError(f"Unknown guidelines_section {guidelines_section!r}; expected one of {self.NIH_SECTIONS}")
        rule = "NIH Guidelines Section III - IBC approval before III-A to III-D work; IBC registration at start for III-E; III-F exempt"
        feature = "NIH Recombinant DNA Monitor"
        if guidelines_section == "III-F":
            return self._execute_gatekeeper_event(25, feature, CLEARED, "EXEMPT",
                "Section III-F experiment. Exempt from IBC review; keep it registered per institutional policy.", rule)
        if guidelines_section == "III-E":
            if ibc_approved:
                return self._execute_gatekeeper_event(25, feature, CLEARED, "CLEARED",
                    "Section III-E experiment registered with the IBC.", rule)
            return self._execute_gatekeeper_event(25, feature, WARNING, "IBC NOTICE REQUIRED",
                "Section III-E experiment: register with the IBC at the time work starts.", rule)
        if not ibc_approved:
            return self._execute_gatekeeper_event(25, feature, BLOCKED, "EXPERIMENT LOCKED",
                f"Section {guidelines_section} experiment has no IBC approval. Work may not begin.", rule)
        if guidelines_section in ("III-A", "III-B", "III-C"):
            extra = {"III-A": "the NIH Director", "III-B": "NIH OSP", "III-C": "the IRB"}[guidelines_section]
            return self._execute_gatekeeper_event(25, feature, WARNING, "CONFIRM ADDITIONAL APPROVAL",
                f"IBC approval on file. Section {guidelines_section} work also needs approval from {extra}; confirm it is recorded.", rule)
        return self._execute_gatekeeper_event(25, feature, CLEARED, "CLEARED",
            "IBC approval on file.", rule)

    # ==========================================
    # 🌌 DATA PORTAL EXECUTION ENGINE
    # ==========================================
    def run_portal(self):
        """Runs one sample check for each of the 25 modules and returns the results."""
        if self.verbose:
            print(f"\n🛡️  OmniArmor.ai: {SLOGAN}")
            print(f"🌌 [OmniArmor.ai Master Portal]: Active - Theme: {self.theme.BASE_THEME} / Brand: {self.theme.BRAND_PRIMARY}")
            print(f"💰 Bootstrapped Maintenance Overhead Active: {self.tracker.total_cost_tracker()}")
            print("-" * 75)

        # 🚀 FIRING ALL 25 INDUSTRIES IN ONE INTEGRATED SIMULATION LOOP
        results = [
            self.fleet_armor_hos_timer(11.5),
            self.resto_armor_temp_check(42.1, unit_name="Walk-in cooler"),
            self.yacht_armor_marpol_sentry(2.1, True),
            self.aero_armor_faa_logger(102),
            self.hospital_armor_patient_gate(5, 25),
            self.ai_armor_eu_act_monitor(0.18),
            self.library_armor_cipa_filter("http://blocked-domain.com", True),
            self.school_armor_ferpa_block("vendor"),
            self.prop_armor_escrow_isolation(False),
            self.auto_armor_ftc_sticker_check(False),
            self.luxury_armor_cites_gate(True, False),
            self.agri_armor_withholding_clock(4, 7),
            self.cop_armor_evidence_timer(280),
            self.fire_armor_scba_verification(False),
            self.park_armor_ride_clearance(False),
            self.jail_armor_wellness_timer(18),
            self.insure_armor_tcpa_filter(True),
            self.bank_armor_ctr_monitor(15000.00),
            self.fintech_armor_adv_countdown(95),
            self.petro_armor_valve_sentry(16),
            self.factory_armor_loto_gate(True),
            self.pharma_armor_cfr_signature(False),
            self.mine_armor_part46_gate(2),
            self.port_armor_twic_check(False),
            self.gene_armor_nih_monitor(False),
        ]

        if self.verbose:
            counts = {level: sum(r.level == level for r in results) for level in LEVELS}
            print(f"\n🏁 [Launch Matrix Execution Complete] - Detailed Checks Run: {len({r.module_id for r in results})} industries (all {len(self.theme.INDUSTRIES)} are covered by the rule catalog)")
            print(f"🚦 Cleared: {counts[CLEARED]} | Warnings: {counts[WARNING]} | Blocked: {counts[BLOCKED]}")
            print(f"💳 Final Calculated Running Overhead Cost: {self.tracker.total_cost_tracker()}")
        return results


def print_catalog_summary():
    """Runs all 250 catalog rules on their sample values and prints one line per industry."""
    portal = OmniArmorPortal(verbose=False)
    print("\n💸 [Costliest-Risk Catalog] - 10 rules per industry, sample readings")
    print("-" * 83)
    totals = {level: 0 for level in LEVELS}
    for module_id, results in portal.run_full_catalog().items():
        counts = {level: sum(r.level == level for r in results) for level in LEVELS}
        for level in LEVELS:
            totals[level] += counts[level]
        name = portal.theme.INDUSTRIES[module_id]["name"]
        name = name if len(name) <= 44 else name[:43] + "…"
        print(f" [{module_id:02d}] {name:<44} Cleared {counts[CLEARED]:>2} | Warning {counts[WARNING]:>2} | Blocked {counts[BLOCKED]:>2}")
    print("-" * 83)
    print(f" All {sum(totals.values())} rules: Cleared {totals[CLEARED]} | Warning {totals[WARNING]} | Blocked {totals[BLOCKED]}")


if __name__ == "__main__":
    portal = OmniArmorPortal()
    portal.run_portal()
    print_catalog_summary()
