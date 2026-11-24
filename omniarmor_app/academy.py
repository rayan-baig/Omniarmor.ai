# -*- coding: utf-8 -*-
"""Future Owner Academy: a game-like course for the kids who may one day run
the family company.

Four family tracks, each with its own progress (Track.total gives the real
level counts, which the pages show):
    Launchpad (Basic)          the 16 core worlds, lessons of 5 questions,
                               easy questions first.
    Trailblazer (Intermediate) all 43 worlds, lessons of 5.
    Summit (Advanced)          all 43 worlds, lessons of 6, hard questions
                               first and a higher pass mark.
    Titan Mastery              all 43 worlds, lessons of 8, hard questions
                               first and the highest pass mark.
Each also has the Owner's Challenge and 51-plus industry Rule Quests (one
lesson per real rule).

Every world is a fixed list of questions cut into lessons, so no question
comes back in a later lesson of the same world, and a world has only as many
lessons as it has questions for: the level count is what a learner really
plays. A retry asks the same lesson's questions, the options in a new order.
Lessons are built from the company's own name, industries and compliance
rules, so a child learns about the business they may inherit. The newer
worlds draw on the question banks in academy_bank. Quizzes are generated from
a seed, so the same attempt always shows the same questions and can be
checked on the server without storing the answers.

Children don't get accounts: a family member adds a learner profile with only
a nickname and a picture, so no child's personal information is collected. A
teacher adds a class the same way, by first name or nickname only
(classrooms.py).
"""

import dataclasses
import difflib
import functools
import itertools
import math
import random
import re
import secrets
from dataclasses import dataclass

from omni_armor_rules import CATALOG, evaluate
from omni_armor_rules.rule import _fmt as format_quantity

from .academy_bank import basics as _basics
from .academy_bank import load_expansions, load_worlds
from .academy_bank.sorting import SORT_SETS
from .academy_bank.word_ideas import WORD_IDEAS, kindred
from .academy_bank.word_use import CLASHES, GAP, WORD_SCENES, scene_picture
from .catalog import INDUSTRIES, counts_first_day, date_mode, date_unit
from .words import plural

PASS_RATE = 0.6
MAX_LEARNERS = 12

AVATARS = {
    "rocket": ("Rocket", "#E5261C"),
    "star": ("Star", "#F59234"),
    "bolt": ("Bolt", "#FFC24B"),
    "crown": ("Crown", "#4FD1A5"),
    "gem": ("Gem", "#5AB0F0"),
    "shield": ("Shield", "#C8231A"),
    "paw": ("Paw", "#E8B98A"),
    "leaf": ("Leaf", "#4FD1A5"),
    "planet": ("Planet", "#B79CFF"),
}

LIGHTS = ["Green: all good", "Yellow: careful, it's getting close", "Red: stop and fix it"]
LIGHT_INDEX = {"CLEARED": 0, "WARNING": 1, "BLOCKED": 2}
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

# Kid-friendly business vocabulary: (word, meaning).
GLOSSARY = [
    ("Revenue", "All the money customers pay the business."),
    ("Cost", "Money the business spends, like pay, supplies and rent."),
    ("Profit", "The money left over after paying all the costs."),
    ("Customer", "A person or company that buys from the business."),
    ("Employee", "A person the business pays to work there."),
    ("Invoice", "A bill that tells a customer how much they owe."),
    ("Budget", "A plan for how much money to spend on each thing."),
    ("Contract", "A written promise between two sides that both agree to."),
    ("Compliance", "Following the laws and rules that apply to the business."),
    ("Deadline", "The last day something must be done."),
    ("Inventory", "All the products and supplies the business has on hand."),
    ("Stakeholder", "Anyone who cares how the business does: owners, workers, customers and neighbors."),
    ("Inspector", "A person whose job is to check that rules are being followed."),
    ("Fine", "Money a business must pay as a penalty for breaking a rule."),
    ("Owner", "The person or family the business belongs to, who makes the big decisions."),
    ("Reputation", "What people think of the business, earned by how it acts."),
]

# Situations for practicing professional speech: (situation, best, not-so-good, not-so-good, why).
PRO_TALK = [
    ("You answer the company phone. What should you say?",
     "Good morning, thank you for calling {company}. How can I help you?",
     "Hello? Who is this and what do you need from us today?", "Yeah, this is the office. What is it?",
     "A friendly greeting with the company's name tells callers they reached the right place and that you're ready to help."),
    ("You're writing an email to a customer named Ms. Lopez. How should it start?",
     "Hello Ms. Lopez, thank you for your order,", "HEY MS. LOPEZ!!! GREAT NEWS FOR YOU!!!", "yo lopez, quick thing about your order",
     "Use the person's name and a polite greeting. All capital letters reads like shouting."),
    ("In a meeting, you disagree with an idea. What's the best thing to say?",
     "I see your point. Could we also think about another way?",
     "That idea is never going to work, and everyone here knows it.",
     "Say nothing now, then complain about it to coworkers after the meeting.",
     "You can disagree and still be respectful. Saying it kindly keeps the team working together."),
    ("You made a mistake on an order. What should you do?",
     "Tell your manager: \"I made a mistake. Here's how I'll fix it.\"",
     "Quietly fix it and hope the customer and your manager never find out about it.",
     "Explain that the system was confusing, so the mistake wasn't really your fault.",
     "Owning a mistake and offering a fix builds trust. Hiding it usually makes it bigger."),
    ("A customer asks a question and you don't know the answer. What do you say?",
     "I'm not sure, but I'll find out and get back to you by tomorrow morning.",
     "Give your best guess with a confident voice so you sound like an expert.",
     "Tell them that's not your department and they'll have to figure it out.",
     "It's fine not to know. Promise to find out, say when, and keep that promise."),
    ("A meeting is ending. What's a professional way to finish?",
     "Thanks for your time. I'll send a summary by Friday.",
     "Okay, I think we're done here, so I'm going to go now. Bye, everyone.",
     "Start packing up and leave while the last person is still talking.",
     "Thank people for their time and say what you'll do next and when."),
    ("Which sentence sounds the most professional?",
     "We will deliver all of the materials to your site on Monday morning.",
     "We'll probably bring all the stuff over to you sometime early next week, hopefully.",
     "Your things will get there whenever our truck has some free time.",
     "Clear words and a specific day help everyone plan."),
    ("You need help from a coworker who is busy. What do you say?",
     "When you have a minute, could you help me with this report?",
     "I need you to drop what you're doing and help me with this report right now.",
     "Keep walking over to their desk until they finally stop and answer you.",
     "Asking politely and respecting their time makes people glad to help."),
    ("How should you end a business email?",
     "Thank you for your time,\nSam Rivera, Sales", "Ok bye, talk later, have fun with the rest of your day lol", "Leave it with no ending or name at all",
     "A short thank-you and your name is polite and lets the reader know who wrote it."),
    ("A customer is upset about a late delivery. What's the best first thing to say?",
     "I'm sorry about the delay. Let me look into it now.",
     "That's not my fault. The delivery company is the one who made it late.",
     "Please calm down first, and then we can talk about whatever the problem is.",
     "Listening and apologizing first helps the customer feel heard, and then you can fix the problem."),
]


# Scenario pools for the leadership levels: (situation, best answer, weaker answer, weaker answer, why).
OWN_IT = [
    ("You forgot to send an order on time. What's the best thing to do?",
     "Tell the customer, apologize, and send it today",
     "Say the mail service must have lost it, so nobody gets upset with you",
     "Wait a few days and hope the customer doesn't notice it's late",
     "Owners own their mistakes. Fixing it fast and being honest keeps customers' trust."),
    ("A project you led didn't go well. What should you say to your team?",
     "That was my call. Here's what I learned and what we'll do next",
     "Some of you didn't do your parts well, and that's why it went wrong",
     "Say nothing about it and quickly move on to the next project",
     "Leaders take responsibility for results, good or bad."),
    ("You promised to finish something by Friday, but it will be late. When should you tell people?",
     "As soon as you know, with a new date",
     "On Friday afternoon, right when it was supposed to be done",
     "Never; just turn it in late and hope nobody remembers the date",
     "Early warnings let people plan. Surprises damage trust."),
    ("Who is responsible for a job getting done when you're the owner?",
     "You are, even when you hand it to someone",
     "Whoever you gave the job to, because it's their job now, not yours",
     "Nobody in particular, because big jobs are everyone's job",
     "You can share the work, but the owner is always responsible that it gets done."),
    ("Your room is messy and you have homework. What shows self-responsibility?",
     "Make a plan and do both without being reminded",
     "Wait until a grown-up tells you to do it, then do it right away",
     "Do the homework only, since the messy room isn't really a big deal",
     "Self-responsibility means doing what needs doing, even when nobody is watching."),
    ("You break a rule by accident at work. What's the right move?",
     "Report it, fix it, and learn how to prevent it",
     "Quietly fix it yourself so nobody has to find out it ever happened",
     "Explain that the rule is silly, so breaking it doesn't really matter",
     "Reporting problems quickly is how good companies stay safe and out of trouble."),
]
GRIT = [
    ("Your first idea for a new product doesn't sell. What do successful owners do?",
     "Ask customers why, improve it, and try again",
     "Decide business isn't for you and go find a different kind of job",
     "Keep selling it exactly the same way until customers change their minds",
     "Many famous companies failed many times before they found what worked."),
    ("A big customer says no. What's a strong response?",
     "Thank them, ask what would change their mind, and follow up later",
     "Call them every day until they finally get tired and say yes",
     "Cross them off your list and never contact them again",
     "Every no teaches you something. Persistent, polite follow-up wins deals."),
    ("Learning something new at work is hard. What helps most?",
     "Practice a little every day and ask for help",
     "Pretend you already know it so nobody thinks you're behind",
     "Stop after the first try, since some people just aren't good at things",
     "Skills grow with practice. Asking for help is smart, not weak."),
    ("What does perseverance mean?",
     "Not quitting when it gets tough",
     "Always choosing the easiest job so you never have to struggle",
     "Doing everything perfectly on the very first try, every time",
     "Perseverance is sticking with a goal through tough times."),
    ("Business is slow this month. What should the owner do?",
     "Stay calm, cut waste, and look for new customers",
     "Close the doors for good before things get any worse",
     "Do nothing and wait for customers to come back on their own",
     "Hard months happen. Steady owners plan their way through them."),
    ("You lose a game or a contest. What's the best mindset?",
     "Figure out what to practice for next time",
     "Decide you'll never enter a contest again, since losing feels bad",
     "Tell everyone the winner must have cheated to beat you",
     "Champions learn from losses. That habit makes great business owners too."),
]
RESPECT = [
    ("What makes people respect a leader the moment they meet them?",
     "Standing tall, making eye contact and speaking in a calm, clear voice",
     "Talking loudly over everyone so they know who's in charge",
     "Checking your phone so people see how busy and important you are",
     "Confident body language and calm words show you're ready to lead."),
    ("What builds respect that lasts?",
     "Keeping your promises every time, even the small ones nobody checks",
     "Reminding everyone of your big wins so they know how good you are",
     "Making people a little afraid of you so they always do what you say",
     "When people know you always do what you say, they respect and trust you."),
    ("Someone is rude to you in a meeting. What does a respected leader do?",
     "Stay calm and answer politely and firmly, without raising your voice",
     "Answer back even louder so everyone sees you won't be pushed around",
     "Get up and walk out of the room to show how upset you are",
     "Staying calm under pressure is one of the strongest signs of a leader."),
    ("How should a leader treat the newest, youngest worker?",
     "With the same respect and patience you show everyone else on the team",
     "Mostly ignore them until they've been there long enough to matter",
     "Give them all the boring jobs, since new people have to earn their place",
     "Leaders who respect everyone earn respect from everyone."),
    ("You walk into a room to speak to the team. What helps you look and sound like a leader?",
     "Be prepared, speak slowly and clearly, and look people in the eye",
     "Read every word from your phone so you don't forget anything important",
     "Arrive a few minutes late so everyone is already waiting for you",
     "Preparation is the secret behind confidence."),
    ("Which leader do people follow most?",
     "One who listens, decides fairly and gives the team credit for wins",
     "One who makes every decision alone and takes the credit for the wins",
     "One who changes their mind every day to keep everyone happy",
     "Fairness and giving credit make people want to follow you."),
]
HIRING = [
    ("When is a good time to hire a new person?",
     "When there's more steady work, week after week, than the team can handle",
     "Whenever a friend or relative asks you for a job, even if there's no work",
     "During one extra-busy week, even if it will be slow again next month",
     "Hire when the work and the money are there to support a new job."),
    ("What's the most important thing to look for in a new hire?",
     "Honesty, a good attitude and the right skills for the job you need done",
     "Whoever is a close friend, since you already know you'll get along",
     "Whoever asks for the lowest pay, no matter how well they do the job",
     "Skills can be taught; honesty and attitude are harder to change."),
    ("What should a good job interview include?",
     "The same fair, job-related questions for every single candidate",
     "Personal questions about their religion, family plans and age",
     "Different easy questions for the people you already like best",
     "Fair, job-related questions help you choose well and follow the law."),
    ("A new worker starts on Monday. What helps them succeed?",
     "A warm welcome, clear training, and a friendly buddy they can ask",
     "Leave them alone so they learn by figuring everything out themselves",
     "Give them the hardest job on day one to see if they can handle it",
     "Good training turns new hires into great teammates."),
    ("Before hiring, what should an owner check?",
     "That the business can afford the new person's pay every month",
     "That the new person likes the same music and sports as the team",
     "Nothing much, since you can always figure out the pay later",
     "A job is a promise to pay someone, so plan the budget first."),
    ("Two people apply. One has great skills but was rude to the receptionist. What should you think about?",
     "How they treat everyone, not just you, shows who they truly are",
     "Skills are all that matter, so rudeness to others doesn't count",
     "Being rude shows they're bold and will be tough with customers",
     "Watch how people treat others. It's how they'll treat your team and customers."),
]
TOUGH_CALLS = [
    ("A worker keeps arriving late. What should a good manager do first?",
     "Talk privately and agree on a plan to fix it",
     "Let them go right away so the rest of the team sees you mean business",
     "Tell the rest of the team about the problem so they can pressure them",
     "Clear, private feedback gives people a fair chance to improve."),
    ("When might an owner need to let someone go?",
     "When, after warnings and help, they still can't or won't do the job",
     "When they tell a joke you didn't like during a team lunch",
     "When a friend of yours needs a job and you want to open a spot",
     "Letting someone go is a last step, after coaching and clear warnings."),
    ("A worker is caught stealing from the company. What's the right response?",
     "Take it seriously, follow the rules and the law, and likely let them go",
     "Ignore it this time, since bringing it up would make things awkward",
     "Take the money out of their next paycheck without telling anyone",
     "Honesty and safety problems can't be ignored, because trust is everything."),
    ("If you must let someone go, how should you do it?",
     "Privately, respectfully and legally, with expert advice",
     "In front of the whole team so everyone learns a lesson from it",
     "With a short text message so you don't have to explain anything",
     "Even hard news should be delivered with respect and done the legal way."),
    ("Why do good managers write down warnings and coaching?",
     "So everything is clear, fair and documented",
     "So they can win any argument and get the worker in trouble later",
     "There's no real reason; it's just extra paperwork for managers",
     "Written records keep things fair and protect both the worker and the company."),
    ("A worker is struggling because the job changed. What's a smart first step?",
     "Offer training for the new skills",
     "Let them go right away and hire someone who already knows the new way",
     "Pretend the job didn't change and hope they catch up on their own",
     "Often the best move is helping a good person grow into the new job."),
]
CUSTOMERS = [
    ("What makes customers come back again and again?",
     "Great quality, friendly service and promises that are always kept",
     "The lowest prices in town, even if the service is rude and slow",
     "Lots of flashy ads, even if the product often breaks quickly",
     "Happy customers return and tell their friends."),
    ("A customer has a complaint. What's the best way to handle it?",
     "Listen, apologize, fix it fast and thank them for telling you",
     "Explain why they're wrong until they agree and leave you alone",
     "Leave the message unanswered and hope they forget about it",
     "A well-handled complaint can turn an upset customer into a loyal fan."),
    ("How can a business find out what customers want?",
     "Ask them, listen closely, and watch what they buy and return",
     "Guess based on what the owner personally likes best",
     "Copy whatever the biggest company in town is selling this year",
     "The best ideas often come straight from customers."),
    ("What is word of mouth?",
     "Customers telling friends and family about the business",
     "A special kind of ad that plays on the radio every morning",
     "A secret password customers say to get a discount",
     "Word of mouth is free advertising earned by treating people well."),
    ("A loyal customer has ordered for five years. What's a smart move?",
     "Thank them and offer something special to show you noticed",
     "Raise their prices, since they'll probably keep ordering anyway",
     "Treat them like any new customer so everything stays fair",
     "Keeping a customer is usually cheaper than finding a new one."),
    ("What should a business promise in its ads?",
     "Only what it can truly deliver, every single time, to everyone",
     "Whatever sounds most exciting, even if it isn't quite true",
     "Free gifts forever, so lots of new customers come in the door",
     "Honest ads build trust, and false ads can break the law."),
]
COMPETE = [
    ("A rival company opens across the street. What's the strongest move?",
     "Be better: quality, speed and happy customers",
     "Tell customers untrue stories about the rival so they stay away",
     "Cut every price in half, even if you lose money on each sale",
     "You win customers by being the best choice, not by cheating."),
    ("How can a small company beat a bigger one?",
     "Be the very best at something they do poorly",
     "Copy everything the big company does, exactly the same way",
     "Give up, because big companies always win in the end",
     "Focusing on a special strength lets small companies win big."),
    ("Your competitor cuts prices. What's a smart way to respond?",
     "Show customers your extra value",
     "Cut your prices even lower, even if you lose money on every sale",
     "Post angry comments about them online so people stop going there",
     "Racing to the bottom on price can sink both companies. Compete on value."),
    ("Is it okay to secretly agree with a rival to charge the same high prices?",
     "No, that's price fixing and it's illegal",
     "Yes, it's a clever trick that helps both companies earn more",
     "Yes, as long as you only do it for a few months at a time",
     "Competitors must set prices on their own. Price fixing brings huge fines."),
    ("What is innovation?",
     "New and better ways to do things",
     "Doing everything exactly the way it has always been done before",
     "Copying a rival's logo and name so customers get confused",
     "Innovators stay ahead because they keep improving."),
    ("How can you learn from a competitor fairly?",
     "Study their public ads, products and reviews",
     "Get one of their workers to secretly share their private files",
     "Pretend to be a customer to trick them into giving away secrets",
     "Learn openly, then out-work and out-think them."),
    ("What's the best way to dominate your field?",
     "Be the company customers trust most",
     "Scare customers into staying by saying other companies are dangerous",
     "Hide your real prices so customers can't compare you to others",
     "Trust is the strongest advantage a company can build."),
]
MOVES = [
    ("You're buying supplies. What's a professional way to negotiate?",
     "Know your budget, ask politely, be ready to walk away",
     "Demand the supplies for free and threaten to tell everyone if they say no",
     "Accept the very first price they give you so you seem easy to work with",
     "Good negotiators prepare, stay polite, and know their limit."),
    ("Before signing a contract, what should you do?",
     "Read it all and ask an expert about anything unclear",
     "Sign it quickly before the other side changes their mind",
     "Read just the first page, since the rest is usually the same",
     "A contract is a promise. Know exactly what you're agreeing to."),
    ("Why should a business save money for a rainy day?",
     "To get through slow months and handle surprises without panic",
     "Saving is pointless, because spending money is how a business grows",
     "So the owner can secretly hide it from the team and the bank",
     "An emergency fund keeps the company safe when things go wrong."),
    ("A big decision is coming up. What's a smart way to decide?",
     "Gather facts, weigh pros and cons, ask advisors",
     "Flip a coin, since big decisions are mostly about luck anyway",
     "Do whatever the loudest person in the room says you should do",
     "Good decisions come from good information."),
    ("A deal sounds too good to be true. What should you do?",
     "Slow down and check every detail carefully before you agree",
     "Say yes right away before someone else grabs the great deal",
     "Send them the money they ask for to show you're serious",
     "If it seems too good to be true, it often is."),
    ("What is a goal that helps a business grow?",
     "\"10 new customers by June\"",
     "\"Do a little better someday, whenever we get the chance\"",
     "\"Have no goals, so nobody feels disappointed later\"",
     "Specific goals with deadlines turn dreams into plans."),
    ("Someone asks for a favor that would break a company rule. What's a pro move?",
     "Politely say no and explain the rule you have to follow",
     "Say yes this one time so they keep liking you",
     "Ignore their message and hope they never ask about it again",
     "Saying a respectful no protects you and the company."),
]


# A choice question that sets a scene and asks what to do (1.18.0): the quiz
# shows it as a scenario, with its own look.
SCENARIO = re.compile(
    r"\b(what (should|would|could|do) you|what('s| is) (the )?(best|smartest|right|fair|honest|safest|professional)"
    r"|how should you|what do you (say|do)|best first step|best way to|which is the (best|right|fairest) (move|thing))\b",
    re.I)


@dataclass
class Question:
    prompt: str
    options: list
    answer: int
    explain: str
    kind: str = "choice"  # "choice", "light", "truefalse", or (1.18.0) "match" and "sort"
    review: bool = False
    # 1.18.0: a match or sort question's pieces, for the page: {"title", "left",
    # "right", "codes"} (match: each word, then each idea; codes: which idea
    # each word goes with) or {"title", "items", "bins", "codes"} (sort: which
    # bin each item goes in). One option per code, so it is graded like any
    # other question: one right option.
    parts: object = None
    look: str = ""        # "scenario": a choice question that sets a scene

    def __post_init__(self):
        if not self.look and self.kind == "choice" and SCENARIO.search(self.prompt):
            self.look = "scenario"


@dataclass(frozen=True)
class World:
    number: int
    key: str
    title: str
    tagline: str
    icon: str
    kind: str = "topic"  # "topic", "final" or "industry"
    industry_id: int = 0
    unit: str = ""


# Units group the topic worlds on the map, in teaching order.
UNITS = [
    ("foundations", "Foundations"), ("leadership", "Leadership"), ("money", "Money and Finance"),
    ("growth", "Growth"), ("operations", "Operations"), ("mindset", "Mindset"),
    ("trust", "Rules and Trust"), ("bigpicture", "The Big Picture"), ("champion", "Winning Mindset"),
]
UNIT_NAMES = dict(UNITS)

ORIGINAL_WORLDS = [
    World(1, "company", "Meet Your Company", "What the family business does", "building", unit="foundations"),
    World(2, "words", "Business Words", "The words grown-ups use at work", "book", unit="foundations"),
    World(3, "rules", "Why Rules Matter", "Rules keep people safe", "scale", unit="foundations"),
    World(4, "lights", "Stop, Careful, Go", "Read the company's signals", "light", unit="foundations"),
    World(5, "calendar", "Countdown Calendar", "Deadlines and reminders", "calendar", unit="foundations"),
    World(6, "money", "Money Smarts", "Revenue, costs and profit", "coin", unit="foundations"),
    World(7, "talk", "Talk Like a Pro", "Speak and write professionally", "chat", unit="foundations"),
    World(8, "team", "Lead the Team", "How good owners lead", "team", unit="foundations"),
    World(9, "ownit", "Own It", "Taking responsibility", "shield", unit="leadership"),
    World(10, "grit", "Never Give Up", "Perseverance", "mountain", unit="leadership"),
    World(11, "respect", "Earn Instant Respect", "Confidence people trust", "star", unit="leadership"),
    World(12, "hiring", "Build Your Dream Team", "When and how to hire", "plus", unit="leadership"),
    World(13, "toughcalls", "Tough Calls", "When to let someone go", "door", unit="leadership"),
    World(14, "customers", "Win Customers", "Make people want to come back", "heart", unit="leadership"),
    World(15, "compete", "Beat the Competition", "Win your field, fair and square", "rocket", unit="leadership"),
    World(16, "moves", "Pro Business Moves", "Negotiate, plan and decide", "chess", unit="leadership"),
]
FINAL_WORLD = World(17, "final", "Owner's Challenge", "Earn and upgrade your certificate", "trophy", "final")
BANK_WORLD_BASE = 18  # worlds from academy_bank are numbered from here
_BANK = {}             # world key -> its bank entry (cards, questions, facts)
BANK_WORLDS = []
for _n, _entry in enumerate(load_worlds()):
    _BANK[_entry["key"]] = _entry
    BANK_WORLDS.append(World(BANK_WORLD_BASE + _n, _entry["key"], _entry["title"], _entry["tagline"],
                             _entry["icon"], unit=_entry["unit"]))
TOPIC_WORLDS = ORIGINAL_WORLDS + BANK_WORLDS
INDUSTRY_WORLD_BASE = 100
INDUSTRY_WORLDS = [
    World(INDUSTRY_WORLD_BASE + i, f"industry-{i}", f"{info['brand']} Rule Quest", info["sector"], "scale",
          "industry", i)
    for i, info in INDUSTRIES.items()
]
# Worlds only the Classroom track has (see "The Classroom track" below): the
# same lessons as the first worlds, told through the class's own pretend
# business instead of a family company.
CLASS_WORLDS = [
    World(60, "classstand", "Meet the Class Stand", "The pretend lemonade stand your class runs", "building",
          unit="foundations"),
    World(61, "classrules", "Rules at the Stand", "Rules that keep customers safe", "scale", unit="foundations"),
    World(62, "classmoney", "Money at the Stand", "Sales, costs and what's left over", "coin", unit="foundations"),
    World(63, "classteam", "Work as a Team", "Sharing jobs, listening and deciding together", "team",
          unit="leadership"),
]
ALL_WORLDS = TOPIC_WORLDS + CLASS_WORLDS + [FINAL_WORLD] + INDUSTRY_WORLDS
WORLDS = {w.number: w for w in ALL_WORLDS}
INDUSTRY_UNLOCK_WORLD = 4  # industry worlds open after the traffic-light lesson


@dataclass(frozen=True)
class Track:
    """A path through the Academy. Bigger tracks add worlds, stages and
    harder quizzes; each keeps its own progress."""
    key: str
    index: int
    name: str
    level: str          # Basic, Intermediate, Advanced or Mastery
    tagline: str
    emblem: str
    topics: tuple       # topic world numbers, in unlock order
    topic_stages: int
    final_stages: int
    industry_stages: int
    min_questions: int
    max_questions: int
    pass_low: float     # pass rate early in a world
    pass_high: float    # pass rate late in a world
    final_questions: int
    industry_questions: int
    mix: tuple          # ((progress up to, {difficulty: weight}), ...) for question banks
    stage_plan: tuple = ()   # ((world number, stages), ...): worlds with their own stage count

    @property
    def topic_worlds(self):
        return [WORLDS[n] for n in self.topics]

    @property
    def topic_lessons(self):
        return sum(self.stages(w) for w in self.topic_worlds)

    @property
    def rule_quests(self):
        """Whether the track has the industry Rule Quests (the Classroom track has none)."""
        return self.industry_stages > 0

    @property
    def worlds(self):
        return self.topic_worlds + [FINAL_WORLD] + (INDUSTRY_WORLDS if self.rule_quests else [])

    @property
    def lessons(self):
        """The business lessons: every topic world and the Owner's (or Class)
        Challenge, without the Rule Quests. The one count every page shows
        (the Academy home, the track picker and the map); the Rule Quests are
        shown apart (quests_for), one per industry."""
        return self.topic_lessons + self.final_stages

    def quests_for(self, industry_ids):
        """How many Rule Quests a workspace's learners have on this track: one
        for each of its own industries (none on the Classroom track). The
        pages show them apart from the lessons, as "+N Rule Quests"; another
        industry's Rule Quest is an optional extra on the map."""
        return len({i for i in industry_ids if i in INDUSTRIES}) if self.rule_quests else 0

    def lessons_done(self, passed):
        """How many of the business lessons (Track.lessons) a set of passed
        level ids holds: the one count every page shows ("4 / 90 lessons")."""
        counted = {w.number for w in self.topic_worlds} | {FINAL_WORLD.number}
        return sum(1 for lid in passed if lid // 1_000_000 == self.index and (lid % 1_000_000) // 1000 in counted
                   and level_exists(self, lid))

    @property
    def total(self):
        return (sum(self.stages(w) for w in self.topic_worlds) + self.final_stages
                + len(INDUSTRY_WORLDS) * self.industry_stages)

    def reachable(self, quests=None):
        """The levels a learner here can pass for ranks and certificates (1.22.0): the business lessons and the
        workspace's own Rule Quests (quests: how many it has, Track.quests_for; None when no workspace is
        known, the lessons only). Track.total also counts every other industry's Rule Quest, optional extras
        on the map, so a family's ladder used to list ranks no learner would get to (Launchpad: "Tycoon, at
        630 lessons" for a workspace with 100). The Classroom track has no Rule Quests: its lessons."""
        if not self.rule_quests:
            return self.total
        return self.lessons + max(0, int(quests or 0)) * self.industry_stages

    def stages(self, w):
        if w.kind == "final":
            return self.final_stages
        if w.kind == "industry":
            return self.industry_stages
        return dict(self.stage_plan).get(w.number, self.topic_stages)

    def has(self, w):
        if w.kind == "industry":
            return self.rule_quests
        return w.kind != "topic" or w.number in self.topics


_ALL_TOPICS = tuple(w.number for w in TOPIC_WORLDS)
_EASY_MIX = ((0.3, {1: 3, 2: 2, 3: 0}), (0.7, {1: 1, 2: 2, 3: 1}), (1.01, {1: 0, 2: 2, 3: 2}))
_HARD_MIX = ((0.25, {1: 2, 2: 2, 3: 1}), (0.6, {1: 0, 2: 2, 3: 2}), (1.01, {1: 0, 2: 1, 3: 3}))
FAMILY_MAX_LESSONS = 10   # lessons a family world has at most (topic_stages); fewer when it has fewer questions
# A family track's stage_plan (each world's real lesson count) is filled in
# once the question pools are defined, at the end of this module.
TRACK_LIST = [
    Track("launchpad", 0, "Launchpad", "Basic", "Blast off with the basics", "rocket",
          tuple(w.number for w in ORIGINAL_WORLDS), FAMILY_MAX_LESSONS, 3, 10, 5, 5, 0.6, 0.8, 10, 5, _EASY_MIX),
    Track("trailblazer", 1, "Trailblazer", "Intermediate", "Every world of business", "flame",
          _ALL_TOPICS, FAMILY_MAX_LESSONS, 5, 10, 5, 5, 0.6, 0.8, 10, 5, _EASY_MIX),
    Track("summit", 2, "Summit", "Advanced", "Bigger lessons, hard questions first", "peak",
          _ALL_TOPICS, FAMILY_MAX_LESSONS, 5, 10, 6, 6, 0.7, 0.85, 12, 6, _HARD_MIX),
    Track("titan", 3, "Titan Mastery", "Mastery", "Long lessons and the highest pass marks", "titan",
          _ALL_TOPICS, FAMILY_MAX_LESSONS, 5, 10, 8, 8, 0.75, 0.9, 15, 8, _HARD_MIX),
]
TRACKS = {t.key: t for t in TRACK_LIST}
DEFAULT_TRACK = "launchpad"
TOTAL_LEVELS = TRACKS[DEFAULT_TRACK].total  # the basic track; see Track.total for the others
# 1.22.0: the sixth rank is "Chief Executive" (it was "Future Owner", the certificate's own name, so a learner
# with both read "Future Owner · Future Owner").
RANKS = [(0, "Rookie"), (5, "Apprentice"), (15, "Team Captain"), (40, "Manager"), (100, "Executive"),
         (250, "Chief Executive"), (600, "Business Legend"), (1000, "Tycoon")]
# The size the goals above (and CERTIFICATES') are written for: the Launchpad track with every industry's Rule
# Quests, as it was when they were set. Each track's goals are scaled from it to the levels it really has
# (Track.reachable), so the Classroom's ladder is the one 1.19.0 gave it.
RANK_BASE = 630
# 1.22.0: the top one is "Platinum Future Owner", like the others (it was "Platinum Business Legend", a rank's name).
CERTIFICATES = [(1, "Future Owner"), (100, "Silver Future Owner"), (500, "Gold Future Owner"),
                (None, "Platinum Future Owner")]


def track(key):
    return TRACKS.get(key) or TRACKS[DEFAULT_TRACK]


def world(number):
    return WORLDS.get(number)


def level_id(t, world_number, stage):
    """One number per level, for storing progress. Each track has its own range."""
    return t.index * 1_000_000 + world_number * 1000 + stage


def is_boss(t, w, stage):
    """A family world's last lesson is its boss round, with the world's
    highest pass mark, when the world has three lessons or more."""
    return (w.kind == "topic" and t.key != CLASSROOM_KEY and t.stages(w) >= 3 and stage == t.stages(w))


def question_count(t, w, stage):
    """How many questions the lesson has: a Rule Quest's lesson is its rule's
    questions, which can be fewer than the track asks for."""
    if w.kind == "final":
        return t.final_questions
    if w.kind == "industry":
        return len(_industry_lesson(t, w.industry_id, stage))
    return t.min_questions


def pass_rate(t, w, stage):
    if w.kind == "industry":
        return t.pass_low
    share = stage / t.stages(w)
    if share <= 0.2:
        return t.pass_low
    if share <= 0.6:
        return round((t.pass_low + t.pass_high) / 2, 4)
    return t.pass_high


def stars_for(score, total, needed=PASS_RATE):
    if total == 0:
        return 0
    rate = score / total
    if rate >= 1:
        return 3
    if rate >= max(0.8, needed + 0.1):
        return 2
    if rate >= needed:
        return 1
    return 0


def pass_mark(t, w, stage):
    """Right answers needed to pass."""
    return math.ceil(round(pass_rate(t, w, stage) * question_count(t, w, stage), 6))


def unlocked(t, w, stage, passed):
    """passed is the set of level ids with at least one star."""
    if not t.has(w) or not 1 <= stage <= t.stages(w):
        return False
    if stage > 1:
        return level_id(t, w.number, stage - 1) in passed
    if w.kind == "topic":
        position = t.topics.index(w.number)
        return position == 0 or level_id(t, t.topics[position - 1], 1) in passed
    if w.kind == "final":
        return all(level_id(t, n, 1) in passed for n in t.topics)
    return level_id(t, INDUSTRY_UNLOCK_WORLD, 1) in passed


def _title_for(table, count):
    name = None
    for needed, title in table:
        if count >= needed:
            name = title
    return name


def _scaled(t, table, quests=None):
    """Rank and certificate goals grow with the levels a learner can pass here (Track.reachable: the track's
    lessons and the workspace's own Rule Quests). Each goal stays above the one before, so a short track still
    starts at the first title, and none is past the last level: the goals that would be are spread evenly up to
    it, the last at it (1.19.0 for the Classroom track; 1.22.0 for the family tracks, whose ladder counted
    every industry's Rule Quests)."""
    total = t.reachable(quests)
    if table is RANKS and t.rule_quests:
        # 1.23.0: a family's ranks are spaced evenly over the levels its workspace has (Launchpad with one
        # industry: 0, 14, 29, 43, 57, 71, 86, 100), not 1, 2, 6, 16, 40, 95 and 100, five ranks in the first
        # fifth and then a long wait. The Classroom track keeps 1.19.0's ladder.
        steps = len(table) - 1
        return [(round(total * k / steps), title) for k, (_, title) in enumerate(table)]
    scale = total / RANK_BASE
    out, last = [], None
    for needed, title in table:
        goal = total if needed is None else (needed if needed <= 1 else round(needed * scale))
        if last is not None and needed is not None:
            goal = max(goal, last + 1)
        out.append((goal, title))
        last = goal
    over = next((i for i, (goal, _) in enumerate(out) if goal > total), None)
    if over is not None and over > 0:
        base, left = out[over - 1][0], len(out) - over
        for k, i in enumerate(range(over, len(out)), start=1):
            out[i] = (min(total, base + max(k, round((total - base) * k / left))), out[i][1])
    return out


RANK_TIERS = [title for _, title in RANKS]


# quests, below: how many Rule Quests the learner's workspace has on the track (Track.quests_for; None: no
# workspace known, the lessons only). Ranks and certificates count every level passed, Rule Quests too.

def rank_for(levels_done, t=None, quests=None):
    return _title_for(_scaled(t or TRACKS[DEFAULT_TRACK], RANKS, quests), levels_done)


def rank_tier(levels_done, t=None, quests=None):
    """0 for Rookie up to 7 for Tycoon: how fancy the learner's picture gets."""
    return RANK_TIERS.index(rank_for(levels_done, t, quests))


def rank_ladder(t=None, quests=None):
    """Every rank on a track, in order, as (lessons needed, title): the forms a
    learner's picture grows through on the map (1.16.0)."""
    return _scaled(t or TRACKS[DEFAULT_TRACK], RANKS, quests)


def next_rank(levels_done, t=None, quests=None):
    for needed, title in _scaled(t or TRACKS[DEFAULT_TRACK], RANKS, quests):
        if levels_done < needed:
            return needed, title
    return None


def certificate_goals(t, quests=None):
    """Each certificate's goal, in levels passed: (levels, title). The first comes with the Owner's (or Class)
    Challenge, which needs the first lesson of every world and the Challenge itself (len(t.topics) + 1). The
    upgrades are spread from there to the last level as CERTIFICATES spreads them over RANK_BASE (1.22.0: scaled
    from 0, Silver came with the Challenge itself on every track, so the first certificate was never seen)."""
    total, first = t.reachable(quests), len(t.topics) + 1
    out, last = [], None
    for needed, title in CERTIFICATES:
        if needed is None:
            goal = total
        elif needed <= 1:
            goal = needed
        else:
            goal = first + round((needed - 1) / (RANK_BASE - 1) * (total - first))
        if last is not None:
            goal = max(goal, last + 1)
        out.append((min(goal, total), title))
        last = goal
    return out


def certificates_for(levels_done, final_passed, t=None, quests=None):
    """Every certificate earned, in the order they are awarded (1.23.0): the Future Owner certificate always
    first, then Silver, Gold and Platinum. Passing the Challenge late, past Silver's goal, earns the Future Owner
    certificate and Silver at once, shown in that order (it used to show only Silver)."""
    t = t or TRACKS[DEFAULT_TRACK]
    if not final_passed:
        return []
    goals = certificate_goals(t, quests)
    earned = [title for goal, title in goals if levels_done >= goal] or [goals[0][1]]
    return [title if t.key == DEFAULT_TRACK else f"{t.name} {title}" for title in earned]


def certificate_for(levels_done, final_passed, t=None, quests=None):
    """The highest certificate earned (the one the certificate page prints), or None."""
    earned = certificates_for(levels_done, final_passed, t, quests)
    return earned[-1] if earned else None


def money(n):
    return f"${n:,}"


# ---------------------------------------------------------------------------
# Building questions
# ---------------------------------------------------------------------------

def _choice(rng, prompt, correct, wrong, explain):
    options = [correct] + [w for w in dict.fromkeys(wrong) if w != correct]
    rng.shuffle(options)
    return Question(prompt, options, options.index(correct), explain)


def _truefalse(prompt, truth, explain):
    return Question(prompt, ["True", "False"], 0 if truth else 1, explain, "truefalse")


def _sectors(industry_ids):
    return [INDUSTRIES[i]["sector"] for i in industry_ids]


def _company_rules(industry_ids):
    """The company's rules; the whole catalog when the company has none of a kind."""
    return [r for i in industry_ids for r in CATALOG[i]]


def _all_rules():
    return [r for rules in CATALOG.values() for r in rules]


def _nice(value):
    if abs(value) >= 10:
        return int(round(value))
    return round(value, 1)


def _light_cases(rule):
    """Example readings for a number rule, each checked with the real engine."""
    lim, warn = rule.limit, rule.warn
    step = max(1.0, abs(lim) * 0.25)
    if rule.kind == "max":
        candidates = [lim - 2 * step, warn, lim + step]
    else:
        candidates = [lim + 2 * step + ((warn - lim) if warn is not None else 0), warn, lim - step]
    cases = {}
    for value in candidates:
        if value is None:
            continue
        value = _nice(value)
        if value < 0:
            continue
        found = evaluate(rule, value)[0]
        cases.setdefault(found, value)
    return cases


def _light_rules(pool):
    return [r for r in pool if r.kind in ("max", "min") and date_unit(r) != "days" and r.unit and _light_cases(r)]


def _since_rules(pool):
    return [r for r in pool if _counts_days_since(r) and 7 <= r.limit <= 3650]


def _counts_days_since(rule):
    """Rules counted in days since something happened (the calendar questions say "days").
    Not one that counts its first day as day 1: "done 3 days ago" is its day 4."""
    return date_mode(rule) == "since" and date_unit(rule) == "days" and not counts_first_day(rule)


def _light_question(rule, value, found):
    word = "limit" if rule.kind == "max" else "minimum"
    explain = {
        "CLEARED": "The reading is safely inside the rule, so the light is green.",
        "WARNING": "The reading is close to the rule's edge, so the light is yellow: plan a fix before it becomes a problem.",
        "BLOCKED": "The reading is past the rule's edge, so the light is red: stop and fix it right away.",
    }[found]
    prompt = (f"Rule: {rule.title}. The {word} is {format_quantity(rule.limit, rule.unit)}. "
              f"Today's reading is {format_quantity(value, rule.unit)}. Which light should Aegizyn show?")
    return Question(prompt, list(LIGHTS), LIGHT_INDEX[found], explain, "light")


# True-or-false facts for the first worlds, true and false mixed, so the
# answer isn't always the same one: (statement, is it true, why).
COMPANY_FACTS = [
    ("Following the rules helps keep workers and customers safe.", True,
     "Rules protect the people who work at the company and the people it serves."),
    ("Customers are the people who pay a business for what it makes or does.", True,
     "Customers buy the products or the work. Without them there is no business."),
    ("A business only has to follow the rules when an inspector is watching.", False,
     "Rules count every day, not only on inspection day. Accidents don't wait for inspectors."),
    ("A business can skip a safety rule on a very busy day.", False,
     "Busy days are when accidents happen most. Safety rules count every day."),
]
RULE_FACTS = [
    ("It's smart to fix a problem as soon as you find it.", True,
     "Small problems are cheaper and safer to fix early, before they grow."),
    ("Writing down when a check was done helps show the rule was followed.", True,
     "A record proves the work was done, so an inspector can see it."),
    ("A small problem is best left alone until it gets bigger.", False,
     "Small problems grow. Fixing them early is cheaper and safer."),
    ("If nobody complains, breaking a rule doesn't matter.", False,
     "A broken rule can still hurt someone or bring a fine, even when nobody has noticed yet."),
]
TEAM_FACTS = [
    ("A good owner hides mistakes from the team.", False,
     "Good owners are honest about mistakes and fix them together."),
    ("A good leader only listens to people who agree with them.", False,
     "Leaders learn the most from people who see things differently."),
    ("Good owners own up to mistakes and fix them with the team.", True,
     "Being honest about a mistake earns trust and gets it fixed sooner."),
    ("Listening to workers' worries helps keep everyone safe.", True,
     "Workers often spot a problem first. Listening lets it be fixed early."),
]


# --- Level 1 ------------------------------------------------------------

def _company_story(company, industry_ids):
    sectors = ", ".join(s.lower() for s in _sectors(industry_ids))
    return [
        ("Hi, I'm Armo!", f"I'm a shield, and my job is helping {company} follow the rules that keep everyone safe."),
        ("Your family's company", f"{company} works in {sectors}. Customers count on it to do that work safely and well."),
        ("What is a business?", "A business is a group of people who make something or do work that others pay for."),
        ("Your adventure", f"Someday you might help lead {company}. Let's get you ready, one level at a time!"),
    ]


# --- Level 2 ------------------------------------------------------------

def _words_story(company, industry_ids):
    sample = GLOSSARY[:6]
    return [
        ("Talk like a business person", "Every job has its own words. Learning them helps you understand meetings, emails and reports."),
    ] + [(word, meaning) for word, meaning in sample] + [
        ("Your Word Bank", "You can find every word in the Word Bank on your level map anytime."),
    ]


# --- Level 3 ------------------------------------------------------------

def _rules_story(company, industry_ids):
    rule = _company_rules(industry_ids)[0]
    return [
        ("Rules are like game rules", "Games are fair and fun because everyone follows the same rules. Businesses work the same way."),
        ("Who makes them?", "Governments write rules to keep workers, customers and neighbors safe. Inspectors check them."),
        ("A real one", f"One of {company}'s rules: \"{rule.title}.\" Aegizyn keeps an eye on it every day."),
        ("Why it matters", "Breaking a rule can mean a fine (money paid as a penalty), losing customers, or someone getting hurt."),
    ]


# --- Level 4 ------------------------------------------------------------

def _lights_story(company, industry_ids):
    return [
        ("Three lights", "Aegizyn checks every rule and shows a light, just like a traffic light."),
        ("Green", "All good! The reading is safely inside the rule."),
        ("Yellow", "Careful! It's getting close to the limit. Time to plan a fix."),
        ("Red", "Stop! The rule is broken. Fix it right away to protect people and avoid a fine."),
    ]


# --- Level 5 ------------------------------------------------------------

def _calendar_story(company, industry_ids):
    pool = _since_rules(_company_rules(industry_ids)) or _since_rules(_all_rules())
    example = pool[0]
    return [
        ("Jobs that repeat", "Lots of jobs must be done again and again, like checking safety gear every year."),
        ("A real example", f"\"{example.title}\" has to be done at least every {plural(int(example.limit), 'day')}."),
        ("Counting days", "Aegizyn counts the days since a job was last done, so nobody has to remember."),
        ("Friendly reminders", "It sends reminders 30, 7 and 1 day before a deadline, so the team is never surprised."),
    ]


# --- Level 6 ------------------------------------------------------------

def _money_story(company, industry_ids):
    return [
        ("Revenue", "Revenue is all the money customers pay the business."),
        ("Costs", "Costs are what the business spends: pay for workers, supplies, rent and more."),
        ("Profit", "Profit is the money left over after paying all the costs: revenue minus costs. Healthy businesses make a profit."),
        ("Surprise costs", "Fines are costs nobody plans for. Following the rules protects the profit."),
    ]


# --- Level 7 ------------------------------------------------------------

def _talk_story(company, industry_ids):
    return [
        ("Speak like a pro", "How you talk at work shapes the company's reputation: what people think of it."),
        ("Be polite", "Say please, thank you and the person's name. Kind words open doors."),
        ("Listen first", "Let people finish. Then answer. Listening shows respect."),
        ("Be clear", "Say exactly what you'll do and when: \"I'll send it by Friday.\""),
        ("Great emails", "Start with a greeting, make your point in a few sentences, say thank you, and sign your name."),
        ("Own mistakes", "Everyone makes mistakes. Saying \"I'll fix it\" earns trust."),
    ]


# --- Level 8 ------------------------------------------------------------

def _team_story(company, industry_ids):
    return [
        ("Owners lead people", f"A business is its people. Leading {company} means helping the team do great work."),
        ("Listen", "Good leaders listen to workers and customers, especially when they raise a problem."),
        ("Keep records", "Aegizyn's audit trail remembers who changed what, and when. That keeps everyone honest."),
        ("Ask for help", "Great owners ask experts for advice: lawyers, accountants and experienced workers."),
    ]


# --- More words, situations and scenarios from academy_bank/expansions.py ---

_more = load_expansions()
if _more is not None:
    GLOSSARY.extend(_more.GLOSSARY_MORE)
    PRO_TALK.extend(_more.PRO_TALK_MORE)
    for _name in ("OWN_IT", "GRIT", "RESPECT", "HIRING", "TOUGH_CALLS", "CUSTOMERS", "COMPETE", "MOVES"):
        globals()[_name].extend(getattr(_more, f"{_name}_MORE", []))


# --- Levels 9 to 16: leadership --------------------------------------------

def _cards(*pairs):
    def make(company, industry_ids):
        return [(title, text.format(company=company)) for title, text in pairs]
    return make


_ownit_story = _cards(
    ("Own it", "Self-responsibility means doing what you said you'd do, without anyone reminding you."),
    ("Mistakes happen", "Everyone makes mistakes. Owners say \"That's on me,\" fix it, and learn from it."),
    ("The owner's promise", "At {company}, the owner is responsible for everything, even jobs handed to others."),
)
_grit_story = _cards(
    ("Never give up", "Perseverance means keeping going when things get hard."),
    ("Failing forward", "Many famous businesses failed many times before they succeeded. Each try taught them something."),
    ("Steady wins", "Owners who stay calm in hard times and keep improving are the ones still standing later."),
)
_respect_story = _cards(
    ("Instant respect", "People decide quickly whether to trust a leader. Stand tall, look people in the eye, and speak calmly and clearly."),
    ("Lasting respect", "The respect that lasts comes from keeping promises, being fair and treating everyone well."),
    ("Calm is powerful", "Leaders who stay calm when others panic are the ones people look to."),
    ("Prepare", "Confidence comes from preparation. Know your stuff before you walk into the room."),
)
_hiring_story = _cards(
    ("Growing the team", "When there's more steady work than the team can handle, it may be time to hire."),
    ("Pick well", "Look for honesty, a great attitude and the right skills. Skills can be taught; character is harder."),
    ("Be fair", "Ask every candidate the same job-related questions. Fair hiring is the law, and it finds the best people."),
    ("Welcome them", "Great training and a friendly welcome help new people succeed fast."),
)
_toughcalls_story = _cards(
    ("Tough calls", "Sometimes a worker isn't doing the job. Good managers talk privately first and help them improve."),
    ("Warnings and records", "Clear feedback, written down, keeps things fair for everyone."),
    ("The last step", "If someone still can't or won't do the job, or breaks trust, letting them go may be the right call."),
    ("Do it right", "Do it privately, respectfully and legally, with advice from an expert."),
)
_customers_story = _cards(
    ("Customers are everything", "Without customers, there is no business. Every job at {company} serves them."),
    ("Keep them coming back", "Great quality, friendly service and kept promises turn customers into fans."),
    ("Complaints are gifts", "A complaint tells you how to get better. Fix it fast and say thank you."),
)
_compete_story = _cards(
    ("Rivals", "Other companies want the same customers. That's competition, and it pushes everyone to get better."),
    ("Win by being better", "The strongest move is to be the best choice: better quality, faster service, new ideas."),
    ("Find your edge", "Be the very best at something special. That's how small companies beat big ones."),
    ("Play fair", "Lying about rivals, stealing secrets or secretly fixing prices with them is against the law. Winners win fair."),
)
_moves_story = _cards(
    ("Pro moves", "Smart owners negotiate politely, read every contract, and plan ahead."),
    ("Negotiate", "Know your budget, ask for a better deal, and be ready to walk away."),
    ("Rainy-day fund", "Saving money lets a business survive surprises."),
    ("Big decisions", "Gather facts, weigh the pros and cons, and ask trusted advisors before deciding."),
)


# --- Industry worlds: one level per real rule ------------------------------

def _yes_no_light(rule, answer_yes):
    found = evaluate(rule, answer_yes)[0]
    word = "Yes" if answer_yes else "No"
    explain = ("That's the safe answer, so the light is green." if found == "CLEARED"
               else "That answer means the rule is broken, so the light is red: fix it right away.")
    return Question(f"Rule: {rule.title}. Aegizyn asks: \"{rule.input}\" The answer is {word}. Which light?",
                    list(LIGHTS), LIGHT_INDEX[found], explain, "light")


@functools.lru_cache(maxsize=None)
def _citation_core(rule):
    """The provision a rule cites, without notes: "21 CFR 1304.11(c)". None
    for a citation that names no provision, such as "State law varies"."""
    core = re.split(r" \(|;", rule.citation, maxsplit=1)[0].strip().casefold()
    return core if re.search(r"\d", core) else None


def _same_requirement(a, b):
    """Whether two industries' rules are the same legal duty, maybe under
    another title: the DEA's biennial inventory is "DEA biennial inventory"
    for drug makers and "Biennial controlled-drug inventory" for pharmacies."""
    return (a.title == b.title or a.key == b.key
            or (_citation_core(a) is not None and _citation_core(a) == _citation_core(b)))


# Industries that are the same kind of business, so neither is ever a wrong
# answer for the other: a school follows School Aegizyn's legal duties (8) and
# School Safety Aegizyn's safety routines (51) alike.
KINDRED = (frozenset({8, 51}),)


@functools.lru_cache(maxsize=None)
def _sharing(industry_id, index):
    """The industries that have this rule, under its own title or another,
    and those of the same kind of business (KINDRED)."""
    rule = CATALOG[industry_id][index - 1]
    found = {i for i, rules in CATALOG.items() if any(_same_requirement(r, rule) for r in rules)}
    for group in KINDRED:
        if industry_id in group:
            found |= group
    return frozenset(found)


def _alike(a, b):
    """Whether two answers say the same thing in nearly the same words."""
    x, y = (re.sub(r"[\W_]+", " ", t).casefold().split() for t in (a, b))
    if x == y:
        return True
    matcher = difflib.SequenceMatcher(None, x, y)
    return matcher.real_quick_ratio() >= 0.8 and matcher.quick_ratio() >= 0.8 and matcher.ratio() >= 0.8


def _wrong_answers(rng, right, texts, count=2, group=None, below=None):
    """`count` wrong answers from texts, none of which reads like the right
    answer or like each other: two near-copies would be two right answers.
    They are about as long as the right answer, picked from the texts just
    shorter and just longer than it. `below` is how many come from the
    shorter side (random when not given): a world's builder turns it round
    question by question, so the right answer is the shortest, the longest or
    in between about equally often, and its length gives nothing away.
    `group` names what two wrong answers may not share (one trade said two
    ways)."""
    group = group or (lambda text: text)
    texts = [t for t in dict.fromkeys(texts) if t != right]
    near = lambda t: (abs(len(t) - len(right)), t)  # noqa: E731
    shorter = sorted((t for t in texts if len(t) < len(right)), key=near)
    longer = sorted((t for t in texts if len(t) > len(right)), key=near)
    below = rng.randint(0, count) if below is None else below % (count + 1)
    picked = []

    def fits(text):
        return not _alike(text, right) and all(not _alike(text, p) and group(text) != group(p) for p in picked)

    for side, many in ((shorter, below), (longer, count - below), (sorted(texts, key=near), count)):
        pool = side[:max(many * 4, 8)]
        rng.shuffle(pool)
        for text in pool + side[len(pool):]:
            if len(picked) >= count or many <= 0:
                break
            if fits(text):
                picked.append(text)
                many -= 1
    return picked


def _length_place(q):
    """Where a question's right answer sits by length: 0 the one shortest,
    2 the one longest, 1 anywhere else."""
    lengths = [len(o) for o in q.options]
    mine = lengths[q.answer]
    if lengths.count(mine) == 1 and mine in (min(lengths), max(lengths)):
        return 0 if mine == min(lengths) else 2
    return 1


# Who follows a rule nearly every business follows: never "only restaurants".
_WHO_ALL = {30: "Any business with employees", 31: "Any business that keeps people's personal data",
            32: "Any business that takes card payments"}


def _who_follows(rng, industry_id, rule, sector, shared, below=None):
    """"Which kind of business follows this rule?" For a rule nearly every
    business follows (is_universal), the answer says so, and the wrong
    answers are each one kind of business only, which can't be true."""
    also = sorted(set(shared) & UNIVERSAL_INDUSTRIES)
    if is_universal(industry_id, rule) or also:
        key = industry_id if industry_id in UNIVERSAL_INDUSTRIES else (also[0] if also else None)
        everyone = _WHO_ALL.get(key, "Many kinds of business, not just one")
        # Each wrong answer is one trade only, said short or long, so the
        # wrong answers can be about as long as the right one.
        trades = {}
        for i in INDUSTRIES:
            if i not in shared and i != industry_id:
                trade = INDUSTRIES[i]["sector"].lower()
                trades[f"Only {trade}"] = trades[f"Only {trade}, no other business"] = trade
        return _choice(rng, f"Who has to follow \"{rule.title}\"?", everyone,
                       _wrong_answers(rng, everyone, list(trades), group=trades.get, below=below),
                       f"\"{rule.title}\" isn't for one trade only: {everyone[0].lower() + everyone[1:]} follows it.")
    return _choice(rng, f"Which kind of business follows \"{rule.title}\"?", sector,
                   _wrong_answers(rng, sector, [INDUSTRIES[i]["sector"] for i in INDUSTRIES
                                                if i not in shared and i not in UNIVERSAL_INDUSTRIES], below=below),
                   f"This rule is one of the ten that matter most in {sector.lower()}.")


def _rule_questions(rng, industry_id, index):
    rule = CATALOG[industry_id][index - 1]
    # Some rules are in several industries (OFAC screening is in four), some
    # under another title: those industries, and their copies of the rule,
    # are never offered as wrong answers.
    shared = _sharing(industry_id, index)
    others = [r for i, rules in CATALOG.items() if i not in shared for r in rules]
    sector = INDUSTRIES[industry_id]["sector"]
    lights = []
    if rule.kind in ("max", "min"):
        lights = [_light_question(rule, value, found) for found, value in _light_cases(rule).items()]
    else:
        lights = [_yes_no_light(rule, True), _yes_no_light(rule, False)]
    # Where the right answer sits by length: the shortest (0), in between (1)
    # or the longest (2), turned round rule by rule. A trade's name can only
    # be the shortest ("Schools") or the longest of its options, so when it
    # is, the rule's other three questions keep off that place.
    who = _who_follows(rng, industry_id, rule, sector, shared, below=index)
    place = _length_place(who)
    if place == 1:
        places = [index, index + 1, index + 2]
    else:
        a, b = [p for p in (0, 1, 2) if p != place]
        places = [a, b, a] if index % 2 else [b, a, b]
    facts = [
        _choice(rng, f"Why does \"{rule.title}\" matter?", rule.cost,
                _wrong_answers(rng, rule.cost, [r.cost for r in others], below=places[0]),
                "Every rule protects something: people, money or the company's good name."),
        _choice(rng, f"If \"{rule.title}\" is broken, what should the team do?", rule.action,
                _wrong_answers(rng, rule.action, [r.action for r in others], below=places[1]),
                "Knowing the fix ahead of time means acting fast."),
        who,
        _choice(rng, f"To check \"{rule.title}\", what does Aegizyn ask?", rule.input,
                _wrong_answers(rng, rule.input, [r.input for r in others], below=places[2]),
                "Aegizyn asks a simple question or reading for every rule."),
    ]
    if _counts_days_since(rule) and 7 <= rule.limit <= 3650:
        limit = int(rule.limit)
        done = rng.randint(1, limit - 1)
        left = limit - done
        facts.append(_choice(rng, f"\"{rule.title}\" must be done at least every {plural(limit, 'day')}. It was last done "
                                  f"{plural(done, 'day')} ago. How many days are left?", str(left),
                             [str(limit + done), str(left + 10)], f"{limit} − {done} = {plural(left, 'day')} left."))
    rng.shuffle(lights)
    rng.shuffle(facts)
    # Two light questions first, so a short lesson still has one of each kind.
    return lights[:2] + facts + lights[2:]


def _rule_story(industry_id, index):
    rule = CATALOG[industry_id][index - 1]
    brand = INDUSTRIES[industry_id]["brand"]
    return [
        (f"{brand} rule {index} of {len(CATALOG[industry_id])}", rule.title),
        ("Why it matters", rule.cost),
        ("What Aegizyn checks", rule.input),
        ("If it goes wrong", rule.action),
    ]


# --- Question-bank worlds ------------------------------------------------------

def _bank_story(key):
    return list(_BANK[key]["cards"])


# Worlds that get a freshly generated math question in every quiz.
_MATH_WORLDS = {"pricing", "budget", "saving", "credit"}


def _distinct(rng, correct, wrong, money=True):
    """Two wrong answers that differ from the right one and from each other."""
    fmt = (lambda n: f"${n}") if money else str
    value = int(correct.lstrip("$"))
    picked = []
    for w in list(wrong) + [fmt(value + d) for d in (1, -1, 2, 5, 10, -5)]:
        if w != correct and w not in picked and not w.lstrip("$").startswith("-"):
            picked.append(w)
        if len(picked) == 2:
            break
    return picked


def _money_math(rng, progress):
    """An exact, generated money problem; bigger numbers as the learner goes deeper."""
    question = _money_problem(rng, progress)
    correct = question.options[question.answer]
    # A generated wrong answer can come out below zero ("$20 off 25" gives
    # "$-5"). No price is negative, so that option gives the answer away;
    # such a question gets its wrong answers picked again.
    if len(question.options) == 3 and not any(o.startswith("$-") for o in question.options):
        return question
    prompt, explain = question.prompt, question.explain
    others = [o for o in question.options if o != correct]
    return _choice(rng, prompt, correct, _distinct(rng, correct, others, correct.startswith("$")), explain)


def _money_problem(rng, progress):
    big = 1 + int(progress * 4)
    kind = rng.choice(["profit", "discount", "markup", "budget", "save", "interest", "break-even"])
    if kind == "profit":
        cost = rng.randint(1, 5 * big)
        price = cost + rng.randint(1, 5 * big)
        n = rng.randint(2, 10 * big)
        answer = (price - cost) * n
        return _choice(rng, f"Each item costs ${cost} to make and sells for ${price}. What is the profit on {n} items?",
                       f"${answer}", [f"${price * n}", f"${answer + n}"],
                       f"Profit per item is ${price} - ${cost} = ${price - cost}. Times {n} items is ${answer}.")
    if kind == "discount":
        price = rng.choice([20, 40, 50, 60, 80, 100, 120, 200]) * big
        off = rng.choice([10, 20, 25, 50])
        answer = price - price * off // 100
        return _choice(rng, f"A ${price} jacket is {off}% off. What is the sale price?", f"${answer}",
                       [f"${price - off}", f"${price * off // 100}"],
                       f"{off}% of ${price} is ${price * off // 100}, so the sale price is ${answer}.")
    if kind == "markup":
        cost = rng.choice([10, 20, 30, 40, 50]) * big
        up = rng.choice([25, 50, 100])
        answer = cost + cost * up // 100
        return _choice(rng, f"A shop buys a game for ${cost} and adds a {up}% markup. What is the price?", f"${answer}",
                       [f"${cost + up}", f"${cost * up // 100}"],
                       f"{up}% of ${cost} is ${cost * up // 100}. Add it to the cost: ${answer}.")
    if kind == "budget":
        budget = rng.choice([100, 200, 250, 500]) * big
        spent = [rng.randint(5, budget // 5) for _ in range(3)]
        answer = budget - sum(spent)
        return _choice(rng, f"Your monthly budget is ${budget}. You spent ${spent[0]}, ${spent[1]} and ${spent[2]}. "
                            "How much is left?", f"${answer}", [f"${answer + spent[0]}", f"${sum(spent)}"],
                       f"Add what you spent (${sum(spent)}) and subtract it from ${budget}: ${answer} left.")
    if kind == "save":
        weekly = rng.randint(2, 10 * big)
        weeks = rng.randint(3, 12)
        return _choice(rng, f"You save ${weekly} every week. How much do you have after {weeks} weeks?",
                       f"${weekly * weeks}", [f"${weekly + weeks}", f"${weekly * (weeks - 1)}"],
                       f"${weekly} x {weeks} weeks = ${weekly * weeks}. Small steady savings add up.")
    if kind == "interest":
        amount = rng.choice([100, 200, 500, 1000]) * big
        rate = rng.choice([2, 5, 10])
        return _choice(rng, f"A bank pays {rate}% interest a year. How much interest does ${amount} earn in one year?",
                       f"${amount * rate // 100}", [f"${rate}", f"${amount + rate}"],
                       f"{rate}% of ${amount} is ${amount * rate // 100}. That's money your savings earn for you.")
    cost = rng.choice([50, 100, 150, 200, 300]) * big
    per = rng.choice([2, 5, 10, 25])
    answer = -(-cost // per)
    return _choice(rng, f"A new machine costs ${cost}. You earn ${per} profit per item. "
                        "How many items must you sell to pay it back?", str(answer), [str(answer * 2), str(answer + per)],
                   f"${cost} / ${per} = {answer} items. After that, the machine is making you money.")


# --- The family tracks' fixed question pools ------------------------------------
# Each world of a family track is a fixed list of questions (family_pool),
# built from a seed per track, world and company, cut into lessons of the
# track's lesson size. No question comes back in a later lesson of the same
# world, and the level count is the real number of lessons. A world built
# from the company's own rules (Meet Your Company, Why Rules Matter, the
# lights and the calendar) has the same number of questions for every
# company, so every family sees the same level counts.

def _row_choice(rng, row, company):
    """A written (question, best, wrong, wrong, why[, level]) row as a question."""
    prompt, best, wrong1, wrong2, why = (str(part).format(company=company) for part in row[:5])
    return _choice(rng, prompt, best, [wrong1, wrong2], why)


def _rows(rng, rows, company, level=1):
    return [(_row_choice(rng, row, company), row[5] if len(row) > 5 else level) for row in rows]


_DECOY_NAMES = ["Riverside Services", "Maple Street Group", "Blue Lake Company", "Summit Supply Co."]


# Rules almost any business follows, whatever its trade: an employer's
# (HR Aegizyn), card payments (Pay Aegizyn) and personal data (Privacy Aegizyn), and
# checks many trades share, like fire extinguishers or safety data sheets.
# They are never a wrong answer to "which is your company's rule?": "Hours
# worked records kept" is true for a restaurant with staff too.
UNIVERSAL_INDUSTRIES = frozenset({30, 31, 32})
UNIVERSAL_RULE = re.compile(
    r"fire extinguisher|safety data sheet|hazard communication|hazcom|osha 300|injury report|severe injury"
    r"|^overtime paid|card (data|security)|first.aid kit|sales tax|hours worked|minimum wage", re.I)


@functools.lru_cache(maxsize=None)
def is_universal(industry_id, rule):
    """Whether a rule is one nearly every business follows (UNIVERSAL_RULE),
    or the same duty as one of an employer's, card payments' or personal
    data's rules ("OFAC sanctions screening" is a bank's and Pay Aegizyn's)."""
    if industry_id in UNIVERSAL_INDUSTRIES or UNIVERSAL_RULE.search(rule.title):
        return True
    return any(_same_requirement(rule, other) for i in UNIVERSAL_INDUSTRIES for other in CATALOG.get(i, ()))


def _unrelated_rules(industry_ids):
    """Rules from industries the company isn't in (nor of the same kind),
    leaving out the rules nearly every business follows (is_universal)."""
    mine = set(industry_ids)
    for group in KINDRED:
        if mine & group:
            mine |= group
    return [r for i, rules in CATALOG.items() if i not in mine for r in rules
            if not is_universal(i, r) and not any(_same_requirement(r, own) for own in _company_rules(industry_ids))]


def _company_items(rng, company, ids):
    sectors = _sectors(ids) or ["Business"]
    mine = set(ids)
    for group in KINDRED:
        if mine & group:
            mine |= group
    others = [INDUSTRIES[i]["sector"] for i in INDUSTRIES if i not in mine]
    if len(others) < 2:  # a company in every industry
        others = ["Toy making", "Travel booking", "Car washing"]
    own = _company_rules(ids) or _all_rules()
    picked = rng.sample(own, 2)
    strangers = [r.title for r in _unrelated_rules(ids)]
    if len(strangers) < 4:
        strangers = ["Front door repainted every year", "Shop sign changed each season",
                     "Staff photos updated monthly", "Lobby music changed weekly"]
    items = [
        (_choice(rng, "What is the name of your family's company?", company,
                 rng.sample([n for n in _DECOY_NAMES if n != company], 2), f"Your family's company is {company}."), 1),
        (_choice(rng, f"What kind of work does {company} do?", sectors[0], rng.sample(others, 2),
                 f"{company} works in {', '.join(s.lower() for s in sectors)}."), 1),
        (_choice(rng, f"Which of these is a rule {company} really follows?", picked[0].title,
                 rng.sample(strangers, 2),
                 f"\"{picked[0].title}\" is one of {company}'s rules. The others are for other kinds of business."), 2),
        (_choice(rng, f"Which of these checks is on {company}'s own checklist?", picked[1].title,
                 rng.sample(strangers, 2),
                 f"\"{picked[1].title}\" is on {company}'s checklist. The others are for other kinds of business."), 2),
    ]
    return items + _rows(rng, _basics.COMPANY, company), COMPANY_FACTS + _basics.COMPANY_FACTS


def _rules_items(rng, company, ids):
    rule = rng.choice(_company_rules(ids) or _all_rules())
    others = [r.cost for r in _unrelated_rules(ids)] or [r.cost for r in _all_rules() if r.cost != rule.cost]
    items = [
        (_choice(rng, "What is a fine?", "Money paid as a penalty for breaking a rule",
                 ["Money paid to renew a permit each year", "Money paid to workers for extra hours"],
                 "A fine is a penalty. It costs the company money that could have gone to growing the business."), 1),
        (_choice(rng, f"Here's a real rule for {company}: \"{rule.title}.\" Why does it matter?", rule.cost,
                 _wrong_answers(rng, rule.cost, others),
                 "Every rule protects something: people, money or the company's good name."), 3),
    ]
    return items + _rows(rng, _basics.RULES, company), RULE_FACTS + _basics.RULE_FACTS


LIGHT_QUESTIONS = 7   # light questions per light, green, yellow and red, in the lights world
YES_NO_LIGHTS = 3


def _lights_items(rng, company, ids):
    own = _company_rules(ids)
    chosen, used = [], set()
    for found in ("CLEARED", "WARNING", "BLOCKED"):
        for pool in (_light_rules(own), _light_rules(_all_rules())):
            cases = [(r, _light_cases(r)[found]) for r in pool if found in _light_cases(r)]
            rng.shuffle(cases)
            for rule, value in cases:
                if sum(1 for c in chosen if c[2] == found) >= LIGHT_QUESTIONS:
                    break
                if (rule.title, found) not in used:
                    used.add((rule.title, found))
                    chosen.append((rule, value, found))
    items = [(_light_question(rule, value, found), 2) for rule, value, found in chosen]
    yes_no = [r for r in own if r.kind in ("required", "forbidden")]
    yes_no += [r for r in _all_rules() if r.kind in ("required", "forbidden") and r not in yes_no]
    for n, rule in enumerate(yes_no[:YES_NO_LIGHTS]):
        items.append((_yes_no_light(rule, n % 2 == 0), 2))
    return items, []


DAYS_LEFT_QUESTIONS = 6
LATE_QUESTIONS = 4
WEEKDAY_QUESTIONS = 4


def _calendar_items(rng, company, ids):
    pool = _since_rules(_company_rules(ids))
    pool = pool + [r for r in _since_rules(_all_rules()) if r not in pool]
    items, prompts = [], set()

    def add(q, level=2):
        if q.prompt not in prompts:
            prompts.add(q.prompt)
            items.append((q, level))

    n = 0
    while sum(1 for q, _ in items if "How many days are left" in q.prompt) < DAYS_LEFT_QUESTIONS:
        rule = pool[n % len(pool)]
        n += 1
        limit = int(rule.limit)
        done = rng.randint(1, limit - 1)
        left = limit - done
        wrong = [w for w in {limit + done, done, abs(left - 7) or left + 3, left + 10} if w != left and w >= 0]
        add(_choice(rng, f"\"{rule.title}\" must be done at least every {plural(limit, 'day')}. It was last done"
                         f" {plural(done, 'day')} ago. How many days are left?", str(left),
                    [str(w) for w in sorted(wrong)[:2]], f"{limit} − {done} = {plural(left, 'day')} left."))
    for k in range(LATE_QUESTIONS):
        rule = pool[(n + k) % len(pool)]
        limit = int(rule.limit)
        late = k % 2 == 0
        ago = limit + rng.randint(1, 20) if late else rng.randint(1, limit - 1)
        add(_choice(rng, f"\"{rule.title}\" must be done every {plural(limit, 'day')}. It was last done {plural(ago, 'day')}"
                         " ago. Is it late?", "Yes, it's overdue" if late else "No, there's still time",
                    ["No, there's still time" if late else "Yes, it's overdue"],
                    f"{plural(ago, 'day')} is {'more' if late else 'less'} than {plural(limit, 'day')}."))
    starts = rng.sample(range(7), WEEKDAY_QUESTIONS)
    for k, start in enumerate(starts):
        ahead = 2 + k + rng.randint(0, 3)
        due_day = WEEKDAYS[(start + ahead) % 7]
        add(_choice(rng, f"Today is {WEEKDAYS[start]}. A job is due in {ahead} days. Which day is that?", due_day,
                    rng.sample([d for d in WEEKDAYS if d != due_day], 2),
                    f"Count forward {ahead} days from {WEEKDAYS[start]} and you land on {due_day}."), 1)
    add(_choice(rng, "When does Aegizyn send the first reminder before a deadline?", "30 days before",
                ["7 days before", "On the day it's due"],
                "Reminders go out 30, 7 and 1 day before, on the day, and every week if it's late."), 1)
    add(_choice(rng, "After a job is finished, someone presses \"Done today.\" What happens?",
                "The countdown starts over for next time",
                ["The check is removed from the list", "The reminder emails stop for good"],
                "Most jobs repeat, like a yearly checkup. Done today starts the next countdown."), 1)
    return items + _rows(rng, _basics.CALENDAR, company), _basics.CALENDAR_FACTS


PROFIT_QUESTIONS = 4
FINE_QUESTIONS = 3


def _money_items(rng, company, ids):
    items = []
    for k in range(PROFIT_QUESTIONS):
        scale = 1 + k  # each one a size bigger, so no two are the same
        revenue = rng.randrange(8000 * scale, 20000 * scale + 1, 500 * scale)
        costs = rng.randrange(3000 * scale, revenue - 1000 * scale, 500 * scale)
        profit = revenue - costs
        items.append((_choice(rng, f"Pretend {company} earned {money(revenue)} one month and spent {money(costs)}."
                                   " What is the profit?", money(profit), [money(revenue + costs), money(costs)],
                              f"Profit = revenue − costs: {money(revenue)} − {money(costs)} = {money(profit)}."),
                      1 + k // 2))
    for k in range(FINE_QUESTIONS):
        # A different fine each time, so no two questions are the same.
        fine = (500, 1000, 1500, 2000)[(k + rng.randrange(4)) % 4] * (1 + k) + 100 * k
        profit = rng.randrange(3000, 12001, 500) * (1 + k)
        items.append((_choice(rng, f"{company} made a profit of {money(profit)}, then paid a {money(fine)} fine."
                                   " How much profit is left?", money(profit - fine),
                              [money(profit + fine), money(fine)],
                              f"A fine is a surprise cost: {money(profit)} − {money(fine)} = {money(profit - fine)}."),
                      2))
    fix, penalty = rng.choice([100, 200, 300]), rng.choice([1000, 2500, 5000])
    items.append((_choice(rng, "Which costs less?", f"Fixing a problem early for {money(fix)}",
                          [f"Paying a fine of {money(penalty)} later"],
                          "Preventing problems is almost always cheaper than paying for them later."), 1))
    return items + _rows(rng, _basics.MONEY, company), _basics.MONEY_FACTS


_TEAM_ROWS = [
    ("Why does {company} keep a record of every change?", "To show who did what, and on what day",
     "To catch people who make small slips", "Because inspectors type it in for you",
     "Records help the team stay honest and show inspectors that the company did its job.", 1),
    ("A worker tells you about a safety problem. What should a good leader do?", "Thank them, then get it fixed fast",
     "Wait to see whether anyone gets hurt", "Ask them to keep it quiet for now",
     "Leaders want to hear about problems early, so people stay safe.", 1),
    ("Who is the best one to ask when a rule is confusing?", "An expert, like a lawyer",
     "A friend who once worked in the business", "Whoever on the team makes the best guess",
     "Smart owners ask experts. Nobody knows everything.", 2),
    ("What's the best way to treat customers?", "Honestly and fairly, whoever they are", "Extra nicely when they spend a lot",
     "The same way rival shops treat theirs", "Trust is a company's most valuable treasure.", 1),
]


def _team_items(rng, company, ids):
    return _rows(rng, _TEAM_ROWS + _basics.TEAM, company), TEAM_FACTS + _basics.TEAM_FACTS


def _word_question(rng, word, meaning, words, n):
    """'What does "Revenue" mean?' (1.18.0): the card and the Word Bank give its
    meaning; the right answer says the same idea in other words (WORD_IDEAS),
    and the wrong answers are other words' ideas, never a kindred word's."""
    right = WORD_IDEAS[word]
    others = [WORD_IDEAS[w] for w, _ in words if w != word and not kindred(word, w)]
    wrong = _wrong_answers(rng, right, others, below=n)
    return _choice(rng, f"What does \"{word}\" mean?", right, wrong, f"{word}: {meaning}")


# --- Business Words in use (1.19.0) ----------------------------------------------
# Besides "What does X mean?", a word is asked in a scene (which word fills
# the gap) and in a sentence (which sentence uses it the right way). The
# scenes are in academy_bank/word_use.py.

def _clash(a, b):
    """Two words that must never be in one question: kindred words, or words
    that could half-fit each other's scenes."""
    return a == b or kindred(a, b) or any(a in group and b in group for group in CLASHES)


def _names(text, word):
    """Whether a text names a word (or its plural)."""
    return re.search(rf"\b{re.escape(word.lower())}(s|es)?\b", text.lower()) is not None


def _in_gap(scene, word):
    """A scene with a word in its gap, as it would be written mid-sentence."""
    return scene.replace(GAP, word if word.isupper() else word.lower())


def _word_scene(rng, word, meaning, words, n):
    """"Which word fills the gap?" (1.19.0): the word's scene, the word and two
    others that don't half-fit it. 1.21.0: with a small picture of where the
    scene happens (scene_picture), never one of the word itself."""
    scene = WORD_SCENES[word]
    others = [w for w, _ in words if not _clash(word, w) and not _names(scene, w)]
    wrong = _wrong_answers(rng, word, others, below=n)
    q = _choice(rng, f"Which word fills the gap? {scene}", word, wrong, f"{word}: {meaning}")
    q.look = "scenario"
    # The page asks the question as its heading and shows the scene under it.
    q.parts = {"title": "Which word fills the gap?", "scene": scene, "pic": scene_picture(scene)}
    return q


# 1.21.0: an answer to "Which sentence uses ...?" is at most this long, so the three sentences read at a glance on a
# phone (some scenes ran to 120 characters). A word whose own scene is longer is asked in its scene instead.
SENTENCE_MOST = 90


# 1.23.0: a wrong answer to "Which sentence uses ...?" must read as a real sentence that means the wrong thing, so it
# is only made from a scene whose gap is a noun's place: after "the", "its", "his", "her", "their" or a "'s", maybe
# with a word or two between ("the shop's biggest ___"). A bare gap ("Following every rule like that is ___.", "a
# high ___", "went to court: ___.") fits only its own word: "is invoice." was not a sentence, so a kid could rule it
# out on grammar alone. tools/quiz_truth_review.py flags any that slip through ("sentence-grammar").
NOUN_SLOT = re.compile(r"(?:\b(?:the|its|his|her|their|our|your|my)|'s)\s+(?:[\w-]+\s+){0,2}" + re.escape(GAP))


def noun_slot(scene):
    """Whether a scene's gap is a noun's place, where any business word reads as a sentence (1.23.0)."""
    return NOUN_SLOT.search(scene) is not None


def _sentence_others(word, words):
    """The other words' scenes with `word` put in their gap that can be wrong answers to its sentence question:
    a noun's place only (noun_slot), so each reads as a sentence and is wrong only in what it means."""
    return [_in_gap(WORD_SCENES[w], word) for w, _ in words
            if w in WORD_SCENES and noun_slot(WORD_SCENES[w]) and not _clash(word, w) and not _names(WORD_SCENES[w], word)
            and len(_in_gap(WORD_SCENES[w], word)) <= SENTENCE_MOST]


def _sentence_fits(word, words):
    """Whether `word` can be asked as "Which sentence uses ...?" with every answer short enough."""
    return len(_in_gap(WORD_SCENES[word], word)) <= SENTENCE_MOST and len(_sentence_others(word, words)) >= 2


def _word_sentence(rng, word, meaning, words, n):
    """'Which sentence uses "Invoice" the right way?' (1.19.0): the word's own
    scene, and two other words' scenes with it put in their gap, each at most
    SENTENCE_MOST characters (1.21.0)."""
    right = _in_gap(WORD_SCENES[word], word)
    wrong = _wrong_answers(rng, right, _sentence_others(word, words), below=n)
    return _choice(rng, f"Which sentence uses \"{word}\" the right way?", right, wrong, f"{word}: {meaning}")


def asked_word(q):
    """The word a Business Words question is about, in any of its kinds ("What does X mean?", "Which word fills
    the gap?", "Which sentence uses X ...?"), or None (1.21.0)."""
    if q.kind != "choice":
        return None
    if q.prompt.startswith("Which word fills the gap?"):
        return q.options[q.answer]
    found = re.match(r'(?:What does "(.+)" mean\?|Which sentence uses "(.+)" the right way\?)$', q.prompt)
    return (found.group(1) or found.group(2)) if found else None


def words_in(q):
    """Every Business Word a question shows, asked or offered: its word, the words offered in a scene, and the
    words whose ideas are its answers to "What does X mean?" (1.21.0)."""
    if q.kind != "choice":
        return set()
    idea_of = {idea: w for w, idea in WORD_IDEAS.items()}
    found = {asked_word(q)} - {None}
    if q.prompt.startswith("Which word fills the gap?"):
        found |= {o for o in q.options if o in WORD_IDEAS}
    elif q.prompt.startswith("What does"):
        found |= {idea_of[o] for o in q.options if o in idea_of}
    return found


def _word_of(q):
    """The word a Business Words question asks about, or None."""
    found = re.match(r'What does "(.+)" mean\?$', q.prompt)
    return found.group(1) if found else None


def _quiz_words(words):
    """The Word Bank's words the quiz asks about: those with an idea in other words."""
    return [(w, m) for w, m in words if w in WORD_IDEAS]


def _words_items(rng, company, ids):
    words = _quiz_words(GLOSSARY)
    rest = words[16:]
    rng.shuffle(rest)
    items = []
    for n, (word, meaning) in enumerate(words[:16] + rest):
        items.append((_word_question(rng, word, meaning, words, n), 1 if n < 16 else 2))
    return items, []


_SCENARIO_POOLS = {"talk": PRO_TALK, "ownit": OWN_IT, "grit": GRIT, "respect": RESPECT, "hiring": HIRING,
                   "toughcalls": TOUGH_CALLS, "customers": CUSTOMERS, "compete": COMPETE, "moves": MOVES}
MATH_QUESTIONS = 3   # generated money problems in each math world


def _bank_items(rng, key, company):
    bank = _BANK[key]
    items = _rows(rng, bank["questions"], company)
    if key in _MATH_WORLDS:
        prompts = {q.prompt for q, _ in items}
        progress = 0.0
        while sum(1 for q, _ in items if q.prompt not in prompts) < MATH_QUESTIONS:
            q = _money_math(rng, progress)
            progress = min(1.0, progress + 0.3)
            if q.prompt not in prompts and all(q.prompt != p.prompt for p, _ in items):
                items.append((q, 2))
    return items, list(bank["facts"])


_WORLD_ITEMS = {"company": _company_items, "rules": _rules_items, "lights": _lights_items,
                "calendar": _calendar_items, "money": _money_items, "team": _team_items, "words": _words_items}


def _world_items(w, rng, company, ids):
    """A world's questions, each with its level (1 easy to 3 hard), and its
    true-or-false facts."""
    if w.key in _BANK:
        return _bank_items(rng, w.key, company)
    if w.key in _WORLD_ITEMS:
        return _WORLD_ITEMS[w.key](rng, company, list(ids))
    return [(_row_choice(rng, row, company), 1) for row in _SCENARIO_POOLS[w.key]], []


# --- Lesson formats (1.18.0) ---------------------------------------------------
# A lesson mixes its kinds of question: multiple choice (a scenario when it
# sets a scene), true or false, and in some worlds a matching game (Business
# Words: three words to their ideas) and a sorting game (safe or unsafe,
# honest or not, safe online or risky). They take the place of a question the
# lesson already had, so every world keeps its number of lessons.

def _code_label(names, picks, sep=" → "):
    return "; ".join(f"{n}{sep}{p}" for n, p in zip(names, picks))


def _build_match(words, idea_of, meaning_of, rng, title="Match each word to its idea.", pool=None):
    """A matching game: three words (or terms), each to its idea, with one
    option per way of pairing them, so it is graded like any question."""
    ideas = [idea_of[w] for w in words]
    shown = list(ideas)
    rng.shuffle(shown)
    codes = list(itertools.permutations(range(3)))
    labels = [_code_label(words, [shown[i] for i in code]) for code in codes]
    truth = tuple(shown.index(idea_of[w]) for w in words)
    explain = " ".join(f"{w}: {meaning_of[w].rstrip('.')}." for w in words)
    parts = {"title": title, "left": list(words), "right": shown,
             "codes": [",".join(map(str, c)) for c in codes]}
    if pool:
        parts["pool"] = pool
    return Question(f"Match the words to their ideas: {', '.join(words)}", labels, codes.index(truth), explain,
                    "match", parts=parts)


def _match_question(q, rng, lesson=()):
    """A word question turned into a matching game: the word asked about and
    the two words whose ideas were its wrong answers, each to its idea.
    1.19.0: it also keeps the other words its lesson teaches (`lesson`), so
    each attempt can match the word with a different two (_rotated)."""
    idea_of = {idea: w for w, idea in WORD_IDEAS.items()}
    word = _word_of(q)
    if not word or any(o not in idea_of for o in q.options):
        return q
    words = [word] + [idea_of[o] for o in q.options if idea_of[o] != word]
    glossary = dict(GLOSSARY)
    pool = list(words) + [w for w in lesson if w in WORD_IDEAS and w not in words and not _clash(word, w)]
    return _build_match(words, WORD_IDEAS, glossary, rng, pool=pool)


def _rotated(q, rng):
    """A match with a pool (1.19.0): the first word, and two others from the
    pool picked for this attempt, so a retry isn't the same three words."""
    pool = q.parts["pool"]
    anchor, rest = pool[0], list(pool[1:])
    rng.shuffle(rest)
    pair = []
    for w in rest:
        if len(pair) < 2 and all(not _clash(w, p) for p in pair):
            pair.append(w)
    if len(pair) < 2:
        return Question(q.prompt, list(q.options), q.answer, q.explain, q.kind, parts=q.parts)
    glossary = dict(GLOSSARY)
    return _build_match([anchor] + pair, WORD_IDEAS, glossary, rng, title=q.parts["title"], pool=pool)


# Worlds with a matching game of their own terms (1.19.0): three "What is a
# ...?" questions of the world, each term to its answer.
TERM_MATCH_WORLDS = ("marketing", "cyber", "world")
_TERM = re.compile(r"^What (?:is|are) (?:a |an |the )?['\"]?([A-Za-z][A-Za-z -]{1,24}?)['\"]?(?: in marketing)?\?$")


def _term_matches(questions, rng):
    """Matching games from a world's "What is a ...?" questions: terms of one
    or two words, three to a game, no term twice."""
    terms = {}
    for q in questions:
        found = _TERM.match(q.prompt) if q.kind == "choice" else None
        if found and len(found.group(1).split()) <= 2:
            term = found.group(1).strip()
            term = term[0].upper() + term[1:]
            terms.setdefault(term, (q.options[q.answer], q.explain))
    names = list(terms)
    rng.shuffle(names)
    out = []
    while len(names) >= 3:
        group, names = names[:3], names[3:]
        idea_of = {t: terms[t][0] for t in group}
        # The idea is the question's right answer; what it means, its explanation (so a lesson's cards never
        # carry another question's answer word for word).
        meaning_of = {t: terms[t][1] for t in group}
        out.append(_build_match(group, idea_of, meaning_of, rng, title="Match each term to what it means."))
    return out


def _sort_questions(key, rng):
    """The world's sorting games: three items each, never all in one bin, and
    no item twice in the world."""
    left, right, title, items = SORT_SETS[key]
    items = list(items)
    rng.shuffle(items)
    out = []
    while len(items) >= 3:
        group = items[:3]
        if len({b for _, b, _ in group}) == 1:
            other = next((i for i, it in enumerate(items[3:], start=3) if it[1] != group[0][1]), None)
            if other is None:
                break
            group[2], items[other] = items[other], group[2]
        del items[:3]
        codes = list(itertools.product(range(2), repeat=3))
        names = [text for text, _, _ in group]
        labels = []
        for code in codes:
            a = [n for n, c in zip(names, code) if c == 0] or ["none"]
            b = [n for n, c in zip(names, code) if c == 1] or ["none"]
            labels.append(f"{left}: {'; '.join(a)}. {right}: {'; '.join(b)}.")
        truth = tuple(b for _, b, _ in group)
        parts = {"title": title, "items": names, "bins": [left, right], "codes": [",".join(map(str, c)) for c in codes]}
        out.append(Question(f"{left} or {right.lower()}? {'; '.join(names)}", labels, codes.index(truth),
                            " ".join(why for _, _, why in group), "sort", parts=parts))
    return out


def _mix_formats(key, questions, size):
    """The world's questions, lesson by lesson, with a sorting game (while
    its items last) in place of each lesson's true-or-false question (or its
    last plain multiple-choice one) after the first, where the world has a
    sorting set, and, in Business Words, a matching game in every second
    lesson. 1.19.0: Business Words also asks most of its words in a scene
    (which word fills the gap) or a sentence (which uses it right), so a
    lesson keeps at most two "What does X mean?"; and a few more worlds
    (TERM_MATCH_WORLDS) get a matching game of their own terms in every second
    lesson. The same every time (a fixed seed per world)."""
    if key not in SORT_SETS and key != "words" and key not in TERM_MATCH_WORLDS:
        return questions
    rng = random.Random(f"formats:{key}:{size}")
    out = list(questions)
    sorts = _sort_questions(key, rng) if key in SORT_SETS else []
    terms = _term_matches(out, rng) if key in TERM_MATCH_WORLDS else []
    words = _quiz_words(GLOSSARY) if key == "words" else []
    turns = {"_word_question": 0, "_word_scene": 0, "_word_sentence": 0}
    for n in range(len(out) // size):
        chunk = range(n * size, (n + 1) * size)
        if sorts and n >= 1:
            # The lesson's true-or-false question, or else its last plain multiple-choice one.
            spot = next((i for i in chunk if out[i].kind == "truefalse"), None)
            if spot is None:
                spot = next((i for i in reversed(chunk) if out[i].kind == "choice" and not out[i].look), None)
            if spot is not None:
                out[spot] = sorts.pop(0)
        if terms and n % 2 == 1:
            spot = next((i for i in reversed(chunk) if out[i].kind == "choice" and not out[i].look), None)
            if spot is None:
                spot = next((i for i in reversed(chunk) if out[i].kind == "choice"), None)
            if spot is not None:
                out[spot] = terms.pop(0)
        if key == "words":
            taught = [_word_of(out[i]) for i in chunk]
            if n % 2 == 1:
                spot = next((i for i in reversed(chunk) if out[i].kind == "choice"), None)
                if spot is not None:
                    out[spot] = _match_question(out[spot], rng, [w for w in taught if w])
            plain = [i for i in chunk if out[i].kind == "choice" and _word_of(out[i]) in WORD_SCENES]
            keep = max(2, size // 3)
            change = plain[:max(0, len(plain) - keep)]
            for turn, i in enumerate(plain):
                word = _word_of(out[i])
                meaning = dict(GLOSSARY)[word]
                # Each kind turns its right answer's length round on its own (shortest, between, longest),
                # so length gives nothing away in any of them.
                make = (_word_question if i not in change else _word_scene if change.index(i) % 2 == 0
                        else _word_sentence)
                # 1.21.0: a word whose sentences would be too long is asked in its scene instead.
                if make is _word_sentence and not _sentence_fits(word, words):
                    make = _word_scene
                out[i] = make(rng, word, meaning, words, turns[make.__name__])
                turns[make.__name__] += 1
            _match_apart(out, chunk, rng)
    return tuple(out)


MATCH_POOL = 5   # a game's first word and the four it can be matched with (1.21.0), so its cards stay few


def _match_apart(out, chunk, rng):
    """1.21.0: the words a lesson's matching game can show are never asked again in that lesson's other
    questions, nor offered in them (a scene's words, or the ideas of "What does X mean?"), so the game and the
    questions teach different words. The game keeps its own first word and takes the rest of its pool from the
    words the lesson doesn't use elsewhere, in the Word Bank's order from that word on (and when another question
    offers its first word, it starts from the next word the lesson doesn't use)."""
    spot = next((i for i in chunk if out[i].kind == "match" and out[i].parts and out[i].parts.get("pool")), None)
    if spot is None:
        return
    game = out[spot]
    used = set().union(*(words_in(out[i]) for i in chunk if i != spot))
    first = game.parts["pool"][0]
    order = [w for w, _ in _quiz_words(GLOSSARY)]
    start = order.index(first) if first in order else 0
    ring = game.parts["pool"][1:] + order[start + 1:] + order[:start]
    # Its first word, unless another question offers it: then the next word the lesson doesn't use.
    anchor = first if first not in used else next((w for w in ring if w not in used), None)
    if anchor is None:
        return
    pool = [anchor]
    for w in ring:
        if w not in pool and w not in used and not _clash(anchor, w) and len(pool) < MATCH_POOL:
            pool.append(w)
    pair = []
    for w in pool[1:]:
        if len(pair) < 2 and all(not _clash(w, p) for p in pair):
            pair.append(w)
    if len(pair) < 2:
        return
    out[spot] = _build_match([anchor] + pair, WORD_IDEAS, dict(GLOSSARY), rng, title=game.parts["title"], pool=pool)


def _lessons(choices, facts, size, lesson):
    """Up to size items in lessons of `lesson`: one true-or-false fact in
    each lesson while there are facts, the rest multiple choice, in order.
    Whole lessons only."""
    items, choices, facts = [], list(choices), list(facts)
    while len(items) < size and (choices or facts):
        take = lesson - 1 if facts else lesson
        part = choices[:take]
        del choices[:take]
        if facts:
            part.append(facts.pop(0))
        items.extend(part)
    items = items[:size]
    return items[:len(items) // lesson * lesson]


@functools.lru_cache(maxsize=4096)
def _family_pool(track_key, world_number, company, ids):
    t = TRACKS[track_key]
    w = WORLDS[world_number]
    rng = random.Random(f"family:{track_key}:{w.key}:{company}:{','.join(map(str, ids))}")
    items, facts = _world_items(w, rng, company, ids)
    rng.shuffle(items)
    # Easy questions first; Summit and Titan put the hard ones first.
    hard_first = t.mix is _HARD_MIX
    items.sort(key=lambda item: -item[1] if hard_first else item[1])
    facts = list(facts)
    rng.shuffle(facts)
    tf = [_truefalse(*f) for f in _balanced(facts)]
    lesson = t.min_questions
    return _mix_formats(w.key, tuple(_lessons([q for q, _ in items], tf, FAMILY_MAX_LESSONS * lesson, lesson)), lesson)


def family_pool(t, world_number, company, industry_ids):
    """A family world's fixed list of questions, in lesson order: lesson n is
    items (n-1)*size to n*size, size being the track's lesson size."""
    return _family_pool(t.key, world_number, company, tuple(industry_ids))


# The company used to count each world's lessons: every company gets the same
# number (tests/test_quiz_fairness.py checks it for every industry).
_SAMPLE_COMPANY = ("Sample Company", (1,))


def family_stages(t, world_number):
    return len(family_pool(t, world_number, *_SAMPLE_COMPANY)) // t.min_questions


@functools.lru_cache(maxsize=1024)
def _final_pool(track_key, company, ids):
    """The Owner's Challenge's questions: final_stages lessons of
    final_questions, drawn from the track's worlds without a repeat."""
    t = TRACKS[track_key]
    rng = random.Random(f"final:{track_key}:{company}:{','.join(map(str, ids))}")
    by_world = [list(family_pool(t, n, company, ids)) for n in t.topics]
    for questions in by_world:
        rng.shuffle(questions)
    picked, prompts = [], set()
    wanted = t.final_stages * t.final_questions
    while len(picked) < wanted and any(by_world):
        for questions in by_world:
            while questions:
                q = questions.pop()
                if q.prompt not in prompts:
                    prompts.add(q.prompt)
                    picked.append(q)
                    break
    # World by world, so each lesson mixes worlds; then shuffled within the whole.
    rng.shuffle(picked)
    return tuple(picked[:wanted])


@functools.lru_cache(maxsize=None)
def _industry_pool(industry_id):
    """Each rule's questions in a Rule Quest, in rule order."""
    return tuple(tuple(_rule_questions(random.Random(f"rule:{industry_id}:{index}"), industry_id, index))
                 for index in range(1, len(CATALOG[industry_id]) + 1))


def _industry_lesson(t, industry_id, stage):
    return _industry_pool(industry_id)[_rule_index(industry_id, stage) - 1][:t.industry_questions]


def level_exists(t, level):
    """Whether a stored level id is a lesson the track has now. Levels from
    before 1.11.0, when worlds had 50 to 300 repeating stages, stay in the
    database but don't count."""
    if level // 1_000_000 != t.index:
        return False
    w = world_for(t, level % 1_000_000 // 1000)
    stage = level % 1000
    return w is not None and t.has(w) and 1 <= stage <= t.stages(w)


# --- Owner's Challenge -------------------------------------------------------

def _final_story(t, company):
    if t.key == CLASSROOM_KEY:
        return [
            ("The Class Challenge", f"{t.final_questions} questions from across the whole {t.name} track."),
            ("Your prize", "Pass to earn your certificate. Your teacher can print it for you!"),
        ]
    return [
        ("The Owner's Challenge", f"{t.final_questions} questions from across the whole {t.name} track."),
        ("Your prize", f"Pass to earn your Future Owner Certificate for {company}, and keep going to upgrade it!"),
    ]


# The lesson cards of the first worlds (the question-bank worlds have theirs
# in academy_bank).
_CONTENT = {
    "company": _company_story, "words": _words_story, "rules": _rules_story, "lights": _lights_story,
    "calendar": _calendar_story, "money": _money_story, "talk": _talk_story, "team": _team_story,
    "ownit": _ownit_story, "grit": _grit_story, "respect": _respect_story, "hiring": _hiring_story,
    "toughcalls": _toughcalls_story, "customers": _customers_story, "compete": _compete_story,
    "moves": _moves_story,
}


def _rule_index(industry_id, stage):
    return (stage - 1) % len(CATALOG[industry_id]) + 1


def story(t, world_number, stage, company, industry_ids):
    """The lesson cards: every lesson teaches what its quiz asks. Stage 1
    teaches the world, plus a short card for any question its cards don't
    cover; a later stage (and the boss round) has a short card for each of
    its own questions, so no question asks about something never taught."""
    w = WORLDS[world_number]
    if w.kind == "industry":
        return _rule_story(w.industry_id, _rule_index(w.industry_id, stage))
    lesson = quiz(t, world_number, stage, company, industry_ids, "teach")
    if t.key == CLASSROOM_KEY:
        company = CLASS_BUSINESS
    if w.kind == "final":
        cards = _final_story(t, company)
    elif w.key in _BANK:
        cards = _bank_story(w.key)
    else:
        cards = _CONTENT[w.key](company, list(industry_ids))
    if stage == 1:
        # The first lesson stays short. When it asks something its cards
        # don't already teach in so many words, its last card ends with a
        # hint on how to think, never the answers (1.16.0: the old "Before
        # the quiz" line listed them): the fact shows the moment the question
        # is answered, and a miss comes back in practice.
        said = " ".join(f"{a} {b}" for a, b in cards).lower()
        if not any(not _taught(q, said) for q in lesson):
            return cards
        return cards[:-1] + [(cards[-1][0], f"{cards[-1][1]} {QUIZ_HINT}: {quiz_hint()}")]
    teach = teaching_cards(lesson)
    if is_boss(t, w, stage):
        head = (f"Stage {stage}: boss round!", "The last lesson of this world, with its highest pass mark. "
                                               "Read each card, then take your time on the quiz.")
    else:
        head = (f"Stage {stage}: learn, then play", f"Read these {len(teach)} short cards. The quiz asks about"
                                                    f" {'each one' if len(teach) > 1 else 'it'}.")
    return [head] + teach


QUIZ_HINT = "Quiz hint"


def quiz_hint():
    """The end of a first lesson's last card, when its quiz asks something
    the cards don't teach in so many words: how to think, not the answers."""
    return ("read every answer before you pick. When a question asks what to do, the safest, fairest and most"
            " honest choice is usually right, and Armo shows you the fact as soon as you answer.")


def _taught(q, said):
    """Whether lesson text already teaches a question: its explanation, or
    its right answer (a word or more, not a bare True or False), is in it."""
    answer = str(q.options[q.answer]).lower().strip(' ."')
    return q.explain.lower().strip(" .") in said or (len(answer) > 5 and answer in said)


def teaching_cards(questions):
    """One short card per question, from what its explanation teaches: the
    fact the question then checks. "Good to know" when the explanation has no
    heading of its own ("Revenue: all the money customers pay")."""
    cards, seen = [], set()
    glossary = dict(GLOSSARY)
    for q in questions:
        if q.kind == "match" and q.parts and q.parts.get("pool"):
            # 1.19.0: a matching game picks its words afresh each attempt, so the cards teach every word it
            # can pick, one card each (the same card a word's own question has).
            for word in q.parts["pool"]:
                text = f"{word}: {glossary[word]}"
                if text not in seen:
                    seen.add(text)
                    cards.append((word, glossary[word]))
            continue
        text = q.explain.strip()
        if not text or text in seen:
            continue
        seen.add(text)
        head, sep, rest = text.partition(": ")
        if sep and len(head) <= 40 and rest and "." not in head:
            cards.append((head, rest))
        else:
            cards.append(("Good to know", text))
    return cards


def quiz(t, world_number, stage, company, industry_ids, seed):
    """The questions for one attempt: the lesson's fixed questions, in an
    order and with options in an order from the seed, so the same seed always
    gives the same quiz and a retry asks the same questions shuffled."""
    w = WORLDS[world_number]
    rng = random.Random(seed)
    if t.key == CLASSROOM_KEY:
        return _classroom_quiz(w, stage, rng)
    ids = tuple(industry_ids)
    if w.kind == "industry":
        lesson = _industry_lesson(t, w.industry_id, stage)
    elif w.kind == "final":
        size = t.final_questions
        lesson = _final_pool(t.key, company, ids)[(stage - 1) * size:stage * size]
    else:
        size = t.min_questions
        lesson = family_pool(t, w.number, company, ids)[(stage - 1) * size:stage * size]
    questions = [_fresh(q, rng) for q in lesson]
    rng.shuffle(questions)
    return questions


def attempt_seed(learner_id, track_key, world_number, stage, attempt):
    base = f"omniarmor-academy:{learner_id}:{world_number}:{stage}:{attempt}"
    return base if track_key == DEFAULT_TRACK else f"{base}:{track_key}"


def grade(questions, answers):
    """answers is a list of chosen option indexes (None when skipped). Returns (score, results)."""
    results = []
    for q, chosen in zip(questions, answers):
        results.append({"question": q, "chosen": chosen, "right": chosen == q.answer})
    return sum(r["right"] for r in results), results


# --- Friends and duels -------------------------------------------------------
# Friends come from different families, so a duel can't use either company's
# name or rules. Duels use the worlds about running any business, and both
# players get the exact same questions from a shared seed.

DUEL_WORLDS = [2, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16] + [w.number for w in BANK_WORLDS]
DUEL_QUESTIONS = 5
DUEL_COMPANY = "the company"
MAX_FRIENDS = 30
FRIEND_CODE_DAYS = 7
_CODE_LETTERS = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O or 1/I mix-ups


def new_friend_code():
    return "ARMO-" + "".join(secrets.choice(_CODE_LETTERS) for _ in range(8))


def clean_friend_code(text):
    letters = "".join(ch for ch in (text or "").upper() if ch.isalnum())
    if letters.startswith("ARMO"):
        letters = letters[4:]
    if len(letters) != 8 or any(ch not in _CODE_LETTERS for ch in letters):
        return None
    return "ARMO-" + letters


def duel_quiz(world_number, stage, seed):
    """Five questions from a world about running any business, the same for
    both players (a shared seed)."""
    rng = random.Random(seed)
    pool = family_pool(TRACKS["trailblazer"], world_number, DUEL_COMPANY, ())
    return [_fresh(q, rng) for q in rng.sample(pool, min(DUEL_QUESTIONS, len(pool)))]


# --- Join codes: a kid's own device ----------------------------------------------

def new_join_code():
    return "KID-" + "".join(secrets.choice(_CODE_LETTERS) for _ in range(8))


def clean_join_code(text):
    letters = "".join(ch for ch in (text or "").upper() if ch.isalnum())
    if letters.startswith("KID"):
        letters = letters[3:]
    if len(letters) != 8 or any(ch not in _CODE_LETTERS for ch in letters):
        return None
    return "KID-" + letters


# --- The Classroom track ----------------------------------------------------------
# For students in a class (classrooms.py). A class learns through its own
# pretend business, a lemonade stand, never "your family's company", and the
# worlds that teach how a family company works, the app's own lights and
# reminders, and the industry Rule Quests are left out. Each world is a fixed
# list of questions cut into lessons of LESSON_QUESTIONS, so no question
# comes back in a later lesson of the same world, and a world has only as
# many lessons as it has questions for (at most CLASS_MAX_STAGES): the level
# count is what a student really plays. A retry asks the same lesson's
# questions, in a new order.

CLASSROOM_KEY = "classroom"
CLASS_BUSINESS = "Sunny Cup Lemonade"
LESSON_QUESTIONS = 5
CLASS_MAX_STAGES = 8
LESSON_MINUTES = 3        # about how long one lesson takes, for the teacher guide
# Who the Classroom track is written for: small-number money (making change,
# profit as revenue minus costs), simple percents in the pricing and budget
# worlds, and reading at about a fourth-grade level.
CLASS_GRADES = "Grades 4–6"
CLASS_AGES = "ages 9 to 12"

# (prompt, best answer, wrong answer, wrong answer, why)
_STAND_QUESTIONS = [
    ("What is the name of your class's pretend business?", CLASS_BUSINESS, "Sunny Day Snacks", "Lemon Lane Drinks",
     f"Your class runs a pretend lemonade stand called {CLASS_BUSINESS}."),
    (f"What does {CLASS_BUSINESS} sell?", "Cups of lemonade", "Fresh-baked cookies", "Bottles of iced tea",
     f"{CLASS_BUSINESS} is a lemonade stand: it sells cups of lemonade."),
    ("What is a business?", "People who make or do something others pay for",
     "A group that gives things away to help people", "Any place where people go to work",
     "A business makes products or does work that customers pay for. Many groups help people for free, and"
     " those are usually charities."),
    (f"Who are {CLASS_BUSINESS}'s customers?", "People who stop and buy a cup of lemonade", "The students who run the stand",
     "The store that sells the stand its lemons", "Customers are the people who buy from a business."),
    ("What is a product?", "Something a business sells, like lemonade", "Work done for someone, like a car wash",
     "The money left after paying for supplies",
     "A product is a thing customers can buy. Work done for someone is a service, not a product."),
    ("What is a service?", "Work a business does for someone", "Something a customer takes home",
     "A list of the prices a business charges",
     "A service is work done for a customer, like washing a car, not a thing to take home."),
    ("Which of these is a service, not a product?", "Walking a neighbor's dog", "A box of homemade cookies",
     "A cup of fresh lemonade", "Walking a dog is work done for someone. Lemonade and cookies are products."),
    ("Why do customers come back to a business?", "They liked what they got and how they were treated",
     "The stand is the closest one to their house", "The stand has the brightest, biggest sign",
     "Good products and kind service make customers want to return."),
    ("Who makes the big decisions for a business?", "The people who own the business", "The customers who buy the most",
     "Whoever has worked there the longest", "Owners decide what the business does and how it does it."),
    ("In a class business, who are the owners?", "The whole class, working together", "Only the student who is in charge",
     "The teacher, since it's the teacher's class",
     "In a class business, everyone shares the work and the decisions, with the teacher's help."),
    ("What do workers at a business do?", "The jobs that keep it running", "Buy most of what the business sells",
     "Decide every price and every rule alone",
     "Workers do the jobs that make the business run, like pouring and selling."),
    ("Before opening the stand, what should the class decide first?", "What to sell, the price and who does each job",
     "Which songs to play while the stand is open", "How to spend the money it will make",
     "A little planning makes opening day go smoothly. Spending comes after you know what you made."),
    ("A customer says the lemonade is too sour. What's the best thing to do?", "Thank them and adjust the next batch",
     "Explain that the recipe is already right", "Give them a free cup and change nothing",
     "Listening to customers helps a business get better."),
    ("Why does a business need customers?", "Their money pays for supplies and keeps it going",
     "They help the business decide on its name", "They tell workers which jobs to do",
     "Without customers paying, a business can't buy supplies or keep going."),
    ("What is a supplier?", "A business that sells you what you need", "A customer who buys a lot every week",
     "The person who counts the money at the end",
     "Suppliers sell a business the things it needs, like lemons and cups."),
    ("Which is a supply the stand needs?", "Paper cups to pour lemonade in", "A cash register with a scanner", "A big menu board with lights",
     "A lemonade stand needs cups, lemons, sugar, water and ice. Fancy equipment can wait."),
    ("What does it mean to \"open for business\"?", "Start selling to customers", "Set up the table and the sign",
     "Buy the supplies you'll need",
     "Setting up and buying supplies come first. Opening for business means starting to sell."),
    ("Where is a good spot for a lemonade stand?", "Where lots of people walk by on a warm day",
     "On a quiet street with very little traffic", "In the shade behind a quiet building",
     "A busy, sunny spot brings more thirsty customers."),
    (f"What could make {CLASS_BUSINESS} different from another stand?", "Something special, like fresh-squeezed lemons",
     "Charging the same price as every other stand", "Using the same sign and cups as the others",
     "Being special at something gives customers a reason to choose you."),
    ("Which is a good goal for the stand?", "Sell 50 cups of lemonade on Saturday", "Sell a lot of lemonade someday",
     "Be the best lemonade stand in the whole world",
     "A good goal is clear and can be measured, so you know when you've reached it."),
]
# (statement, is it true, why)
_STAND_FACTS = [
    ("A business can be small, like a lemonade stand, or huge, like a car maker.", True,
     "Businesses come in every size. They all sell something people want."),
    ("A business only needs customers on its first day.", False,
     "A business needs customers every day to keep going."),
    ("Customers are the people who pay a business for what it makes or does.", True,
     "Customers buy the products or the work. Without them there is no business."),
    ("If a stand has a big sign, it doesn't need to treat customers kindly.", False,
     "A sign brings people over once. Kindness brings them back."),
    ("Running a pretend business is a good way to learn how real ones work.", True,
     "Planning, selling and counting money at a pretend stand are the same skills real owners use."),
]

_STAND_RULES = [
    ("Why do businesses have rules to follow?", "To keep people safe and treat everyone fairly",
     "To make sure every business sells the same things", "So the town can collect more money",
     "Rules are written after people learn what keeps others safe."),
    ("Before pouring lemonade, what should every worker do?", "Wash their hands with soap",
     "Rinse their hands with water only", "Wipe their hands on a napkin",
     "Soap and water wash germs away. Water alone or a napkin doesn't."),
    ("Why should the lemonade stay in a cooler with ice?", "Germs grow faster in warm drinks",
     "Cold lemonade tastes a bit sweeter", "Ice makes each pitcher last longer",
     "Cold drinks stay safe longer. Warm ones let germs grow."),
    ("A cup fell on the ground. What should you do with it?", "Throw it away and use a clean one",
     "Wipe it off with a napkin and use it", "Rinse it in the cooler's ice water",
     "A dropped cup isn't clean anymore, and the cooler water would spread the germs. Use a new one."),
    ("A customer asks if the cookies have nuts. What's the right move?", "Check the label and tell them honestly",
     "Say they probably don't, since most don't", "Tell them to pick a different snack",
     "Nuts can make some people very sick. Always check and tell the truth."),
    ("What is a food allergy?", "When someone's body reacts badly to a food",
     "When someone doesn't like the taste of a food", "When a food has gone bad from sitting out",
     "An allergy can be serious, so food sellers say what's in their food."),
    ("Who checks that real food businesses follow safety rules?", "Food safety inspectors", "The town's mayor",
     "The business's own customers", "Inspectors visit food businesses to make sure the rules are followed."),
    ("What is a fine?", "Money paid as a penalty for breaking a rule", "Money paid to the town for a permit",
     "Money a customer adds as a thank-you",
     "A fine is a penalty for breaking a rule. It costs money that could have gone to growing the business."),
    ("Why do some real stands need a permit?", "It's the town's permission to sell there",
     "It's a receipt for the supplies", "It's a sign that the lemonade tastes good",
     "A permit says the town has agreed the stand can sell in that spot."),
    ("You notice a loose tablecloth that someone could trip on. What should you do?",
     "Fix it or tell a grown-up right away", "Warn customers to watch their step",
     "Wait until the stand closes, then fix it", "Fixing a small problem early stops someone getting hurt."),
    ("Why write down when the cooler was last cleaned?", "So everyone knows it was done, and when",
     "So the teacher can grade the cleaning", "So nobody has to clean it again",
     "A written record shows the work was done and when it's due again."),
    ("What should you do if you're not sure about a rule?", "Ask a grown-up who knows",
     "Do what the last group did", "Choose the quickest way",
     "Asking is the smart way to get it right."),
    ("The ice ran out and the lemonade is getting warm. What's the safest choice?",
     "Stop selling until there's more ice", "Sell the warm lemonade at a lower price",
     "Sell it quickly before it gets warmer", "Safety comes before sales. Wait until the drinks are cold again."),
    ("Why should the stand always give the right change?", "It's honest and keeps customers' trust",
     "The teacher checks the cash box later", "It makes the line move faster",
     "Honest change shows customers they can trust you."),
    ("The sign says \"Fresh-squeezed\", but the lemonade is made from a powder. Is that OK?",
     "No: signs should tell the truth", "Yes, if it tastes just as good", "Yes, if the price is low",
     "Signs and ads must be honest about what you sell."),
    ("Rules for a business are a bit like...", "The rules of a board game", "A list of tips you can skip",
     "Suggestions from friends",
     "Like game rules, business rules keep things fair and safe, and they work because everyone follows them."),
    ("When should safety rules be followed?", "Every day, even the busiest ones", "Mostly when an inspector visits",
     "On the first day, until everyone knows them",
     "Accidents can happen any day, so rules count every day."),
    ("Why keep raw eggs away from snacks that are ready to eat?", "Germs from raw food can spread to other food",
     "The eggs might crack if they're too close", "Raw eggs make snacks taste different",
     "Keeping raw food apart stops germs from spreading."),
    ("What's a good way to keep the stand's area safe?", "Keep the walkway clear of all boxes",
     "Stack spare boxes beside the table", "Put the cooler where customers walk",
     "A clear, tidy walkway keeps customers and workers from tripping."),
    ("If someone gets hurt at the stand, what should you do first?", "Get a grown-up to help right away",
     "Find a bandage and fix it yourself", "Finish serving the customer first",
     "When someone is hurt, getting a grown-up's help comes first."),
]
_STAND_RULE_FACTS = [
    ("Washing hands with soap helps stop germs from spreading.", True,
     "Soap and water wash germs away before they reach food."),
    ("A business only has to follow rules when an inspector is watching.", False,
     "Rules count every day, not only on inspection day."),
    ("A small problem is best left alone until it gets bigger.", False,
     "Small problems grow. Fixing them early is cheaper and safer."),
    ("Telling customers the truth about what's in the food is part of selling food.", True,
     "People with allergies need true answers to stay safe."),
    ("Busy days are a good time to skip safety steps.", False,
     "Busy days are when mistakes happen most. Safety steps count every day."),
]

_STAND_MONEY = [
    (f"{CLASS_BUSINESS} sold 10 cups at $1 each. How much money came in?", "$10", "$1", "$11",
     "10 cups × $1 = $10. That's the stand's revenue: all the money customers paid."),
    ("What is revenue?", "Every dollar coming in from sales", "The money left after paying for supplies",
     "The money spent on lemons and cups", "Revenue is all the money that comes in from sales."),
    ("What is a cost?", "Money the business spends", "Money customers pay the business",
     "Money saved for next week", "Costs are what a business pays for, like lemons and cups, so it can sell."),
    ("The stand took in $20 and spent $8 on lemons, sugar and cups. What was the profit?", "$12", "$28", "$8",
     "Profit = revenue − costs: $20 − $8 = $12."),
    ("What is profit?", "The money left after paying the costs", "All the money that came in",
     "The price of one cup of lemonade", "Profit is what's left once the costs are paid."),
    ("Lemons cost more this week, and the price per cup stays the same. What happens to the profit?",
     "It goes down", "It goes up", "It stays exactly the same",
     "Higher costs with the same price leave less money over."),
    ("A cup costs 25¢ to make and sells for $1. How much is left over on each cup?", "75¢", "$1.25", "25¢",
     "$1.00 − 25¢ = 75¢ left over on each cup."),
    ("A customer pays with $5 for 2 cups at $1 each. How much change do they get?", "$3", "$2", "$4",
     "2 cups cost $2. $5 − $2 = $3 in change."),
    ("Why might the stand lower its price on a chilly day?", "Fewer people want cold drinks, so a deal can help",
     "Lemons always cost less on chilly days", "Customers expect lower prices in the morning",
     "When fewer people are buying, a lower price can bring more customers."),
    ("What could the class do with the stand's profit?", "Save some, buy supplies or give to a good cause",
     "Spend it all on the first day", "Split it before paying for supplies",
     "Profit can be saved, used to grow, or shared, once the costs are paid."),
    ("What is a budget?", "A plan for spending money", "A list of customers' names",
     "A record of yesterday's sales", "A budget is a spending plan made before you buy."),
    ("The stand has $15 to spend. Lemons cost $6 and cups cost $4. How much is left for sugar and ice?", "$5",
     "$10", "$25", "$6 + $4 = $10 spent. $15 − $10 = $5 left."),
    ("Why keep a record of every sale?", "To know how much came in and what sold best",
     "So the sign can show the day's total", "Because the bank asks for one every day",
     "A record shows what's working and catches mistakes."),
    ("A big bag of lemons costs $3 and makes 12 cups. A small bag costs $1 and makes 3 cups. Which is the better"
     " deal for each cup?", "The big bag", "The small bag", "They cost the same for each cup",
     "The big bag is 25¢ a cup ($3 ÷ 12). The small bag is about 33¢ a cup ($1 ÷ 3)."),
    ("Which is a smart way to set a price?", "Cover the costs and stay fair", "Charge what the stand next door does",
     "Pick a round number that feels right",
     "A good price pays for the costs and feels fair to customers. Other stands' prices are only a guide."),
    ("What does it mean to save money?", "Keep some for later", "Spend it on supplies right away",
     "Lend it to a friend", "Saving means putting money aside for later."),
    ("The stand sold 30 cups on Saturday and 20 on Sunday. How many cups in all?", "50", "10", "40",
     "30 + 20 = 50 cups."),
    ("Each cup costs 20¢ to make. What do 10 cups cost to make?", "$2", "20¢", "$10",
     "10 × 20¢ = 200¢, which is $2."),
    ("Why is a surprise cost, like a spilled pitcher, a problem?", "It uses up money that would have been profit",
     "It means the price has to go up for good", "It makes the stand sell fewer cups",
     "Surprise costs come straight out of what would have been left over."),
    ("Who decides how a class business spends its money?", "The class, with the teacher",
     "The student who holds the cash box", "The student who sold the most cups",
     "In a class business, money decisions are made together."),
]
_STAND_MONEY_FACTS = [
    ("Profit is what's left after paying the costs.", True, "Revenue minus costs is profit."),
    ("Revenue and profit always mean the same thing.", False,
     "Revenue is all the money in. Profit is what's left after costs."),
    ("Counting the money at the end of the day helps catch mistakes.", True,
     "Checking the cash box against the sales record shows if something went wrong."),
    ("A business should spend money before it knows how much it has.", False,
     "Know what you have first, then plan what to spend."),
    ("Saving a little from each day's sales can pay for supplies later.", True,
     "Small amounts saved often add up."),
]

_STAND_TEAM = [
    ("Why give each person a job at the stand?", "So the work gets done and is shared fairly",
     "So each person can stay at one job all day", "So the teacher can see who works hardest",
     "Sharing the jobs gets everything done and keeps it fair."),
    ("Which job list is fair?", "Everyone takes turns at every single job", "Each person keeps the job they're best at",
     "The first to arrive picks their job",
     "Taking turns shares the fun jobs and the hard ones, and everyone learns them all."),
    ("Two teammates want the same job. What's a fair way to decide?", "Take turns, or flip a coin",
     "Give it to whoever asked first", "Let the older one have it",
     "A fair way to decide keeps the team happy."),
    ("A teammate has a new idea for the sign. What should a good teammate do?", "Listen to the idea and then talk about it",
     "Keep the old sign, since it already works", "Say it's a good idea, then change nothing",
     "Listening to ideas helps the team find the best ones."),
    ("You finished your job early. What's a helpful thing to do?", "Ask your teammates if anyone needs help",
     "Start a new job you like better", "Take a break until the end",
     "Helping out makes the whole team stronger."),
    ("You made a mistake counting the change. What should you say?", "\"I made a mistake. Let's fix it.\"",
     "\"The cash box was a mess already.\"", "\"It's only a little, so it's fine.\"",
     "Owning a mistake and fixing it builds trust."),
    ("What does a good leader do?", "Helps the team do its best work", "Does the hardest jobs alone",
     "Makes every decision for the team", "Good leaders help everyone do well."),
    ("A teammate looks upset. What's a kind first step?", "Ask them quietly if they're okay",
     "Give them an easier job without asking", "Let them be until they feel better",
     "Checking in shows you care about your teammates."),
    ("Why should the team agree on a plan before opening?", "So everyone knows just what to do",
     "So the plan can't change later", "So the leader doesn't have to explain",
     "A shared plan keeps everyone on track."),
    ("How should the team treat every customer?", "Kindly and fairly, the same for all", "Extra nicely if they're a friend",
     "Quickly, so the line keeps moving", "Every customer deserves the same kind, fair service."),
    ("A teammate keeps breaking a team rule. What's a good first step?", "Talk with them kindly, in private",
     "Tell the whole class about it", "Do their part of the work for them",
     "Talking calmly first is fair. Ask the teacher for help if it keeps happening."),
    ("What's the best way to share an idea in a team meeting?", "Wait your turn and speak clearly",
     "Say it first, before others start", "Write it down and keep it for later",
     "Taking turns lets everyone be heard."),
    ("The team disagrees about the price. What helps most?", "Share reasons, listen, then decide",
     "Let the leader choose without a vote", "Use last week's price to avoid arguing",
     "Hearing every reason helps the team make a good choice."),
    ("Why say thank you to teammates?", "It shows you notice their work", "It's what the teacher expects",
     "It makes the day go by faster", "Thanks shows people their work matters, so they want to keep helping."),
    ("What does it mean to be reliable?", "People can count on you to do what you said", "You're the fastest worker",
     "You always have the best ideas", "Reliable people do what they said they'd do."),
    ("Your job is pouring, but the cash box is busy. What's a team player move?",
     "Offer to help, if the cashier wants it", "Take over the cash box yourself", "Keep pouring, since that's your job",
     "Offering help, and asking first, is how good teams work."),
    ("Why is it important to listen to quieter teammates?", "They may have great ideas too",
     "The teacher asks everyone to talk", "It keeps the meeting short",
     "Good ideas can come from anyone on the team."),
    ("At the end of the day, what should the whole team do?", "Clean up the stand together",
     "Let the cleanup team do it", "Leave it for the next group",
     "Cleaning up together is fair and quick."),
    ("A customer is rude to a teammate. What's the best response?", "Stay calm and get the teacher if needed",
     "Tell the customer they're being rude", "Ask them to leave the line",
     "Staying calm and getting a grown-up keeps things safe."),
    ("What makes a team strong?", "Trust, fairness and helping each other", "One leader who decides everything",
     "Everyone working on their own jobs alone", "Strong teams trust and help each other."),
]
_STAND_TEAM_FACTS = [
    ("A good leader listens to people who disagree.", True, "Different views help a team find the best idea."),
    ("Good teammates hide mistakes from the team.", False, "Good teammates own mistakes and fix them together."),
    ("Taking turns at the jobs is a fair way to share the work.", True, "Turns share the fun and the hard jobs."),
    ("Teams work best when only one person talks.", False, "Teams work best when everyone can share ideas."),
    ("Saying sorry and fixing a mistake builds trust.", True, "People trust someone who owns up and makes it right."),
]

_STAND_CARDS = {
    "classstand": (
        (f"Welcome to {CLASS_BUSINESS}!", f"Your class runs a pretend lemonade stand called {CLASS_BUSINESS}."
                                          " Let's learn how a business works by running it."),
        ("What is a business?", "A business is a group of people who make something or do work that others pay"
                                " for."),
        ("Customers", "Customers are the people who buy from a business. Happy customers come back."),
        ("Products and services", "A product is something you sell, like a cup of lemonade. A service is work you"
                                  " do for someone, like washing a car."),
        ("Your adventure", "Each short lesson has five questions. Get most of them right to unlock the next one!"),
    ),
    "classrules": (
        ("Rules keep people safe", "A business that sells food follows rules so nobody gets sick or hurt."),
        ("Clean hands", "Wash your hands with soap before pouring, and use clean cups."),
        ("Keep it cold", "Cold drinks stay in a cooler with ice. Germs grow faster when it's warm."),
        ("Tell the truth", "Signs, prices and answers about what's in the food should always be true."),
        ("Who checks?", "In real life, inspectors check that food businesses follow the rules. Breaking them can"
                        " mean a fine: money paid as a penalty."),
    ),
    "classmoney": (
        ("Revenue", "Revenue is all the money customers pay the business. 10 cups at $1 each is $10."),
        ("Costs", "Costs are what the stand spends: lemons, sugar, cups and ice."),
        ("Profit", "Profit is the money left over after paying all the costs: revenue minus costs. $10 in and $4 spent leaves $6."),
        ("Budget", "A budget is a plan for how much money to spend on each thing, made before you buy."),
        ("Saving", "Saving some money each day helps pay for next week's lemons."),
    ),
    "classteam": (
        ("A team of owners", "In a class business, the whole class works together, like owners."),
        ("Jobs", "Pouring, selling, counting money, making signs: each person has a job, and everyone takes turns."),
        ("Listen and share", "Good teammates listen, share their ideas and decide together."),
        ("Own mistakes", "Everyone makes mistakes. Saying \"Let's fix it\" earns trust."),
        ("Be kind", "Treat customers and teammates kindly and fairly, every time."),
    ),
}
_STAND_POOLS = {
    "classstand": (_STAND_QUESTIONS, _STAND_FACTS),
    "classrules": (_STAND_RULES, _STAND_RULE_FACTS),
    "classmoney": (_STAND_MONEY, _STAND_MONEY_FACTS),
    "classteam": (_STAND_TEAM, _STAND_TEAM_FACTS),
}

# The track's worlds, in order: the class worlds, then worlds about running any
# business that suit a class. Not: the family company, the app's lights and
# reminders, hiring and letting people go, taxes, loans, and the Rule Quests.
CLASSROOM_TOPICS = (60, 2, 61, 62, 7, 63, 9, 10, 14, 18, 19, 22, 34, 37, 30, 38)

# For the teacher guide: what each world teaches, and two questions to talk
# about after it, in plain words.
CLASS_GUIDE = {
    "classstand": ("What a business is, who its customers are, and products and services, through the class's"
                   " pretend lemonade stand.",
                   ("If our class ran a real stand, what would we sell, and who would buy it?",
                    "What is the difference between a product and a service? Name one of each from our town.")),
    "words": ("Everyday business words: revenue, cost, profit, customer, budget and more.",
              ("Which word was new to you? Use it in a sentence about our stand.",
               "Where have you heard one of these words outside school?")),
    "classrules": ("Why businesses follow rules: clean hands, cold drinks, honest signs and allergies.",
                   ("What rules would keep customers at our stand safe?",
                    "Why might a town ask a stand to get a permit?")),
    "classmoney": ("Revenue, costs and profit with small numbers, making change, budgets and saving.",
                   ("If lemons cost more, what could the stand do?",
                    "What would you do with the stand's profit, and why?")),
    "talk": ("Polite, clear speaking and writing: greetings, emails and owning up to mistakes.",
             ("Act out greeting a customer. What makes a greeting friendly?",
              "How would you write a thank-you note to a customer?")),
    "classteam": ("Sharing jobs fairly, listening, deciding together and sorting out disagreements.",
                  ("How should our class decide who does each job?",
                   "What can a team do when two people disagree?")),
    "ownit": ("Taking responsibility: keeping promises and owning mistakes.",
              ("Tell about a time you fixed a mistake. How did it feel?",
               "Why do people trust someone who owns up?")),
    "grit": ("Keeping going when things get hard, and learning from setbacks.",
             ("What was hard for you at first but got easier?",
              "What would you say to a friend who wants to give up?")),
    "customers": ("Treating customers well so they come back, and handling complaints.",
                  ("What makes you want to go back to a shop?",
                   "How should we answer a customer who isn't happy?")),
    "pricing": ("How businesses choose prices: costs, value and other sellers.",
                ("How would you price a cup of lemonade? What did you think about?",
                 "Why can the same thing cost different amounts in different places?")),
    "budget": ("Planning money before spending it: needs, wants and keeping track.",
               ("Make a budget for a class party with $20.",
                "What is the difference between a need and a want?")),
    "marketing": ("Telling people about what you sell: signs, flyers and honest ads.",
                  ("Design a sign for our stand. What must it say?",
                   "What makes an ad honest?")),
    "ethics": ("Honesty, fairness and doing the right thing when nobody is watching.",
               ("What would you do if a customer paid too much by mistake?",
                "Why does fairness matter in a business?")),
    "cyber": ("Staying safe online: passwords, tricks and keeping private things private.",
              ("What makes a strong password?",
               "What should you do if a message asks for personal information?")),
    "goals": ("Setting clear goals and the steps to reach them.",
              ("Set a goal for our stand. How will we know we reached it?",
               "What small step could you take today toward a goal?")),
    "startup": ("Going from an idea to open for business: a problem to solve, customers and a simple plan.",
                ("What problem at our school could a business solve?",
                 "Who would its first customers be?")),
}

# Questions a class never gets: about a family's own company or relatives, or
# about the app itself.
_NOT_FOR_CLASS = re.compile(
    r"\byour (family|parents|uncle|little brother|brother|sister)\b|\bfamily('s)? (shop|store|company|business"
    r"|bakery|pizza|team)\b|\b(omniarmor|aegizyn)\b|\binherit", re.I)


def _for_class(*texts):
    return not any(_NOT_FOR_CLASS.search(text) for text in texts)


def _interleave(choices, facts, size):
    """Up to size items: one true-or-false fact in each lesson of
    LESSON_QUESTIONS, the rest multiple choice, in order."""
    items, facts = [], list(facts)
    while len(items) < size and (choices or facts):
        lesson = choices[:LESSON_QUESTIONS - 1] if facts else choices[:LESSON_QUESTIONS]
        del choices[:len(lesson)]
        if facts:
            lesson = lesson + [facts.pop(0)]
        items.extend(lesson)
    return items[:size]


def _balanced(facts):
    """True and false facts taking turns, so "False" is never the safe guess."""
    trues = [f for f in facts if f[1]]
    falses = [f for f in facts if not f[1]]
    out = []
    while trues or falses:
        for side in (trues, falses):
            if side:
                out.append(side.pop(0))
    return out


@functools.lru_cache(maxsize=None)
def classroom_pool(world_number):
    """A Classroom world's fixed list of questions, in lesson order: lesson n
    is items (n-1)*LESSON_QUESTIONS to n*LESSON_QUESTIONS. The same list every
    time (a fixed seed per world)."""
    w = WORLDS[world_number]
    rng = random.Random(f"classroom:{w.key}")
    size = CLASS_MAX_STAGES * LESSON_QUESTIONS
    company = CLASS_BUSINESS
    if w.key in _STAND_POOLS:
        rows, facts = _STAND_POOLS[w.key]
        choices = [_choice(rng, p, best, [w1, w2], why) for p, best, w1, w2, why in rows]
        tf = [_truefalse(*f) for f in _balanced(list(facts))]
        rng.shuffle(choices)
        return _mix_formats(w.key, tuple(_interleave(choices, tf, size)), LESSON_QUESTIONS)
    if w.key in _BANK:
        bank = _BANK[w.key]
        rows = [q for q in bank["questions"] if _for_class(*q[:5])]
        order = list(range(len(rows)))
        rng.shuffle(order)
        rows = [rows[i] for i in sorted(order, key=lambda i: (rows[i][5], order.index(i)))]
        choices = [_choice(rng, p, best, [w1, w2], why) for p, best, w1, w2, why, _ in rows]
        facts = [f for f in bank["facts"] if _for_class(f[0], f[2])]
        rng.shuffle(facts)
        tf = [_truefalse(*f) for f in _balanced(facts)]
        return _mix_formats(w.key, tuple(_interleave(choices, tf, size)), LESSON_QUESTIONS)
    if w.key == "words":
        words = _quiz_words((word, meaning) for word, meaning in GLOSSARY if _for_class(word, meaning))
        picked = words[:16] + rng.sample(words[16:], max(0, min(len(words) - 16, size - 16)))
        out = [_word_question(rng, word, meaning, words, n) for n, (word, meaning) in enumerate(picked[:size])]
        return _mix_formats(w.key, tuple(out[:len(out) // LESSON_QUESTIONS * LESSON_QUESTIONS]), LESSON_QUESTIONS)
    pools = {"talk": PRO_TALK, "ownit": OWN_IT, "grit": GRIT, "respect": RESPECT, "customers": CUSTOMERS,
             "compete": COMPETE, "moves": MOVES, "hiring": HIRING}
    rows = [r for r in pools[w.key] if _for_class(*r)]
    rng.shuffle(rows)
    return tuple(_choice(rng, situation.format(company=company), best.format(company=company), [bad1, bad2], why)
                 for situation, best, bad1, bad2, why in rows[:size])


def classroom_stages(world_number):
    """How many lessons a Classroom world has: one per LESSON_QUESTIONS of its
    questions, at most CLASS_MAX_STAGES."""
    return min(CLASS_MAX_STAGES, len(classroom_pool(world_number)) // LESSON_QUESTIONS)


def _fresh(q, rng):
    """A copy of a pool question with its options in a new order (a true or
    false question keeps True first, and a light question keeps green,
    yellow, red: the order of a traffic light)."""
    if q.kind == "match" and q.parts and q.parts.get("pool"):
        return _rotated(q, rng)
    if q.kind in ("truefalse", "light", "match", "sort"):
        # A match or sort question keeps its pieces in place: its options are their codes.
        return Question(q.prompt, list(q.options), q.answer, q.explain, q.kind, parts=q.parts)
    right = q.options[q.answer]
    options = list(q.options)
    rng.shuffle(options)
    return Question(q.prompt, options, options.index(right), q.explain, q.kind, parts=q.parts, look=q.look)


def _classroom_quiz(w, stage, rng):
    if w.kind == "final":
        everything = [q for n in CLASSROOM_TOPICS for q in classroom_pool(n)]
        questions = [_fresh(q, rng) for q in rng.sample(everything, CLASSROOM.final_questions)]
    else:
        lesson = classroom_pool(w.number)[(stage - 1) * LESSON_QUESTIONS:stage * LESSON_QUESTIONS]
        questions = [_fresh(q, rng) for q in lesson]
    rng.shuffle(questions)
    return questions


def _stand_story(key):
    return lambda company, industry_ids: list(_STAND_CARDS[key])


WORLDS_BY_KEY = {w.key: w for w in ALL_WORLDS}
_CONTENT.update({key: _stand_story(key) for key in _STAND_CARDS})

CLASSROOM = Track(CLASSROOM_KEY, 4, "Classroom", "Class", "Run a pretend class business, one short lesson at a time",
                  "rocket", CLASSROOM_TOPICS, CLASS_MAX_STAGES, 1, 0, LESSON_QUESTIONS, LESSON_QUESTIONS, 0.6, 0.6,
                  10, 0, _EASY_MIX, stage_plan=tuple((n, classroom_stages(n)) for n in CLASSROOM_TOPICS))
TRACKS[CLASSROOM.key] = CLASSROOM
# Each family world's real lesson count, now that the pools exist.
TRACK_LIST = [dataclasses.replace(t, stage_plan=tuple((n, family_stages(t, n)) for n in t.topics))
              for t in TRACK_LIST]
TRACKS.update({t.key: t for t in TRACK_LIST})
TOTAL_LEVELS = TRACKS[DEFAULT_TRACK].total
# Every track, the Classroom one too: for what is stored per track (progress,
# certificates). The track picker offers TRACK_LIST, the families' tracks.
ALL_TRACKS = TRACK_LIST + [CLASSROOM]


# The Classroom track's last world: the Owner's Challenge's place (the same
# world number, so certificates work alike), named for a class.
CLASS_FINAL_WORLD = dataclasses.replace(FINAL_WORLD, title="Class Challenge", tagline="Earn your class certificate")


def world_for(t, number):
    """A world as a track shows it: the Classroom track calls the last one the Class Challenge."""
    if t.key == CLASSROOM_KEY and number == FINAL_WORLD.number:
        return CLASS_FINAL_WORLD
    return WORLDS.get(number)


def class_guide():
    """The teacher guide: each Classroom world in order, with what it teaches,
    its lessons, about how long they take and two questions to talk about."""
    out = []
    for w in CLASSROOM.topic_worlds:
        teaches, talk = CLASS_GUIDE[w.key]
        lessons = CLASSROOM.stages(w)
        out.append({"world": w, "unit": UNIT_NAMES.get(w.unit, ""), "teaches": teaches, "talk": talk,
                    "lessons": lessons, "minutes": lessons * LESSON_MINUTES})
    return out
