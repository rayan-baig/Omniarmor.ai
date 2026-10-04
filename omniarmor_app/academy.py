# -*- coding: utf-8 -*-
"""Future Owner Academy: a game-like course for the kids who may one day run
the family company.

Four tracks, each with its own progress:
    Launchpad (Basic)          1,350 levels: 16 core worlds x 50 stages, the
                               Owner's Challenge (50) and 50 industry Rule Quests x 10.
    Trailblazer (Intermediate) 2,700 levels: all 43 worlds x 50, plus the same.
    Summit (Advanced)          5,400 levels: 43 x 100, Challenge 100, Rule Quests x 20.
    Titan Mastery              15,700 levels: 43 x 300, Challenge 300, Rule Quests x 50.

Stage 1 of a world teaches the lesson; later stages add questions, harder
questions, a higher pass mark and review from other worlds, and every tenth
stage is a boss round. Lessons are built from the company's own name,
industries and compliance rules, so a child learns about the business they
may inherit. The newer worlds draw on the question banks in academy_bank.
Quizzes are generated from a seed, so the same attempt always shows the same
questions and can be checked on the server without storing the answers.

Children don't get accounts: a family member adds a learner profile with only
a nickname and a picture, so no child's personal information is collected.
"""

import math
import random
import secrets
from dataclasses import dataclass

from omni_armor_rules import CATALOG, evaluate
from omni_armor_rules.rule import _fmt as format_quantity

from .academy_bank import load_expansions, load_worlds
from .catalog import INDUSTRIES, date_mode

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
     "Hi Ms. Lopez,", "HEY MS. LOPEZ!!! GREAT NEWS FOR YOU!!!", "yo lopez, quick thing about your order",
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
     "Let me find out and get back to you by tomorrow.",
     "Give your best guess with a confident voice so you sound like an expert.",
     "Tell them that's not your department and they'll have to figure it out.",
     "It's fine not to know. Promise to find out, say when, and keep that promise."),
    ("A meeting is ending. What's a professional way to finish?",
     "Thanks for your time. I'll send a summary by Friday.",
     "Okay, I think we're done here, so I'm going to go now. Bye, everyone.",
     "Start packing up and leave while the last person is still talking.",
     "Thank people for their time and say what you'll do next and when."),
    ("Which sentence sounds the most professional?",
     "We will deliver the materials on Monday.",
     "We'll probably bring all the stuff over to you sometime early next week, hopefully.",
     "Your things will get there whenever our truck has some free time.",
     "Clear words and a specific day help everyone plan."),
    ("You need help from a coworker who is busy. What do you say?",
     "When you have a minute, could you help me with this report?",
     "I need you to drop what you're doing and help me with this report right now.",
     "Keep walking over to their desk until they finally stop and answer you.",
     "Asking politely and respecting their time makes people glad to help."),
    ("How should you end a business email?",
     "Thank you,\nSam", "Ok bye, talk later, have fun with the rest of your day lol", "Leave it with no ending or name at all",
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
     "Keeping going when things get hard",
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
     "Standing tall, eye contact and a calm, clear voice",
     "Talking loudly over everyone so they know who's in charge",
     "Checking your phone so people see how busy and important you are",
     "Confident body language and calm words show you're ready to lead."),
    ("What builds respect that lasts?",
     "Keeping your promises every time",
     "Reminding everyone of your big wins so they know how good you are",
     "Making people a little afraid of you so they always do what you say",
     "When people know you always do what you say, they respect and trust you."),
    ("Someone is rude to you in a meeting. What does a respected leader do?",
     "Stay calm and answer politely and firmly",
     "Answer back even louder so everyone sees you won't be pushed around",
     "Get up and walk out of the room to show how upset you are",
     "Staying calm under pressure is one of the strongest signs of a leader."),
    ("How should a leader treat the newest, youngest worker?",
     "With the same respect as everyone else",
     "Mostly ignore them until they've been there long enough to matter",
     "Give them all the boring jobs, since new people have to earn their place",
     "Leaders who respect everyone earn respect from everyone."),
    ("You walk into a room to speak to the team. What helps you look and sound like a leader?",
     "Be prepared, speak slowly, and look at people",
     "Read every word from your phone so you don't forget anything important",
     "Arrive a few minutes late so everyone is already waiting for you",
     "Preparation is the secret behind confidence."),
    ("Which leader do people follow most?",
     "One who listens, decides fairly and credits the team",
     "One who makes every decision alone and takes the credit for the wins",
     "One who changes their mind every day to keep everyone happy",
     "Fairness and giving credit make people want to follow you."),
]
HIRING = [
    ("When is a good time to hire a new person?",
     "When there's more steady work than the team can handle",
     "Whenever a friend or relative asks you for a job, even if there's no work",
     "During one extra-busy week, even if it will be slow again next month",
     "Hire when the work and the money are there to support a new job."),
    ("What's the most important thing to look for in a new hire?",
     "Honesty, a good attitude and the right skills",
     "Whoever is a close friend, since you already know you'll get along",
     "Whoever asks for the lowest pay, no matter how well they do the job",
     "Skills can be taught; honesty and attitude are harder to change."),
    ("What should a good job interview include?",
     "The same fair questions for every candidate",
     "Personal questions about their religion, family plans and age",
     "Different easy questions for the people you already like best",
     "Fair, job-related questions help you choose well and follow the law."),
    ("A new worker starts on Monday. What helps them succeed?",
     "A welcome, clear training and a buddy to ask",
     "Leave them alone so they learn by figuring everything out themselves",
     "Give them the hardest job on day one to see if they can handle it",
     "Good training turns new hires into great teammates."),
    ("Before hiring, what should an owner check?",
     "That the business can afford the pay every month",
     "That the new person likes the same music and sports as the team",
     "Nothing much, since you can always figure out the pay later",
     "A job is a promise to pay someone, so plan the budget first."),
    ("Two people apply. One has great skills but was rude to the receptionist. What should you think about?",
     "How they treat everyone shows who they are",
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
     "Great quality, friendly service and kept promises",
     "The lowest prices in town, even if the service is rude and slow",
     "Lots of flashy ads, even if the product often breaks quickly",
     "Happy customers return and tell their friends."),
    ("A customer has a complaint. What's the best way to handle it?",
     "Listen, apologize, fix it fast and thank them",
     "Explain why they're wrong until they agree and leave you alone",
     "Leave the message unanswered and hope they forget about it",
     "A well-handled complaint can turn an upset customer into a loyal fan."),
    ("How can a business find out what customers want?",
     "Ask them, listen, and watch what they buy",
     "Guess based on what the owner personally likes best",
     "Copy whatever the biggest company in town is selling this year",
     "The best ideas often come straight from customers."),
    ("What is word of mouth?",
     "Customers telling others about the business",
     "A special kind of ad that plays on the radio every morning",
     "A secret password customers say to get a discount",
     "Word of mouth is free advertising earned by treating people well."),
    ("A loyal customer has ordered for five years. What's a smart move?",
     "Thank them and offer something special",
     "Raise their prices, since they'll probably keep ordering anyway",
     "Treat them like any new customer so everything stays fair",
     "Keeping a customer is usually cheaper than finding a new one."),
    ("What should a business promise in its ads?",
     "Only what it can truly deliver",
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
     "To survive slow months and surprises",
     "Saving is pointless, because spending money is how a business grows",
     "So the owner can secretly hide it from the team and the bank",
     "An emergency fund keeps the company safe when things go wrong."),
    ("A big decision is coming up. What's a smart way to decide?",
     "Gather facts, weigh pros and cons, ask advisors",
     "Flip a coin, since big decisions are mostly about luck anyway",
     "Do whatever the loudest person in the room says you should do",
     "Good decisions come from good information."),
    ("A deal sounds too good to be true. What should you do?",
     "Slow down and check the details carefully",
     "Say yes right away before someone else grabs the great deal",
     "Send them the money they ask for to show you're serious",
     "If it seems too good to be true, it often is."),
    ("What is a goal that helps a business grow?",
     "\"10 new customers by June\"",
     "\"Do a little better someday, whenever we get the chance\"",
     "\"Have no goals, so nobody feels disappointed later\"",
     "Specific goals with deadlines turn dreams into plans."),
    ("Someone asks for a favor that would break a company rule. What's a pro move?",
     "Politely say no and explain the rule",
     "Say yes this one time so they keep liking you",
     "Ignore their message and hope they never ask about it again",
     "Saying a respectful no protects you and the company."),
]


@dataclass
class Question:
    prompt: str
    options: list
    answer: int
    explain: str
    kind: str = "choice"  # "choice", "light" or "truefalse"
    review: bool = False


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
ALL_WORLDS = TOPIC_WORLDS + [FINAL_WORLD] + INDUSTRY_WORLDS
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

    @property
    def topic_worlds(self):
        return [WORLDS[n] for n in self.topics]

    @property
    def worlds(self):
        return self.topic_worlds + [FINAL_WORLD] + INDUSTRY_WORLDS

    @property
    def total(self):
        return (len(self.topics) * self.topic_stages + self.final_stages
                + len(INDUSTRY_WORLDS) * self.industry_stages)

    def stages(self, w):
        if w.kind == "final":
            return self.final_stages
        if w.kind == "industry":
            return self.industry_stages
        return self.topic_stages

    def has(self, w):
        return w.kind != "topic" or w.number in self.topics


_ALL_TOPICS = tuple(w.number for w in TOPIC_WORLDS)
_EASY_MIX = ((0.3, {1: 3, 2: 2, 3: 0}), (0.7, {1: 1, 2: 2, 3: 1}), (1.01, {1: 0, 2: 2, 3: 2}))
TRACK_LIST = [
    Track("launchpad", 0, "Launchpad", "Basic", "Blast off with the basics", "rocket",
          tuple(w.number for w in ORIGINAL_WORLDS), 50, 50, 10, 5, 8, 0.6, 0.8, 10, 5, _EASY_MIX),
    Track("trailblazer", 1, "Trailblazer", "Intermediate", "Every world of business", "flame",
          _ALL_TOPICS, 50, 50, 10, 5, 8, 0.6, 0.8, 10, 5, _EASY_MIX),
    Track("summit", 2, "Summit", "Advanced", "Twice the stages, tougher questions", "peak",
          _ALL_TOPICS, 100, 100, 20, 6, 10, 0.7, 0.85, 12, 6,
          ((0.25, {1: 2, 2: 2, 3: 1}), (0.6, {1: 0, 2: 2, 3: 2}), (1.01, {1: 0, 2: 1, 3: 3}))),
    Track("titan", 3, "Titan Mastery", "Mastery", "The ultimate mastery program", "titan",
          _ALL_TOPICS, 300, 300, 50, 8, 12, 0.75, 0.9, 15, 8,
          ((0.1, {1: 1, 2: 2, 3: 2}), (1.01, {1: 0, 2: 1, 3: 3}))),
]
TRACKS = {t.key: t for t in TRACK_LIST}
DEFAULT_TRACK = "launchpad"
TOTAL_LEVELS = TRACKS[DEFAULT_TRACK].total  # the basic track; see Track.total for the others
RANKS = [(0, "Rookie"), (5, "Apprentice"), (15, "Team Captain"), (40, "Manager"), (100, "Executive"),
         (250, "Future Owner"), (600, "Business Legend"), (1000, "Tycoon")]
CERTIFICATES = [(1, "Future Owner"), (100, "Silver Future Owner"), (500, "Gold Future Owner"),
                (None, "Platinum Business Legend")]


def track(key):
    return TRACKS.get(key) or TRACKS[DEFAULT_TRACK]


def world(number):
    return WORLDS.get(number)


def level_id(t, world_number, stage):
    """One number per level, for storing progress. Each track has its own range."""
    return t.index * 1_000_000 + world_number * 1000 + stage


def is_boss(w, stage):
    return w.kind == "topic" and stage % 10 == 0


def question_count(t, w, stage):
    if w.kind == "final":
        return t.final_questions
    if w.kind == "industry":
        return t.industry_questions
    steps = t.max_questions - t.min_questions
    count = t.min_questions + min(steps, (stage - 1) * 5 // t.topic_stages)
    return count + (2 if is_boss(w, stage) else 0)


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


def _scaled(t, table):
    """Rank and certificate goals grow with the track's size."""
    scale = t.total / TRACKS[DEFAULT_TRACK].total
    return [(t.total if needed is None else (needed if needed <= 1 else round(needed * scale)), title)
            for needed, title in table]


RANK_TIERS = [title for _, title in RANKS]


def rank_for(levels_done, t=None):
    return _title_for(_scaled(t or TRACKS[DEFAULT_TRACK], RANKS), levels_done)


def rank_tier(levels_done, t=None):
    """0 for Rookie up to 7 for Tycoon: how fancy the learner's picture gets."""
    return RANK_TIERS.index(rank_for(levels_done, t))


def next_rank(levels_done, t=None):
    for needed, title in _scaled(t or TRACKS[DEFAULT_TRACK], RANKS):
        if levels_done < needed:
            return needed, title
    return None


def certificate_for(levels_done, final_passed, t=None):
    t = t or TRACKS[DEFAULT_TRACK]
    if not final_passed:
        return None
    title = _title_for(_scaled(t, CERTIFICATES), levels_done)
    return title if t.key == DEFAULT_TRACK else f"{t.name} {title}"


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
    return [r for r in pool if r.kind in ("max", "min") and date_mode(r) is None and r.unit and _light_cases(r)]


def _since_rules(pool):
    return [r for r in pool if date_mode(r) == "since" and 7 <= r.limit <= 3650]


def _light_question(rule, value, found):
    word = "limit" if rule.kind == "max" else "minimum"
    explain = {
        "CLEARED": "The reading is safely inside the rule, so the light is green.",
        "WARNING": "The reading is close to the rule's edge, so the light is yellow: plan a fix before it becomes a problem.",
        "BLOCKED": "The reading is past the rule's edge, so the light is red: stop and fix it right away.",
    }[found]
    prompt = (f"Rule: {rule.title}. The {word} is {format_quantity(rule.limit, rule.unit)}. "
              f"Today's reading is {format_quantity(value, rule.unit)}. Which light should OmniArmor show?")
    return Question(prompt, list(LIGHTS), LIGHT_INDEX[found], explain, "light")


# --- Level 1 ------------------------------------------------------------

def _company_questions(rng, company, industry_ids, stage=1):
    sectors = _sectors(industry_ids)
    others = [INDUSTRIES[i]["sector"] for i in INDUSTRIES if i not in industry_ids]
    if len(others) < 2:
        others = ["Space travel", "Ice cream trucks", "Toy making"]
    decoy_names = ["Sunny Side Snacks", "Rocket Repair Co.", "Blue Lake Toys", "Maple Street Bakery"]
    return [
        _choice(rng, "What is the name of your family's company?", company,
                rng.sample([n for n in decoy_names if n != company], 2),
                f"Your family's company is {company}."),
        _choice(rng, f"What kind of work does {company} do?", rng.choice(sectors), rng.sample(others, 2),
                f"{company} works in {', '.join(s.lower() for s in sectors)}."),
        _choice(rng, "What is a business?",
                "A group of people who make or do something that others pay for",
                ["A place where you only play games", "A kind of school"],
                "A business makes products or does work that customers pay for."),
        _choice(rng, "Who does a business serve?", "Its customers", ["Only the owner", "Nobody"],
                "Businesses exist to help their customers. Happy customers come back."),
        _truefalse("Following the rules helps keep workers and customers safe.", True,
                   "Rules protect the people who work at the company and the people it serves."),
    ]


def _company_story(company, industry_ids):
    sectors = ", ".join(s.lower() for s in _sectors(industry_ids))
    return [
        ("Hi, I'm Armo!", f"I'm a shield, and my job is helping {company} follow the rules that keep everyone safe."),
        ("Your family's company", f"{company} works in {sectors}. Customers count on it to do that work safely and well."),
        ("What is a business?", "A business is a group of people who make something or do work that others pay for."),
        ("Your adventure", f"Someday you might help lead {company}. Let's get you ready, one level at a time!"),
    ]


# --- Level 2 ------------------------------------------------------------

def _words_questions(rng, company, industry_ids, stage=1):
    picked = rng.sample(GLOSSARY, 5)
    questions = []
    for word, meaning in picked:
        others = [m for w, m in GLOSSARY if w != word]
        questions.append(_choice(rng, f"What does \"{word}\" mean?", meaning, rng.sample(others, 2),
                                 f"{word}: {meaning}"))
    return questions


def _words_story(company, industry_ids):
    sample = GLOSSARY[:6]
    return [
        ("Talk like a business person", "Every job has its own words. Learning them helps you understand meetings, emails and reports."),
    ] + [(word, meaning) for word, meaning in sample] + [
        ("Your Word Bank", "You can find every word in the Word Bank on your level map anytime."),
    ]


# --- Level 3 ------------------------------------------------------------

def _rules_questions(rng, company, industry_ids, stage=1):
    rule = rng.choice(_company_rules(industry_ids))
    return [
        _choice(rng, "What is a fine?", "Money a business must pay for breaking a rule",
                ["A prize for doing a good job", "A kind of thin noodle"],
                "A fine is a penalty. It costs the company money that could have gone to growing the business."),
        _choice(rng, "Who checks that a business follows the rules?", "Inspectors",
                ["Customers' pets", "Nobody ever checks"],
                "Inspectors visit businesses to make sure rules are followed."),
        _choice(rng, f"Here's a real rule for {company}: \"{rule.title}.\" Why do rules like this exist?",
                "To keep people safe and things fair", ["To make work boring", "So nobody has any fun"],
                "Rules are written after people learn what keeps others safe."),
        _choice(rng, f"What could happen if {company} ignored an important rule?",
                "It could pay a fine or have to close for a while", ["Nothing, ever", "It would win a trophy"],
                "Breaking rules can cost money, customers and even the right to stay open."),
        _truefalse("It's smart to fix a problem as soon as you find it.", True,
                   "Small problems are cheaper and safer to fix early, before they grow."),
    ]


def _rules_story(company, industry_ids):
    rule = _company_rules(industry_ids)[0]
    return [
        ("Rules are like game rules", "Games are fair and fun because everyone follows the same rules. Businesses work the same way."),
        ("Who makes them?", "Governments write rules to keep workers, customers and neighbors safe. Inspectors check them."),
        ("A real one", f"One of {company}'s rules: \"{rule.title}.\" OmniArmor keeps an eye on it every day."),
        ("Why it matters", "Breaking a rule can mean a fine (money paid as a penalty), losing customers, or someone getting hurt."),
    ]


# --- Level 4 ------------------------------------------------------------

def _lights_questions(rng, company, industry_ids, stage=1):
    pool = _light_rules(_company_rules(industry_ids))
    if len(pool) < 3:
        pool = _light_rules(_all_rules())
    by_level = {"CLEARED": [], "WARNING": [], "BLOCKED": []}
    for rule in pool:
        for found, value in _light_cases(rule).items():
            by_level[found].append((rule, value, found))
    chosen = []
    for found in ("CLEARED", "WARNING", "BLOCKED"):
        if by_level[found]:
            chosen.append(rng.choice(by_level[found]))
    rest = [case for cases in by_level.values() for case in cases if case not in chosen]
    rng.shuffle(rest)
    used_rules = {c[0].key for c in chosen}
    for case in rest:
        if len(chosen) >= 5:
            break
        if case[0].key not in used_rules:
            chosen.append(case)
            used_rules.add(case[0].key)
    rng.shuffle(chosen)
    return [_light_question(rule, value, found) for rule, value, found in chosen[:5]]


def _lights_story(company, industry_ids):
    return [
        ("Three lights", "OmniArmor checks every rule and shows a light, just like a traffic light."),
        ("Green", "All good! The reading is safely inside the rule."),
        ("Yellow", "Careful! It's getting close to the limit. Time to plan a fix."),
        ("Red", "Stop! The rule is broken. Fix it right away to protect people and avoid a fine."),
    ]


# --- Level 5 ------------------------------------------------------------

def _calendar_questions(rng, company, industry_ids, stage=1):
    pool = _since_rules(_company_rules(industry_ids)) or _since_rules(_all_rules())
    rule = rng.choice(pool)
    limit = int(rule.limit)
    done = rng.randint(1, limit - 1)
    left = limit - done
    wrong = [w for w in {limit + done, done, abs(left - 7) or left + 3, left + 10} if w != left and w >= 0]
    late_rule = rng.choice(pool)
    late_limit = int(late_rule.limit)
    is_late = rng.random() < 0.5
    ago = late_limit + rng.randint(1, 20) if is_late else rng.randint(1, late_limit - 1)
    start = rng.randrange(7)
    ahead = rng.randint(2, 5 + min(stage, 50) // 5)
    due_day = WEEKDAYS[(start + ahead) % 7]
    return [
        _choice(rng, f"\"{rule.title}\" must be done at least every {limit} days. It was last done {done} days ago. "
                     "How many days are left?", str(left), [str(w) for w in sorted(wrong)[:2]],
                f"{limit} − {done} = {left} days left."),
        _choice(rng, f"\"{late_rule.title}\" must be done every {late_limit} days. It was last done {ago} days ago. Is it late?",
                "Yes, it's overdue" if is_late else "No, there's still time",
                ["No, there's still time" if is_late else "Yes, it's overdue"],
                f"{ago} days is {'more' if is_late else 'less'} than {late_limit} days."),
        _choice(rng, "When does OmniArmor send the first reminder before a deadline?", "30 days before",
                ["The day after it's late", "Never"],
                "Reminders go out 30, 7 and 1 day before, on the day, and every week if it's late."),
        _choice(rng, "After a job is finished, someone presses \"Done today.\" What happens?",
                "The countdown starts over for next time", ["The rule disappears forever", "Nothing happens"],
                "Most jobs repeat, like a yearly checkup. Done today starts the next countdown."),
        _choice(rng, f"Today is {WEEKDAYS[start]}. A job is due in {ahead} days. Which day is that?", due_day,
                rng.sample([d for d in WEEKDAYS if d != due_day], 2),
                f"Count forward {ahead} days from {WEEKDAYS[start]} and you land on {due_day}."),
    ]


def _calendar_story(company, industry_ids):
    pool = _since_rules(_company_rules(industry_ids)) or _since_rules(_all_rules())
    example = pool[0]
    return [
        ("Jobs that repeat", "Lots of jobs must be done again and again, like checking safety gear every year."),
        ("A real example", f"\"{example.title}\" has to be done at least every {int(example.limit)} days."),
        ("Counting days", "OmniArmor counts the days since a job was last done, so nobody has to remember."),
        ("Friendly reminders", "It sends reminders 30, 7 and 1 day before a deadline, so the team is never surprised."),
    ]


# --- Level 6 ------------------------------------------------------------

def _money_questions(rng, company, industry_ids, stage=1):
    scale = 1 + min(stage, 50) // 10
    revenue = rng.randrange(8000 * scale, 20000 * scale + 1, 500 * scale)
    costs = rng.randrange(3000 * scale, revenue - 1000 * scale, 500 * scale)
    profit = revenue - costs
    fine = rng.choice([500, 1000, 1500, 2000])
    fix = rng.choice([100, 200, 300])
    penalty = rng.choice([1000, 2500, 5000])
    return [
        _choice(rng, f"Pretend {company} earned {money(revenue)} this month and spent {money(costs)}. What is the profit?",
                money(profit), [money(revenue + costs), money(costs)],
                f"Profit = revenue − costs: {money(revenue)} − {money(costs)} = {money(profit)}."),
        _choice(rng, f"If the profit was {money(profit)} and the company paid a {money(fine)} fine, how much profit is left?",
                money(profit - fine), [money(profit + fine), money(profit)],
                f"A fine is a surprise cost: {money(profit)} − {money(fine)} = {money(profit - fine)}."),
        _choice(rng, "Which costs less?", f"Fixing a problem early for {money(fix)}",
                [f"Paying a fine of {money(penalty)} later"],
                "Preventing problems is almost always cheaper than paying for them later."),
        _choice(rng, "What is a cost?", "Money the business spends",
                ["Money customers pay", "A kind of coat"],
                "Costs are what the business pays for, like pay for workers, supplies and rent."),
        _choice(rng, "What can a business do with its profit?", "Save it, grow the company and reward its people",
                ["Throw it away", "Nothing at all"],
                "Profit helps a company grow, get through hard times, and take care of its team."),
    ]


def _money_story(company, industry_ids):
    return [
        ("Revenue", "Revenue is all the money customers pay the business."),
        ("Costs", "Costs are what the business spends: pay for workers, supplies, rent and more."),
        ("Profit", "Profit is what's left: revenue minus costs. Healthy businesses make a profit."),
        ("Surprise costs", "Fines are costs nobody plans for. Following the rules protects the profit."),
    ]


# --- Level 7 ------------------------------------------------------------

def _talk_questions(rng, company, industry_ids, stage=1):
    questions = []
    for situation, best, bad1, bad2, why in rng.sample(PRO_TALK, 5):
        questions.append(_choice(rng, situation, best.format(company=company), [bad1, bad2], why))
    return questions


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

def _team_questions(rng, company, industry_ids, stage=1):
    return [
        _choice(rng, f"Why does {company} keep a record of every change?",
                "So everyone can see who did what and when", ["To get people in trouble", "Because it's fun to type"],
                "Records help the team stay honest and show inspectors that the company did its job."),
        _choice(rng, "A worker tells you about a safety problem. What should a good leader do?",
                "Thank them and get it fixed", ["Ignore it", "Tell them to stop complaining"],
                "Leaders want to hear about problems early, so people stay safe."),
        _choice(rng, "Who can help when a rule is confusing?", "An expert, like a lawyer or an accountant",
                ["Guess and hope for the best", "A random video online"],
                "Smart owners ask experts. Nobody knows everything."),
        _choice(rng, "What's the best way to treat customers?", "Honestly and fairly",
                ["Only nicely when they're watching", "However you feel that day"],
                "Trust is a company's most valuable treasure."),
        _truefalse("A good owner hides mistakes from the team.", False,
                   "Good owners are honest about mistakes and fix them together."),
    ]


def _team_story(company, industry_ids):
    return [
        ("Owners lead people", f"A business is its people. Leading {company} means helping the team do great work."),
        ("Listen", "Good leaders listen to workers and customers, especially when they raise a problem."),
        ("Keep records", "OmniArmor's audit trail remembers who changed what, and when. That keeps everyone honest."),
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

def _scenarios(pool):
    def make(rng, company, industry_ids, stage=1):
        return [_choice(rng, situation.format(company=company), best.format(company=company), [bad1, bad2], why)
                for situation, best, bad1, bad2, why in rng.sample(pool, 5)]
    return make


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
    return Question(f"Rule: {rule.title}. OmniArmor asks: \"{rule.input}\" The answer is {word}. Which light?",
                    list(LIGHTS), LIGHT_INDEX[found], explain, "light")


def _rule_questions(rng, industry_id, index):
    rule = CATALOG[industry_id][index - 1]
    others = [r for i, rules in CATALOG.items() if i != industry_id for r in rules]
    sector = INDUSTRIES[industry_id]["sector"]
    lights = []
    if rule.kind in ("max", "min"):
        lights = [_light_question(rule, value, found) for found, value in _light_cases(rule).items()]
    else:
        lights = [_yes_no_light(rule, True), _yes_no_light(rule, False)]
    facts = [
        _choice(rng, f"Why does \"{rule.title}\" matter?", rule.cost, [r.cost for r in rng.sample(others, 2)],
                "Every rule protects something: people, money or the company's good name."),
        _choice(rng, f"If \"{rule.title}\" is broken, what should the team do?", rule.action,
                [r.action for r in rng.sample(others, 2)], "Knowing the fix ahead of time means acting fast."),
        _choice(rng, f"Which kind of business follows \"{rule.title}\"?", sector,
                rng.sample([INDUSTRIES[i]["sector"] for i in INDUSTRIES if i != industry_id], 2),
                f"This rule is one of the ten that matter most in {sector.lower()}."),
        _choice(rng, f"To check \"{rule.title}\", what does OmniArmor ask?", rule.input,
                [r.input for r in rng.sample(others, 2)], "OmniArmor asks a simple question or reading for every rule."),
    ]
    if date_mode(rule) == "since" and 7 <= rule.limit <= 3650:
        limit = int(rule.limit)
        done = rng.randint(1, limit - 1)
        left = limit - done
        facts.append(_choice(rng, f"\"{rule.title}\" must be done at least every {limit} days. It was last done "
                                  f"{done} days ago. How many days are left?", str(left),
                             [str(limit + done), str(left + 10)], f"{limit} − {done} = {left} days left."))
    rng.shuffle(lights)
    rng.shuffle(facts)
    questions = lights[:2] + facts
    questions = questions[:5]
    rng.shuffle(questions)
    return questions


def _rule_story(industry_id, index):
    rule = CATALOG[industry_id][index - 1]
    brand = INDUSTRIES[industry_id]["brand"]
    return [
        (f"{brand} rule {index} of {len(CATALOG[industry_id])}", rule.title),
        ("Why it matters", rule.cost),
        ("What OmniArmor checks", rule.input),
        ("If it goes wrong", rule.action),
    ]


# --- Question-bank worlds ------------------------------------------------------

def _weights_for(t, progress):
    for limit, weights in t.mix:
        if progress <= limit:
            return weights
    return t.mix[-1][1]


def _bank_questions(rng, key, count, progress, t):
    """count questions from a world's bank, harder as the learner goes deeper.
    About one in four is a quick true-or-false fact."""
    bank = _BANK[key]
    weights = _weights_for(t, progress)
    pool = [q for q in bank["questions"] if weights.get(q[5], 0) > 0] or list(bank["questions"])
    facts = list(bank["facts"])
    rng.shuffle(facts)
    picked = []
    while len(picked) < count and pool:
        if facts and rng.random() < 0.25:
            statement, truth, why = facts.pop()
            picked.append(_truefalse(statement, truth, why))
            continue
        total = sum(weights.get(q[5], 1) for q in pool)
        roll = rng.uniform(0, total)
        for i, q in enumerate(pool):
            roll -= weights.get(q[5], 1)
            if roll <= 0:
                break
        prompt, best, wrong1, wrong2, why, _level = pool.pop(i)
        picked.append(_choice(rng, prompt, best, [wrong1, wrong2], why))
    if key in _MATH_WORLDS and picked:
        picked[rng.randrange(len(picked))] = _money_math(rng, progress)
    return picked


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
    if len(question.options) == 3:
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


# --- Owner's Challenge -------------------------------------------------------

def _topic_questions(t, w, rng, company, industry_ids, stage, count, progress):
    if w.key in _BANK:
        return _bank_questions(rng, w.key, count, progress, t)
    return _CONTENT[w.key][1](rng, company, industry_ids, stage)[:count]


def _final_questions(t, rng, company, industry_ids, stage):
    """One question each from a random set of the track's topic worlds."""
    progress = (stage - 1) / max(1, t.final_stages - 1)
    questions, prompts = [], set()
    worlds = t.topic_worlds
    tries = 0
    while len(questions) < t.final_questions and tries < 200:
        tries += 1
        w = rng.choice(worlds)
        sub = random.Random(rng.random())
        options = _topic_questions(t, w, sub, company, industry_ids, max(1, int(progress * t.topic_stages)), 3, progress)
        fresh = [q for q in options if q.prompt not in prompts]
        if fresh:
            q = sub.choice(fresh)
            prompts.add(q.prompt)
            questions.append(q)
    return questions


def _final_story(t, company):
    return [
        ("The Owner's Challenge", f"{t.final_questions} questions from across the whole {t.name} track."),
        ("Your prize", f"Pass to earn your Future Owner Certificate for {company}, and keep going to upgrade it!"),
    ]


_CONTENT = {
    "company": (_company_story, _company_questions),
    "words": (_words_story, _words_questions),
    "rules": (_rules_story, _rules_questions),
    "lights": (_lights_story, _lights_questions),
    "calendar": (_calendar_story, _calendar_questions),
    "money": (_money_story, _money_questions),
    "talk": (_talk_story, _talk_questions),
    "team": (_team_story, _team_questions),
    "ownit": (_ownit_story, _scenarios(OWN_IT)),
    "grit": (_grit_story, _scenarios(GRIT)),
    "respect": (_respect_story, _scenarios(RESPECT)),
    "hiring": (_hiring_story, _scenarios(HIRING)),
    "toughcalls": (_toughcalls_story, _scenarios(TOUGH_CALLS)),
    "customers": (_customers_story, _scenarios(CUSTOMERS)),
    "compete": (_compete_story, _scenarios(COMPETE)),
    "moves": (_moves_story, _scenarios(MOVES)),
}


def _rule_index(industry_id, stage):
    return (stage - 1) % len(CATALOG[industry_id]) + 1


def story(t, world_number, stage, company, industry_ids):
    """The lesson cards. Stage 1 teaches the whole lesson; later stages show one
    reminder card so kids get straight to the challenge."""
    w = WORLDS[world_number]
    if w.kind == "industry":
        if stage > len(CATALOG[w.industry_id]):
            brand = INDUSTRIES[w.industry_id]["brand"]
            return [(f"{brand} review", "This stage mixes questions from several of the industry's rules. "
                                        "Remember the lights, the costs and the fixes!")]
        return _rule_story(w.industry_id, _rule_index(w.industry_id, stage))
    if w.kind == "final":
        cards = _final_story(t, company)
    elif w.key in _BANK:
        cards = _bank_story(w.key)
    else:
        cards = _CONTENT[w.key][0](company, list(industry_ids))
    if stage == 1:
        return cards
    if is_boss(w, stage):
        return [(f"Stage {stage}: boss round!", "More questions than usual, mixed from this world and the ones before. "
                                                "Take your time and read carefully.")]
    reminder = cards[(stage - 2) % len(cards)]
    return [(f"Stage {stage}: remember", f"{reminder[0]}: {reminder[1]}")]


def _industry_quiz(t, rng, w, stage):
    rules = len(CATALOG[w.industry_id])
    wanted = t.industry_questions
    if stage <= rules:
        questions = _rule_questions(rng, w.industry_id, stage)[:wanted]
        order = [i for i in range(1, rules + 1) if i != stage]
    else:
        # Review stages: questions from several of the industry's rules.
        questions = []
        order = list(range(1, rules + 1))
    rng.shuffle(order)
    prompts = {q.prompt for q in questions}
    for index in order * 2:
        if len(questions) >= wanted:
            break
        options = [q for q in _rule_questions(random.Random(rng.random()), w.industry_id, index)
                   if q.prompt not in prompts]
        if options:
            q = rng.choice(options)
            q.review = stage <= rules
            prompts.add(q.prompt)
            questions.append(q)
    rng.shuffle(questions)
    return questions


def _fill(questions, prompts, wanted, source, tries=60):
    """Adds questions from source() until there are enough, skipping repeats."""
    while len(questions) < wanted and tries > 0:
        tries -= 1
        for q in source():
            if len(questions) >= wanted:
                break
            if q.prompt not in prompts:
                prompts.add(q.prompt)
                questions.append(q)


def quiz(t, world_number, stage, company, industry_ids, seed):
    """The questions for one attempt. The same seed always gives the same quiz.
    Deeper stages ask more and harder questions and mix in review from earlier
    worlds; every tenth stage is a boss round with extra review."""
    w = WORLDS[world_number]
    rng = random.Random(seed)
    ids = list(industry_ids)
    if w.kind == "industry":
        return _industry_quiz(t, rng, w, stage)
    if w.kind == "final":
        return _final_questions(t, rng, company, ids, stage)
    wanted = question_count(t, w, stage)
    progress = (stage - 1) / max(1, t.topic_stages - 1)
    reviews = 3 if is_boss(w, stage) else (1 if wanted > 5 else 0)
    questions, prompts = [], set()
    _fill(questions, prompts, wanted - reviews,
          lambda: _topic_questions(t, w, random.Random(rng.random()), company, ids, stage, 5, progress))
    position = t.topics.index(w.number)
    earlier = [WORLDS[n] for n in t.topics[:position]]
    review_from = earlier if len(earlier) >= 3 else [WORLDS[n] for n in t.topics if n != w.number]
    start = len(questions)

    def review():
        source = rng.choice(review_from)
        return _topic_questions(t, source, random.Random(rng.random()), company, ids, stage, 2, progress)
    _fill(questions, prompts, wanted, review)
    for q in questions[start:]:
        q.review = True
    # A world with few distinct questions tops up from its own pool again.
    _fill(questions, prompts, wanted,
          lambda: _topic_questions(t, w, random.Random(rng.random()), company, ids, stage, 5, progress))
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
    w = WORLDS[world_number]
    rng = random.Random(seed)
    progress = (stage - 1) / 49
    return _topic_questions(TRACKS["trailblazer"], w, rng, DUEL_COMPANY, [], stage, DUEL_QUESTIONS, progress)


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
