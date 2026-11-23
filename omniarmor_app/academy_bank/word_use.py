"""Academy question bank: each business word used in a small scene (1.19.0).

Business Words used to ask "What does X mean?" five times in a row. Each word
here has one short scene with a gap where the word goes, which makes two more
kinds of question (academy._word_scene and academy._word_sentence):

- a scenario: "Which word fills the gap?", with the word and two others
- using the word: "Which sentence uses "Invoice" the right way?", with its own
  scene and two other words' scenes with "invoice" put in their gap (wrong)

Every gap reads "the ___" or a bare "___", so any word can be put in it and
still read as a sentence, and only the right word makes sense there. No
scene uses a word that is another word's answer for the same idea (the
kindred groups in word_ideas.py are never mixed in one question).
"""

GAP = "___"

WORD_SCENES = {
    "Revenue": "Mia sold 40 cups at $1 each, so before paying for anything the ___ was $40.",
    "Cost": "Lemons, sugar and cups came to $12: the ___ of making the lemonade.",
    "Profit": "The bake sale took in $90 and spent $30 on flour and eggs, so the ___ was $60.",
    "Customer": "A neighbor paid $2 for a cookie. She was the stand's first ___ today.",
    "Employee": "The bike shop pays Jordan every Friday for fixing flat tires. Jordan is one of the shop's workers, called the shop's ___.",
    "Invoice": "Leo sent Mrs. Kim the ___, listing the fence work and the $50 she owed.",
    "Budget": "Before the school fair, the class wrote down how much it could spend on posters, prizes and snacks: the ___.",
    "Contract": "The cafe and the bakery signed the ___, so both knew how many muffins came each week and for how much.",
    "Compliance": "The kitchen checks its fridge temperatures and hand sinks every day. Following every rule like that is ___.",
    "Deadline": "Posters must be in by Friday at noon. Friday at noon is the ___.",
    "Inventory": "Each night the shop counts the shirts and hats left on its shelves: its ___.",
    "Stakeholder": "Workers, customers, the landlord and the town all care how the market does. Each of them is called the market's ___.",
    "Inspector": "A visitor from the health office came to look at the restaurant's kitchen and fridges. She was the ___.",
    "Fine": "The food truck parked where it wasn't allowed and had to pay $100 to the city: the ___.",
    "Owner": "Grandpa started the store and still makes the final calls. He is the ___.",
    "Reputation": "Everyone says the pizza place is friendly and fast: the ___ it earned.",
    "Asset": "The bakery's big oven is worth $3,000 and helps it make money every day. The oven is the bakery's most valuable ___.",
    "Liability": "The shop still owes the bank $800 for its freezer: the shop's ___.",
    "Loan": "The bank gave the farm $5,000 to buy seeds, to be paid back over two years: the ___.",
    "Interest": "Ava borrowed $100 and has to pay back $105. The extra $5 is the ___.",
    "Credit score": "Sam always paid his bills on time, so the bank saw a high ___.",
    "Emergency fund": "When the van broke down, the shop paid for the repair from money it had set aside: the ___.",
    "Withdrawal": "Leo took $20 out of his savings account. The bank wrote down the ___.",
    "Investor": "Aunt Rosa gave the new juice bar $2,000, hoping to share in its success later. She is the ___ behind it.",
    "Dividend": "After a good year, each owner of a share got $10: the ___.",
    "Collateral": "To get the loan, the shop agreed the bank could keep its delivery van if it didn't pay: the van is ___.",
    "Bankruptcy": "The store owed far more than it could ever pay and went to court: ___.",
    "Cash flow": "Money comes in on weekends and goes out for rent on Mondays. Watching that movement is watching ___.",
    "Fixed cost": "The shop pays $900 rent every month, busy or not: its biggest ___.",
    "Break-even": "After selling 50 cups, the stand had made back exactly what it spent, with nothing extra: ___.",
    "Markup": "The shop buys a game for $20 and sells it for $30. The extra $10 added on is the ___.",
    "Discount": "The bookstore took $5 off every book for the holiday sale. The $5 off is the ___.",
    "Forecast": "From last summer, the shop guessed it would sell 500 cones in July: its ___.",
    "Quarter": "The company looks at its sales every three months. January to March is one ___.",
    "Tax": "Part of every sale goes to the government to pay for roads and schools: the ___.",
    "Audit": "An expert checked all the store's money records were right: the ___.",
    "Bookkeeping": "Every evening Maya writes down each sale and each thing she bought. That daily record-keeping is ___.",
    "Accountant": "At tax time the bakery hires an expert to do its numbers: the ___.",
    "Late fee": "The library book came back a week late, so an extra $2 was added on: the ___.",
    "Down payment": "For a $10,000 truck, the farm paid $2,000 at the start: the ___.",
    "Depreciation": "The laptop cost $1,000 new, but after three years it is worth $300. That drop in value is ___.",
    "Inflation": "A candy bar cost $1 last year and $1.10 now, like most prices: ___.",
    "Recession": "For months, many businesses sold less and lots of people lost jobs across the country. People called it the ___.",
    "Risk": "Opening a second shop could bring more sales, or it could lose money. That chance of losing is the ___.",
    "Diversify": "Instead of selling only lemonade, the stand also sells cookies and popcorn, to ___.",
    "Entrepreneur": "Priya had an idea for dog-walking, set it up herself and took the chance it might fail. She is the ___ behind it.",
    "Startup": "Two friends just began a new app company last month and are still figuring things out. Their young company is the ___.",
    "Nonprofit": "The animal shelter uses every dollar it gets to care for pets, not to make owners rich. The shelter is run as the ___.",
    "Franchise": "Lee pays a famous sandwich brand to open a shop using its name and recipes. Lee's shop is the brand's ___.",
    "Merger": "Two bakeries in town joined to become one bigger bakery: the ___.",
    "Succession plan": "Grandma wrote down who will run the store when she retires: the ___.",
    "CEO": "The person at the very top who leads the whole company and its managers is the ___.",
    "Mission": "The bike shop says its purpose every day is to get kids riding safely: its ___.",
    "Vision": "The cafe dreams of one day having a shop in every town in the state: its ___.",
    "Milestone": "The stand celebrated selling its 1,000th cup, a big step on the way to its goal. That cup was the ___.",
    "Prototype": "Before making 100 phone stands, Omar built one first try to test it: the ___.",
    "Innovation": "The pizza place invented a new box that keeps pizza hot twice as long. Everyone wanted the new ___.",
    "Productivity": "The team now packs 50 boxes an hour instead of 30: its ___ went up.",
    "Bottleneck": "Orders pile up because only one person can work the slow cash register: the ___.",
    "Quality control": "Before any cookie goes in a box, someone checks it isn't burnt or broken: ___.",
    "License": "The city gave the food truck official permission to sell food on its streets: the ___.",
    "Insurance": "The shop pays a little every month so that if a storm breaks its window, the repair is covered: ___.",
    "Landlord": "The bakery pays rent each month to the person who owns its building: the ___.",
    "Utilities": "Each month the shop pays for its electricity, water and heat: the ___.",
    "Agenda": "Before the meeting, everyone got the list of topics to talk about: the ___.",
    "Minutes": "Sam wrote down what the meeting decided, for everyone to read: the ___.",
    "Delegation": "The manager handed the supply orders to Ana, to focus on customers: ___.",
    "Accountability": "The order went out wrong and Kai said, \"My job, I'll fix it.\" That is ___.",
    "Confidential": "The customers' phone numbers are private and never shared: ___.",
    "Trademark": "The shop's name and its special logo are protected, so no other shop can use them. The logo is the shop's ___.",
    "Patent": "Lin invented a new kind of zipper, and the government says only she can make it for years: the ___.",
    "Copyright": "Max wrote a song for the store's ads, and the law says nobody can copy it without asking: the ___.",
    "Supplier": "The farm that sells the cafe its milk and eggs every morning is the cafe's ___.",
    "Wholesale": "The shop buys 500 pencils at once, for less each: buying ___.",
    "Retail": "The shop then sells those pencils one at a time to students who walk in: that is ___.",
    "Quote": "Before starting, the painter said the room would cost $400: the ___.",
    "Logistics": "Planning how the boxes get from the warehouse to every store on time is ___.",
    "Lead time": "New chairs arrive three weeks after they're ordered: the ___.",
    "Warehouse": "The online shop keeps its boxes of toys in a big building: the ___.",
    "Stockout": "Everyone wanted the new game, and by noon the shelf was empty with none left to sell. The shop had the ___.",
    "Receipt": "After paying, Zoe got a slip showing what she bought and paid: the ___.",
    "Refund": "The toy was broken, so the store gave back the $15 that was paid for it: the ___.",
    "Warranty": "The bike shop promises to fix any problem with the new bike for one year: the ___.",
    "Recall": "The company found a problem in its car seats and asked everyone to bring them back. Everyone heard about the ___.",
    "Demand": "In summer, many more people want ice cream. More people wanting it means more ___.",
    "Supply": "The farm grew plenty of apples for every store to sell: the ___ was big.",
    "Exports": "The farm ships its cheese to shops in other countries. That cheese is one of its ___.",
    "Imports": "The store sells bananas that are grown in other countries and brought in: ___.",
    "Logo": "The small picture of a smiling lemon on every cup and sign is the stand's ___.",
    "Slogan": "\"Squeezed fresh, served with a smile!\" is the stand's catchy ___.",
    "Advertising": "The bakery paid for a bus sign and a radio spot about itself: ___.",
    "Coupon": "Liam handed over a paper ticket that said \"$1 off any sandwich\": the ___.",
    "Market research": "Before opening, the stand asked 30 people what flavors they would buy: ___.",
    "Target market": "The toy shop's best buyers are parents of kids under ten: its ___.",
    "Competitor": "Another lemonade stand opened across the street, selling to the same people. It is the stand's ___.",
    "Monopoly": "Only one company sells water in the whole town, so nobody can buy it anywhere else. That company has the ___.",
    "Referral": "Mrs. Lopez told her friend to try the dog-walking business, and the friend signed up. That new customer came from the ___.",
    "Complaint": "A customer said the soup was cold and asked the manager to fix it. The manager wrote down the ___.",
    "Upsell": "The waiter asked, \"Would you like the large size for just 50 cents more?\" The waiter was trying the ___.",
    "Subscription": "Every month the family pays $10 and a box of books arrives at the door. The family pays for the ___.",
    "Pitch": "Maya had two minutes to tell the judges why her business idea would work: her ___.",
    "Negotiation": "The farmer wanted $5 a box and the cafe offered $3; they talked and settled on $4. Both sides were happy with the ___.",
    "Win-win": "The cafe got fresh bread cheaper and the baker got a steady order. Both sides call the deal the ___.",
    "Payroll": "Every two weeks the restaurant adds up how much it pays all of its workers: its ___.",
    "Wage": "Ben earns $12 for every hour he works at the market: his ___.",
    "Overtime": "Mia usually works 40 hours, but this week she worked 45. The extra 5 hours are ___.",
    "Benefits": "Besides her pay, the company gives Rosa paid holidays and health care: her ___.",
    "Raise": "After a great year, Leo's boss said he'll be paid $1 more every hour from now on. Leo was happy with the ___.",
    "Shift": "Ana works at the cafe from 7 in the morning until noon on Saturdays: her ___.",
    "Resume": "To apply, Kai sent a page of his skills, school and past jobs: his ___.",
    "Interview": "The manager met Kai to ask him questions and see if he fits the job: the ___.",
    "Onboarding": "On his first week, Kai learned the rules, met the team and got a tour: his ___.",
    "Feedback": "After the sale, the teacher told the class what went well and what to do better: ___.",
    "Mentor": "An older shop owner meets Zoe every month to share advice and help her grow: her ___.",
    "Intern": "A student works at the newspaper for the summer to learn how it's done. The newspaper calls the student the ___.",
    "Teamwork": "One poured, one took money, one made signs, and it ran smoothly: ___.",
}

# Words that could half-fit each other's scenes ("the logo is the shop's
# copyright", "the extra $5 is the profit"): never in one question, on top of
# the kindred groups (word_ideas.KINDRED_WORDS). A scene that names a word
# ("customers" in the stakeholders' scene) is never used against it either.
CLASHES = (
    {"Trademark", "Patent", "Copyright"},
    {"Delegation", "Teamwork"},
    {"Discount", "Coupon", "Upsell"},
    {"Feedback", "Complaint", "Referral", "Market research"},
    {"Asset", "Collateral", "Inventory"},
    {"Emergency fund", "Insurance"},
    {"Owner", "Landlord"},
    {"Lead time", "Deadline"},
    {"Budget", "Quote", "Forecast"},
    {"Markup", "Profit", "Interest", "Late fee", "Dividend"},
    {"Fine", "Late fee", "Tax"},
    {"Stakeholder", "Employee", "Customer", "Supplier", "Landlord"},
    {"Inflation", "Recession"},
    {"Startup", "Entrepreneur", "Franchise"},
    {"Agenda", "Minutes"},
)

# 1.21.0: a small picture beside each scene of "Which word fills the gap?", for where it happens (the stand, the
# bakery, the bank, the farm...). It shows the place the scene already names, never the word asked, so it gives
# nothing away. The first words that match a scene choose its picture; a scene with none gets a briefcase.
SCENE_PICTURES = (
    (r"lemonade|lemon|\bstand\b|\bcups?\b|poured", "🍋"),
    (r"cookie", "🍪"),
    (r"pizza", "🍕"),
    (r"ice cream|cones?\b", "🍦"),
    (r"bake sale|bakery|bakeries|bread|muffins?|baker\b", "🥐"),
    (r"cafe|juice bar", "☕"),
    (r"soup|restaurant|waiter|kitchen|sandwich|food truck", "🍽️"),
    (r"\bfarm|apples|bananas|cheese|seeds", "🚜"),
    (r"\bbank|savings|borrowed|loan", "🏦"),
    (r"\bbike", "🚲"),
    (r"\bdog|pets|animal", "🐶"),
    (r"\bbooks?\b|library|newspaper", "📚"),
    (r"\btoys?\b|\bgame\b", "🧸"),
    (r"shirts|jacket|\bhats\b", "👕"),
    (r"fence|painter|paint", "🎨"),
    (r"\bsong\b", "🎵"),
    (r"phone|\bapp\b|laptop", "📱"),
    (r"candy", "🍬"),
    (r"car seats|\bcar\b|\btruck\b|\bvan\b", "🚗"),
    (r"boxes|warehouse|chairs|pencils|zipper", "📦"),
    (r"meeting", "👥"),
    (r"school|science fair|\bclass\b|teacher|student|posters", "🏫"),
    (r"\bjob\b|\bhours?\b|\bworkers\b|\bpay\b|\bboss\b|company", "👔"),
    (r"\bcity\b|\btown\b|government|court|\blaw\b|country|countries", "🏛️"),
    (r"store|shop|market", "🏪"),
)


def scene_picture(scene):
    """The small picture for a scene (SCENE_PICTURES)."""
    import re
    for pattern, picture in SCENE_PICTURES:
        if re.search(pattern, scene, re.IGNORECASE):
            return picture
    return "💼"
