"""Academy question bank: sorting games (1.18.0).

In a world with a sorting set, each lesson after the first (while the items
last: five games a world) has one "sort" question in place of its
true-or-false one: three things to put in one of two bins
(safe or unsafe, honest or not, safe online or risky). It counts as one
question, right when all three are in the right bin.

Each item is (what someone does, which bin: 0 or 1, the fact behind it).
The fact is what the lesson's card teaches; it never repeats the item's own
words, so the game asks the learner to use the idea, not to spot a sentence.
Every item is clearly one or the other for any business, a class stand
included.
"""

# Which world uses which set: (bin 0, bin 1, the question's title, items).
SAFE_AT_WORK = ("Safe", "Unsafe", "Safe or unsafe? Sort all three.", [
    ("Washing your hands before you touch food", 0, "Clean hands keep germs off the food people eat."),
    ("Wiping up a spill as soon as you see it", 0, "A wet floor makes people slip, so spills get cleaned at once."),
    ("Keeping cold drinks on ice all day", 0, "Germs grow fast in warm food and drinks; cold keeps them slow."),
    ("Asking a grown-up before using a sharp knife", 0, "Sharp tools are used with care and with permission."),
    ("Putting the first-aid kit where everyone can find it", 0, "Help works only if people can reach it quickly."),
    ("Throwing away food that fell on the ground", 0, "Food that touched the floor can carry dirt and germs."),
    ("Taping down a cord that crosses the walkway", 0, "Loose cords trip people up."),
    ("Telling an adult when something is broken", 0, "Broken things get fixed only when someone speaks up."),
    ("Stacking boxes in front of the exit door", 1, "Exits stay clear so everyone can get out fast."),
    ("Serving lemonade that sat out warm since yesterday", 1, "Drinks left warm for hours can make people sick."),
    ("Leaving a knife on the edge of the table", 1, "Sharp things are put away, never left where they can fall."),
    ("Running across a wet floor to save time", 1, "Hurrying on a slippery floor is how falls happen."),
    ("Using the same cloth for the floor and the cups", 1, "Dirty cloths spread germs from one place to another."),
    ("Skipping the safety check because it's a busy day", 1, "Safety rules count most on busy days, when mistakes happen."),
    ("Lifting a heavy crate alone instead of asking for help", 1, "Heavy loads are a two-person job, so nobody gets hurt."),
    ("Plugging many cords into one outlet to save trips", 1, "Too many plugs in one outlet can overheat and start a fire."),
])

SAFETY_FIRST = ("Safe", "Unsafe", "Safe or unsafe? Sort all three.", [
    ("Wearing gloves when using cleaning spray", 0, "Strong cleaners can hurt skin, so hands stay covered."),
    ("Keeping chemicals in their own labelled bottles", 0, "A label tells everyone what is inside and how to handle it."),
    ("Checking the fire extinguisher's gauge each month", 0, "An extinguisher has to be ready before a fire, not after."),
    ("Putting a wet-floor sign by a freshly mopped floor", 0, "A warning sign tells people to slow down before they slip."),
    ("Bending your knees to lift a box", 0, "Your legs, not your back, should do the lifting."),
    ("Reporting a near miss to the manager", 0, "A close call shows a danger to fix before someone is hurt."),
    ("Practising the fire drill until everyone knows the way out", 0, "In a real emergency, people do what they practised."),
    ("Keeping the walkways clear of boxes and bags", 0, "Clear paths stop trips and let people move fast in a hurry."),
    ("Pouring cleaner into an old drink bottle", 1, "Chemicals in a drink bottle can be mistaken for something to drink."),
    ("Propping the fire door open with a chair", 1, "Fire doors stay closed so smoke and flames can't spread."),
    ("Standing on a wobbly chair to reach a high shelf", 1, "A proper step stool or ladder stops falls."),
    ("Mixing two cleaners to make them stronger", 1, "Some cleaners make poison gas when they are mixed."),
    ("Ignoring a frayed power cord because it still works", 1, "Damaged cords can shock people or start fires."),
    ("Taking the guard off a machine to work faster", 1, "Guards keep fingers and hands out of moving parts."),
    ("Hiding an injury so you don't have to fill in a form", 1, "Every injury is reported, so it gets treated and fixed."),
    ("Leaving the freezer door open while you unload", 1, "Food warms fast with the door open, and warm food spoils."),
])

HONEST = ("Honest", "Not honest", "Honest or not? Sort all three.", [
    ("Giving back extra change a customer handed you by mistake", 0, "Fixing a mistake that helps you is still the right thing."),
    ("Telling a customer an item is out of stock when it is", 0, "Telling the truth keeps customers' trust, even when it's bad news."),
    ("Marking yesterday's cookies as day-old", 0, "Clear labels let customers choose for themselves."),
    ("Saying sorry and fixing an order you got wrong", 0, "Owning a mistake quickly builds trust."),
    ("Charging every customer the price on the sign", 0, "Posted prices are a promise to everyone."),
    ("Telling your partner you bought from your cousin's shop", 0, "Being open about a personal tie keeps choices fair."),
    ("Paying your helper the amount you agreed on", 0, "Keeping a deal is part of being fair."),
    ("Writing down the real number of cups you sold", 0, "True records are how a business plans and proves what it did."),
    ("Saying the lemonade has no sugar when it does", 1, "A false label can hurt people who are avoiding something."),
    ("Keeping a wallet someone left at your stand", 1, "Lost things are kept safe and returned to their owner."),
    ("Taking a few dollars from the cash box to pay back later", 1, "Money that isn't yours stays where it is, even for a while."),
    ("Posting a fake review of your own shop", 1, "Reviews are meant to be real customers' words."),
    ("Hiding a cheaper part inside a repair you charged full price for", 1, "Customers have a right to know what they are paying for."),
    ("Blaming a classmate for a mistake you made", 1, "Owning your mistakes is part of speaking up honestly."),
    ("Taking a gift from a supplier to pick their company", 1, "A gift meant to sway a choice is a kind of bribe."),
    ("Changing the date on a check you forgot to do", 1, "A record is only useful if it tells the truth."),
])

SAFE_ONLINE = ("Safe online", "Risky", "Safe online or risky? Sort all three.", [
    ("Using a long password that's different for each account", 0, "One stolen password shouldn't open every door."),
    ("Asking a grown-up before you download an app", 0, "Some downloads carry hidden bad software."),
    ("Locking the tablet when you walk away", 0, "A locked screen keeps others out of your accounts."),
    ("Checking who an email is really from before clicking", 0, "Tricksters copy names to make fake emails look real."),
    ("Turning on the second sign-in step, like a code by text", 0, "A second step stops someone who only has your password."),
    ("Keeping the shop's software up to date", 0, "Updates fix holes that attackers look for."),
    ("Logging out of the shop computer when you're done", 0, "The next person can't use an account that is signed out."),
    ("Telling an adult about a strange message", 0, "A trusted adult can check if a message is a trick."),
    ("Sharing your password with a friend who asks nicely", 1, "Passwords are private, even from friends."),
    ("Clicking a link that says you won a prize", 1, "Surprise prizes are a common trick to steal information."),
    ("Posting a photo that shows the shop's cash drawer code", 1, "Codes in photos can be read by strangers."),
    ("Using \"password123\" because it's easy to remember", 1, "Easy passwords are the first ones guessed."),
    ("Writing the card number of a customer on a sticky note", 1, "Card numbers are kept secret and never written down."),
    ("Joining free café Wi-Fi to check the shop's bank account", 1, "Public Wi-Fi can be watched by others."),
    ("Opening an attachment from someone you don't know", 1, "Unknown attachments can hide harmful software."),
    ("Telling a caller your account code because they sound official", 1, "Real companies never ask for your secret codes."),
])

SORT_SETS = {
    "rules": SAFE_AT_WORK,
    "classrules": SAFE_AT_WORK,
    "safety": SAFETY_FIRST,
    "ethics": HONEST,
    "cyber": SAFE_ONLINE,
}
