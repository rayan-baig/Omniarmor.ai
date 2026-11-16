# -*- coding: utf-8 -*-
"""
Rule catalog, group 11: SchoolSafetyArmor, a K-12 school's safety and
operations routines (private, charter and public), beside SchoolArmor's
legal duties (industry 8: FERPA, IDEA, Title IX, AHERA). Ten checks a
school office runs into, most of them a reminder to do
something and write it down: drills, AED and first-aid kits, playground and
gym equipment, the nurse's office, the cafeteria, buses and vans, athletics,
visitor sign-in, the science lab and staff background checks.

The rules behind them differ from state to state, so every limit is a policy
setting a school can change to match its own state and insurer. No rule sets
`method`.
"""

from omni_armor_rules.rule import Rule

RULES = {
    # --- 51. SCHOOLSAFETYARMOR (school safety and operations) ---
    51: [
        Rule(key="drills_logged", title="Fire and lockdown drills logged",
             cost="A missed or unlogged drill is a common fire marshal finding, can bring fines, and leaves no record"
                  " if something goes wrong.",
             citation="State fire code and school safety drill rules (they vary by state)", kind="max",
             input="Days since the last fire or lockdown drill was held and written down", unit="days", limit=30,
             warn=25, policy=True, sample=21,
             action="Hold the next drill on your state's schedule and write down the date, time, kind of drill and"
                    " how long it took."),
        Rule(key="aed_first_aid_check", title="AED and first-aid kits checked",
             cost="A dead AED battery or expired pads can cost a life, and an empty first-aid kit is a common"
                  " inspection finding.",
             citation="AED maker's instructions; state school health rules (they vary by state)", kind="max",
             input="Days since every AED (ready light, pads, battery) and first-aid kit was last checked and"
                   " written down", unit="days", limit=30, warn=25, policy=True, sample=12,
             action="Check each AED's ready light and its pad and battery dates, restock every first-aid kit, then"
                    " write down the date."),
        Rule(key="play_equipment_check", title="Playground and gym equipment checked",
             cost="Broken equipment and worn surfacing cause injuries, and an injury with no inspection record is"
                  " costly to settle.",
             citation="CPSC Public Playground Safety Handbook; equipment makers' instructions", kind="max",
             input="Days since the playground and gym equipment were last inspected and the inspection written down",
             unit="days", limit=30, warn=25, policy=True, sample=34,
             action="Walk the playground and gym, close off anything broken, fix or report it, and write down what"
                    " you checked."),
        Rule(key="nurse_log_and_fridge", title="Medication log and fridge reviewed",
             cost="Missed doses, and medicine kept too warm or too cold, put students at risk and are a common"
                  " state health finding.",
             citation="State school nursing and medication rules (they vary by state); medicine makers' storage"
                      " instructions", kind="max",
             input="Days since the nurse's office medication log and fridge temperature log were last reviewed",
             unit="days", limit=7, warn=5, policy=True, sample=3,
             action="Check the medication log against the medicine on hand, look over the fridge temperatures, fix"
                    " any gap and write down the date."),
        Rule(key="cafeteria_food_safety", title="Cafeteria food-safety check done",
             cost="Food kept at the wrong temperature makes students sick and can bring a failed health inspection"
                  " or a closed kitchen.",
             citation="FDA Food Code as adopted by your state; USDA school meal food safety program, 7 CFR 210.13",
             kind="max",
             input="Days since the cafeteria's food-safety self-check (fridge and freezer temperatures, hot holding,"
                   " handwashing, date labels) was done and written down",
             unit="days", limit=7, warn=5, policy=True, sample=2,
             action="Do the food-safety self-check today, fix anything out of range and write down the results."),
        Rule(key="bus_pretrip_review", title="Bus and van pre-trip checks reviewed",
             cost="A bus or van with bad brakes, tires or lights can be put out of service, and missing checks weaken"
                  " an insurance claim.",
             citation="State pupil transportation rules; FMCSA 49 CFR 392.7 and 396.13 for drivers who need a CDL",
             kind="max",
             input="Days since the drivers' pre-trip check sheets for every bus and van were last reviewed",
             unit="days", limit=7, warn=5, policy=True, sample=4,
             action="Collect the pre-trip sheets for every bus and van, follow up on every problem written down, and"
                    " keep them on file."),
        Rule(key="athletics_safety", title="Concussion forms and heat checks",
             cost="An athlete playing without a signed concussion form, or practicing in dangerous heat, risks"
                  " serious injury and a costly claim.",
             citation="State youth sports concussion laws; your state athletic association's heat rules (they vary"
                      " by state)", kind="required",
             input="This season, is a signed concussion form on file for every athlete, and is the heat checked and"
                   " written down before outdoor practice on hot days?",
             sample=True, policy=True,
             action="Hold out any athlete without a signed form, and check and write down the heat before every"
                    " outdoor practice."),
        Rule(key="visitor_log_review", title="Visitor sign-in log reviewed",
             cost="Without a reviewed sign-in log nobody can say who was in the building, and gaps in the front-desk"
                  " routine go unnoticed.",
             citation="Your school's own safety plan; state school safety rules (they vary by state)", kind="max",
             input="Days since the visitor sign-in log was last reviewed for missing sign-outs, badges and anything"
                   " unusual", unit="days", limit=7, warn=5, policy=True, sample=9,
             action="Review the sign-in log, follow up on missing sign-outs or badges, and write down the date you"
                    " checked."),
        Rule(key="lab_chemical_storage", title="Science lab chemicals stored safely",
             cost="Old, unlabeled or wrongly stored chemicals can cause fires and injuries, bring OSHA penalties, and"
                  " are costly to clear out.",
             citation="OSHA Laboratory Standard, 29 CFR 1910.1450; OSHA Hazard Communication, 29 CFR 1910.1200",
             kind="max",
             input="Days since the science lab chemical storage was last checked (labels, safety data sheets, locked"
                   " cabinets, old stock)", unit="days", limit=90, warn=75, policy=True, sample=60,
             action="Check labels and safety data sheets, lock up what should be locked, set old stock aside for"
                    " proper disposal and note the date."),
        Rule(key="background_check_renewals", title="Staff background checks up to date",
             cost="Staff working with children on a lapsed background check can break state rules and your insurer's"
                  " terms, and puts students at risk.",
             citation="State school employee background check laws (they vary by state)", kind="min",
             input="Days until the next staff background-check renewal is due", unit="days", limit=0, warn=45,
             policy=True, sample=52,
             action="Start the renewal now so it's back before it lapses, and keep staff without a current check"
                    " away from students."),
    ],
}
