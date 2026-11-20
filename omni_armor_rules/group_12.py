# -*- coding: utf-8 -*-
"""
Rule catalog, group 12 (1.11.0): starter lists for three trades that had
only borrowed checks before: SalonArmor (salons and barbershops), InkArmor
(tattoo and piercing studios) and GymArmor (gyms and fitness studios).

Most of what these trades follow is set by a state board or a city or county
health department, and differs from place to place. So most checks here are
policy settings a business changes to match its own rules, their citations
name the kind of rule ("your state board's sanitation rules") rather than
one law, and they say so ("they vary by state"). A check cites a federal
rule by number only where that rule really applies to the trade: OSHA's
Hazard Communication standard (29 CFR 1910.1200) for hazardous products used
at work, its Bloodborne Pathogens standard (29 CFR 1910.1030) for jobs with
blood exposure, its portable fire extinguisher rule (29 CFR 1910.157) and
its first-aid rule (29 CFR 1910.151). Those cover employers: a one-person
shop with no employees can treat them as good practice. No rule sets
`method`.
"""

from omni_armor_rules.rule import Rule

_EXTINGUISHER = dict(
    key="fire_extinguisher_monthly", title="Fire extinguishers checked monthly",
    cost="An extinguisher that is empty or blocked can fail in a fire, and a missed monthly check is a common fire"
         " and OSHA inspection finding.",
    citation="OSHA 29 CFR 1910.157(e)(2) (where extinguishers are provided for employees); your local fire code",
    kind="max", input="Days since every fire extinguisher was last given its monthly visual check",
    unit="days", limit=31, warn=25, sample=12,
    action="Check each extinguisher's gauge, pin and seal and that nothing blocks it, then write down the date.")

_HAZCOM = dict(
    key="safety_data_sheets", title="Safety data sheets and training",
    kind="required", sample=True,
    action="Get the missing safety data sheets from the maker or supplier, keep them where staff can reach them,"
           " and go over them with the team.")

RULES = {
    # --- 52. SALONARMOR (salons and barbershops) ---
    52: [
        Rule(key="shop_license_renewal", title="Shop license renewed on time",
             cost="Working with an expired shop license can bring state board fines and an order to stop work until"
                  " it is renewed.",
             citation="Your state board of cosmetology or barbering (license terms vary by state)", kind="min",
             input="Days until the salon's or barbershop's establishment license expires", unit="days", limit=0,
             warn=30, policy=True, sample=75,
             action="Renew the shop license with your state board now and post the new one where the board says."),
        Rule(key="operator_licenses_current", title="Every stylist licensed and current",
             cost="An unlicensed or lapsed stylist, barber or nail tech is one of the most common state board fines,"
                  " for the shop and the worker.",
             citation="State cosmetology and barbering board rules (they vary by state)", kind="required",
             input="Is everyone working on clients today licensed, with the license current and displayed as your"
                   " state board requires?",
             sample=True, policy=True,
             action="Take anyone without a current license off clients until it is renewed, and post each license."),
        Rule(key="tool_disinfection", title="Tools cleaned and disinfected",
             cost="Tools not disinfected between clients spread infections and are a top state board inspection"
                  " finding.",
             citation="State board sanitation rules (they vary by state); the disinfectant's label directions"
                      " (EPA-registered products)",
             kind="required",
             input="Are combs, brushes, clippers and other reusable tools cleaned, then disinfected with an"
                   " EPA-registered disinfectant for the label's full contact time, between clients?",
             sample=True, policy=True,
             action="Pull the tools that weren't disinfected, clean and disinfect them by the label, and keep enough"
                    " sets to rotate."),
        Rule(key="disinfectant_changed", title="Disinfectant solution changed",
             cost="Old or dirty disinfectant stops killing germs, and a cloudy jar is easy for an inspector to spot.",
             citation="State board sanitation rules (most say every day, or sooner if it's dirty); the disinfectant's"
                      " label directions",
             kind="max",
             input="Days since each disinfectant jar or tub was last mixed fresh", unit="days", limit=1, warn=1,
             policy=True, sample=0,
             action="Empty, clean and refill the jar with fresh disinfectant mixed by the label, then note the date."),
        Rule(key="foot_spa_cleaning", title="Pedicure tubs cleaned and logged",
             cost="Foot spas that aren't cleaned and disinfected can cause serious skin infections, and many states"
                  " fine a missing cleaning log.",
             citation="State board pedicure equipment rules (many states require a cleaning log); the maker's"
                      " instructions",
             kind="max",
             input="Days since each pedicure tub or foot spa was last given its end-of-day cleaning and disinfecting,"
                   " with the log filled in", unit="days", limit=1, warn=1, policy=True, sample=0,
             action="Clean and disinfect the tub (screens and jets too) by your state's steps, then fill in the log."),
        Rule(key="single_use_items", title="Single-use items thrown away",
             cost="Reusing a nail file, buffer, wax stick or razor blade on another client spreads infection and"
                  " brings state board fines.",
             citation="State board sanitation rules (they vary by state)", kind="forbidden",
             input="Was any single-use item (nail file, buffer, pumice, wax stick, neck strip or razor blade) used on"
                   " more than one client?",
             sample=False, policy=True,
             action="Throw the item away, give the client a new one, and keep enough single-use supplies at each"
                    " station."),
        Rule(citation="OSHA Hazard Communication, 29 CFR 1910.1200 (for a shop with employees)",
             cost="Hair dye, relaxers, acrylics and other products can burn skin and lungs; missing safety data sheets"
                  " or training is a common OSHA citation.",
             input="Is there a safety data sheet for every hazardous product (color, relaxer, acrylics, disinfectant),"
                   " and have staff been trained on them?",
             **_HAZCOM),
        Rule(key="nail_ventilation", title="Ventilation where nails are done",
             cost="Fumes from acrylics, gels and polish cause headaches and breathing problems, and poor ventilation"
                  " can bring state board or OSHA findings.",
             citation="State board rules (they vary by state); OSHA's guide for nail salon workers (good practice)",
             kind="required",
             input="Is the ventilation working where acrylics, gels and polish are applied (fans or vented tables, as"
                   " your state requires)?",
             sample=True, policy=True,
             action="Fix the fan or vented table before the next acrylic or gel service, and keep product lids"
                    " closed."),
        Rule(key="blood_spill_kit", title="Blood spill kit stocked",
             cost="Without gloves and disinfectant at hand, a nick or cut can expose staff and clients to blood, and"
                  " many state boards require a kit.",
             citation="State board rules for cuts and blood exposure (they vary by state); good practice",
             kind="max",
             input="Days since the blood spill kit (gloves, disinfectant, bandages, a bag for waste) was last checked"
                   " and restocked", unit="days", limit=30, warn=25, policy=True, sample=10,
             action="Restock the kit, put it where every station can reach it, and note the date."),
        Rule(**_EXTINGUISHER),
    ],

    # --- 53. INKARMOR (tattoo and piercing studios) ---
    53: [
        Rule(key="studio_permit_renewal", title="Studio permit renewed on time",
             cost="Working without a current body art permit can bring fines and a closed studio until it is"
                  " renewed.",
             citation="Your city, county or state health department's body art permit (terms vary)", kind="min",
             input="Days until the studio's body art permit expires", unit="days", limit=0, warn=30, policy=True,
             sample=90,
             action="Renew the permit with your health department now and post it where clients can see it."),
        Rule(key="artist_registration", title="Artists registered and trained",
             cost="An unregistered artist or lapsed bloodborne pathogens training can bring health department fines"
                  " and OSHA citations.",
             citation="State and local body art rules (they vary); OSHA Bloodborne Pathogens, 29 CFR"
                      " 1910.1030(g)(2) (yearly training for employees)",
             kind="required",
             input="Is every artist and piercer working today registered or licensed as your health department"
                   " requires, with bloodborne pathogens training done in the last year?",
             sample=True, policy=True,
             action="Keep anyone not registered or trained off clients until they are, and file the certificates."),
        Rule(key="spore_test", title="Sterilizer spore test passed",
             cost="An autoclave that isn't tested may not sterilize, which can spread hepatitis and other infections;"
                  " many health departments require monthly tests.",
             citation="State and local body art rules (many require a monthly spore test); the sterilizer maker's"
                      " instructions",
             kind="max",
             input="Days since each autoclave last passed a spore (biological indicator) test", unit="days",
             limit=30, warn=25, policy=True, sample=18,
             action="Run a spore test now; if it fails, stop using that sterilizer, have it serviced and resterilize"
                    " what it processed."),
        Rule(key="single_use_needles", title="Needles and ink cups single-use",
             cost="Reusing a needle, tube or ink cup on another client can spread hepatitis and HIV, and can close a"
                  " studio.",
             citation="State and local body art rules (they vary)", kind="forbidden",
             input="Was any needle, tube, ink cup or other item meant for one client used on another client?",
             sample=False, policy=True,
             action="Stop, throw the items away, tell the client, and talk to your health department about next"
                    " steps."),
        Rule(key="sharps_disposal", title="Sharps containers handled right",
             cost="Loose needles cause needlestick injuries, and wrong disposal can bring OSHA citations and medical"
                  " waste fines.",
             citation="OSHA Bloodborne Pathogens, 29 CFR 1910.1030(d)(4)(iii); your state's medical waste rules",
             kind="required",
             input="Do used needles go straight into a closable, puncture-resistant sharps container, and are full"
                   " containers disposed of under your state's medical waste rules?",
             sample=True,
             action="Put a sharps container at every station, close and replace full ones, and use a licensed"
                    " medical waste service."),
        Rule(key="exposure_control_plan", title="Exposure control plan reviewed",
             cost="An out-of-date written plan for blood exposure is one of the most cited OSHA rules for studios"
                  " with employees.",
             citation="OSHA Bloodborne Pathogens, 29 CFR 1910.1030(c)(1)(iv) (for a studio with employees)",
             kind="max",
             input="Days since the written exposure control plan was last reviewed and updated", unit="days",
             limit=365, warn=335, sample=200,
             action="Review the plan with your artists, update it for new equipment and safer needles, and date it."),
        Rule(key="hepb_vaccine_offer", title="Hep B vaccine offered to artists",
             cost="Not offering the free hepatitis B vaccine to artists who can be exposed to blood is an OSHA"
                  " citation and puts them at risk.",
             citation="OSHA Bloodborne Pathogens, 29 CFR 1910.1030(f)(2)(i) (for a studio with employees)",
             kind="required",
             input="Has every artist and piercer who can be exposed to blood been offered the hepatitis B vaccine,"
                   " free, within 10 working days of starting?",
             sample=True,
             action="Offer the vaccine now at no cost, and keep a signed form from anyone who says no."),
        Rule(key="client_records", title="Client consent and records kept",
             cost="Missing consent forms and records are a common health department finding and leave the studio"
                  " exposed if a client has a problem.",
             citation="State and local body art rules (how long to keep records varies)", kind="required",
             input="Is there a signed consent form and record for every client (date, artist, what was done, ink or"
                   " jewelry), kept as long as your health department requires?",
             sample=True, policy=True,
             action="Fill in any missing records today and keep them filed for the time your rules require."),
        Rule(key="minors_rules", title="Age rules for minors followed",
             cost="Tattooing or piercing a minor against state law can bring fines, a lost permit and criminal"
                  " charges in some states.",
             citation="State laws on tattooing and piercing minors (they vary; some ban tattooing minors)",
             kind="forbidden",
             input="Was anyone under 18 tattooed or pierced against your state's age rules (ID checked, and a"
                   " parent's consent where it is allowed)?",
             sample=False, policy=True,
             action="Stop, check ID for every client who may be under 18, and ask your health department what to do"
                    " next."),
        Rule(key="surfaces_disinfected", title="Work surfaces disinfected",
             cost="Blood left on a chair or tray can infect the next client, and dirty surfaces are a top inspection"
                  " finding.",
             citation="OSHA Bloodborne Pathogens, 29 CFR 1910.1030(d)(4)(ii); state and local body art rules",
             kind="required",
             input="Are the chair, tray and work surfaces cleaned and disinfected between clients, with barrier"
                   " film changed each time?",
             sample=True,
             action="Clean and disinfect the station before the next client and change every barrier."),
    ],

    # --- 54. GYMARMOR (gyms and fitness studios) ---
    54: [
        Rule(key="aed_check", title="AED ready and checked",
             cost="An AED with a dead battery or expired pads can cost a life, and some states require health clubs"
                  " to keep a working one.",
             citation="The AED maker's instructions; state AED and health club laws (some require one)", kind="max",
             input="Days since each AED was last checked (ready light, pads and battery dates)", unit="days",
             limit=30, warn=25, policy=True, sample=9,
             action="Check the ready light and the pad and battery dates, replace what's expired, and note the date."),
        Rule(key="staff_cpr", title="CPR-trained staff on duty",
             cost="A collapse with nobody trained nearby can cost a life, and some states require trained staff at"
                  " health clubs.",
             citation="State health club laws in some states; good practice (CPR and AED courses usually last two"
                      " years)",
             kind="required",
             input="Is someone with current CPR and AED training on duty whenever the gym is open to members?",
             sample=True, policy=True,
             action="Schedule a trained person for every open hour, and book a course for staff whose cards have"
                    " run out."),
        Rule(key="equipment_inspection", title="Equipment inspected",
             cost="Frayed cables, loose bolts and treadmills without a working stop cause injuries and costly"
                  " claims.",
             citation="Equipment makers' maintenance instructions (good practice); your insurer's terms",
             kind="max",
             input="Days since the equipment (cables, pulleys, benches, treadmill belts and stop buttons) was last"
                   " inspected and written down", unit="days", limit=30, warn=25, policy=True, sample=14,
             action="Inspect each machine, tag and close off anything unsafe until it's fixed, and note the date."),
        Rule(key="cleaning_log", title="Equipment and locker rooms cleaned",
             cost="Shared mats, benches and showers spread skin infections when they aren't cleaned, and members"
                  " notice first.",
             citation="Local health department rules for locker rooms and showers (they vary); good practice",
             kind="max",
             input="Days since the shared equipment, mats and locker rooms were last cleaned and disinfected and the"
                   " cleaning log filled in", unit="days", limit=1, warn=1, policy=True, sample=0,
             action="Clean and disinfect the equipment, mats and locker rooms, restock wipes, and fill in the log."),
        Rule(key="pool_chlorine", title="Pool chlorine in range",
             cost="Too little chlorine lets germs spread in the water, and a failed reading can close the pool.",
             citation="Your state and local pool code (limits vary); the CDC Model Aquatic Health Code (hot tubs need more"
                      " chlorine than pools)",
             kind="min",
             input="Free chlorine in each pool, in parts per million (leave it blank if you have no pool; set your"
                   " own minimum for a hot tub)", unit="ppm", limit=1, warn=1.5, policy=True, sample=2,
             action="Close the pool, adjust the chlorine, and test again before members swim."),
        Rule(citation="OSHA Hazard Communication, 29 CFR 1910.1200 (for a gym with employees)",
             cost="Pool and cleaning chemicals can burn skin and lungs; missing safety data sheets or training is a"
                  " common OSHA citation.",
             input="Is there a safety data sheet for every hazardous product (pool chemicals, cleaners,"
                   " disinfectants), and have staff been trained on them?",
             **_HAZCOM),
        Rule(key="membership_contracts", title="Membership contracts follow state law",
             cost="Contracts without the cancel rights your state requires can be voided, with refunds and state"
                  " attorney general penalties.",
             citation="State health club services laws (cancel periods and terms vary by state)", kind="required",
             input="Do membership contracts give the cancel rights, cooling-off period and terms your state's health"
                   " club law requires?",
             sample=True, policy=True,
             action="Have the contract checked against your state's law and update it before selling more"
                    " memberships."),
        Rule(**_EXTINGUISHER),
        Rule(key="first_aid_kit", title="First-aid kit stocked",
             cost="An empty first-aid kit slows help for sprains and cuts, and first-aid supplies are required for"
                  " employers.",
             citation="OSHA 29 CFR 1910.151(b) (for a gym with employees); good practice", kind="max",
             input="Days since the first-aid kit was last checked and restocked", unit="days", limit=30, warn=25,
             policy=True, sample=20,
             action="Restock the kit (bandages, cold packs, gloves) and note the date."),
        Rule(key="member_agreements", title="Member agreements on file",
             cost="Without a signed agreement on file, an injury claim is harder to answer and your insurer may"
                  " object.",
             citation="Your insurer's requirements; state contract law (good practice)", kind="required",
             input="Does every member have a signed membership agreement on file (and the health questionnaire, if"
                   " you use one)?",
             sample=True, policy=True,
             action="Collect the missing agreements at the front desk before those members' next visit."),
    ],
}
