"""Balanced synthetic retail feedback generator with clause-level labels.

CSV columns: text, stars, category, aspects, aspect_sentiments, aspect_clauses, has_detail.

Key points:
  - 12 aspect categories incl. online_app, loyalty_sparks, gifting.
  - Each aspect is paired with the exact CLAUSE it came from (aspect_clauses),
    so the sentiment head trains on the clause, not the whole review. This fixes
    the "prices high but staff lovely" polarity swap.
  - positive / negative / neutral / sarcasm / mixed-polarity coverage.
  - stars correlated with category.
  - aspects attached only when a retail aspect word is in the clause.

Run:
    python -m app.llm.data_gen --per-class 12000 --out data/retail_feedback.csv
"""
from __future__ import annotations

import argparse
import csv
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

ASPECTS = [
    "product_quality",
    "availability",
    "staff_service",
    "checkout_payment",
    "delivery_online",
    "returns_refund",
    "store_environment",
    "price_value",
    "accessibility",
    "online_app",
    "loyalty_sparks",
    "gifting",
]

# -------------------------------------------------------------- slot banks

NOUNS: dict[str, list[str]] = {
    "product_quality": [
        "the sandwich", "the ready meal", "the strawberries", "the shirt",
        "the jeans", "the jacket", "the dress", "the cake", "the milk",
        "the bread", "the chicken", "the salad", "the cardigan", "the trousers",
        "the shoes", "the biscuits", "the yogurt", "the ham", "the jumper",
        "the coat", "the blouse",
    ],
    "availability": [
        "the shelves", "the stock levels", "the fresh bread section",
        "the strawberries", "the size I needed", "the colour I wanted",
        "the stocks of my size", "all the sizes", "the fitting room",
        "the sizes in store", "the stock", "the shelf",
    ],
    "staff_service": [
        "the colleague", "the manager", "the till assistant",
        "the fitting room assistant", "the woman at the bakery",
        "the man in the cafe", "the lady at returns", "the staff member",
        "the cashier", "the team", "the assistant",
    ],
    "checkout_payment": [
        "the queue", "the checkout", "the self-service till",
        "the card reader", "the payment", "the receipt", "the till",
        "the checkout experience",
    ],
    "delivery_online": [
        "my online order", "the delivery", "the parcel",
        "the courier", "the delivery driver", "the tracking",
        "my click-and-collect order",
    ],
    "returns_refund": [
        "the return", "the refund", "the exchange", "the replacement",
        "my returns experience", "the returns desk",
    ],
    "store_environment": [
        "the store", "the aisles", "the lighting", "the cafe area",
        "the fitting rooms", "the music", "the temperature in store",
        "the in-store experience", "the shop floor", "the atmosphere",
    ],
    "price_value": [
        "the prices", "the price of this", "the cost", "the value for money",
        "the pricing",
    ],
    "accessibility": [
        "the ramp", "the wheelchair access", "the lift", "the aisle width",
        "the accessible checkout",
    ],
    "online_app": [
        "the app", "the website", "the online account", "the mobile app",
        "the login", "the checkout page", "the online experience", "the site",
    ],
    "loyalty_sparks": [
        "the Sparks offers", "my Sparks points", "the rewards", "the vouchers",
        "the loyalty points", "the Sparks app", "the member offers",
    ],
    "gifting": [
        "the gift card", "the flowers", "the hamper", "the gift wrapping",
        "the birthday present", "the bouquet", "the gift selection",
    ],
}

POSITIVE_PRED: dict[str, list[str]] = {
    "product_quality": [
        "was delicious", "tasted amazing", "fitted perfectly",
        "washed beautifully", "was great quality", "looked lovely",
        "was properly fitting", "was really fresh", "was spot on",
    ],
    "availability": [
        "was fully stocked", "had everything I needed", "had plenty",
        "had all the sizes", "had my size in stock", "was well stocked",
        "had the colour I wanted", "had great variety",
    ],
    "staff_service": [
        "was so helpful", "went above and beyond", "was really friendly",
        "took the time to explain", "made my day", "was outstanding",
        "was really patient with me",
    ],
    "checkout_payment": [
        "was quick", "was efficient", "took no time at all",
        "was really smooth", "moved fast",
    ],
    "delivery_online": [
        "arrived early", "was packaged beautifully", "arrived on time",
        "arrived in perfect condition",
    ],
    "returns_refund": [
        "was processed instantly", "was handled brilliantly",
        "was really easy",
    ],
    "store_environment": [
        "felt welcoming", "was spotlessly clean", "had a lovely atmosphere",
        "was so good", "was really pleasant", "felt bright and tidy",
    ],
    "price_value": [
        "was great value", "was really fair", "was a bargain",
        "was reasonable",
    ],
    "accessibility": [
        "was easy to use", "was really well designed", "was spot on",
    ],
    "online_app": [
        "worked perfectly", "was really easy to use", "loaded quickly",
        "made ordering a breeze", "was smooth and simple",
    ],
    "loyalty_sparks": [
        "were brilliant this month", "saved me a fortune", "were really generous",
        "were easy to redeem", "made me feel valued",
    ],
    "gifting": [
        "arrived beautifully wrapped", "was a lovely touch", "looked stunning",
        "was perfect for the occasion", "went down a treat",
    ],
}

NEGATIVE_PRED: dict[str, list[str]] = {
    "product_quality": [
        "was stale", "was damaged", "fell apart after one wash",
        "was not fresh", "had a hole in it", "was overcooked",
        "tasted off", "shrunk in the wash", "faded immediately",
        "was not good quality", "wasn't fresh at all", "did not fit well",
        "was not worth it", "wasn't nice",
    ],
    "availability": [
        "was completely empty", "was sold out", "had nothing left",
        "was out of stock", "didn't have my size", "was never restocked",
        "was not well stocked", "wasn't available",
    ],
    "staff_service": [
        "was rude", "ignored me", "was unhelpful", "was impatient",
        "would not even look at me", "was dismissive",
        "left me waiting with no explanation",
        "was not so friendly", "was not very helpful", "wasn't friendly",
        "wasn't helpful at all", "was not welcoming", "was not polite",
        "didn't seem to care",
    ],
    "checkout_payment": [
        "took forever", "had only one till open", "froze mid-transaction",
        "overcharged me", "was painfully slow", "was a complete mess",
        "was not quick at all", "wasn't smooth",
    ],
    "delivery_online": [
        "still hasn't arrived", "arrived damaged", "was two weeks late",
        "was left in the rain", "went to the wrong address",
        "did not arrive on time", "wasn't on time",
    ],
    "returns_refund": [
        "was refused for no reason", "has not been processed",
        "has been pending for weeks", "was declined without explanation",
        "was not easy at all", "wasn't straightforward",
    ],
    "store_environment": [
        "was dirty", "was freezing cold", "was far too hot",
        "was too dim", "was too bright and hurt my eyes",
        "smelled awful", "was a mess",
        "was not clean", "wasn't welcoming", "was not pleasant",
        "did not feel welcoming",
    ],
    "price_value": [
        "is far too expensive", "has gone up again", "is poor value",
        "isn't worth it anymore", "is not good value", "wasn't worth the money",
    ],
    "accessibility": [
        "was blocked", "was broken", "was out of order",
        "was impossible to use", "was not accessible", "wasn't easy to use",
    ],
    "online_app": [
        "kept crashing", "was full of bugs", "would not let me log in",
        "froze at checkout", "was painfully slow", "threw an error every time",
        "did not work", "wasn't easy to use",
    ],
    "loyalty_sparks": [
        "never applied at the till", "disappeared from my account",
        "were useless this month", "would not redeem", "stopped working",
        "were not worth it", "weren't any good",
    ],
    "gifting": [
        "arrived damaged", "looked nothing like the photo", "was poorly wrapped",
        "turned up wilted", "was missing the card",
        "was not what I ordered", "wasn't nicely wrapped",
    ],
}

NEUTRAL_PRED: dict[str, list[str]] = {
    "product_quality": ["was okay", "was fine", "was average"],
    "availability": ["was fine", "had some things"],
    "staff_service": ["was polite", "was okay"],
    "checkout_payment": ["was normal", "was okay"],
    "delivery_online": ["arrived"],
    "returns_refund": ["was processed"],
    "store_environment": ["was quiet"],
    "price_value": ["was reasonable"],
    "accessibility": ["was there"],
    "online_app": ["was okay", "worked fine"],
    "loyalty_sparks": ["were there", "were okay"],
    "gifting": ["was fine", "was okay"],
}

# ---- M&S-specific vocabulary (Per Una, Autograph, Percy Pigs, Sparks wallet ...) ----
NOUNS["product_quality"] += [
    "the Per Una dress", "the Autograph jacket", "the Percy Pigs",
    "the Colin the Caterpillar cake", "the Dine In meal", "the fabric",
    "the stitching", "the waistband", "the fit", "the sizing",
]
NOUNS["delivery_online"] += ["my Click & Collect order", "the Click & Collect service"]
NOUNS["loyalty_sparks"] += ["the Sparks digital wallet", "my Sparks rewards", "the hot drink stamps"]
NOUNS["checkout_payment"] += ["the till queue", "the self-checkout"]
NOUNS["availability"] += ["the Dine In range", "the sizes"]
POSITIVE_PRED["product_quality"] += [
    "was brilliant", "was smashing", "was spot on", "was true to size",
    "was lovely", "was really comfortable",
]
POSITIVE_PRED["loyalty_sparks"] += ["was brilliant", "worked a treat"]
POSITIVE_PRED["checkout_payment"] += ["was brilliant", "was smashing"]
NEGATIVE_PRED["product_quality"] += [
    "was rubbish", "was shocking", "was baggy", "was too tight",
    "was a joke", "was useless",
]
NEGATIVE_PRED["loyalty_sparks"] += ["was glitchy", "was a joke", "was useless"]
NEGATIVE_PRED["checkout_payment"] += ["was shocking", "was rubbish", "was a joke"]
NEGATIVE_PRED["online_app"] += ["was glitchy", "was rubbish", "was useless"]
NEGATIVE_PRED["availability"] += ["was shocking", "was a joke"]

# Everyday UK adjectives, for every aspect, so common wording is never out of vocabulary.
GENERIC_POS = ["was amazing", "was excellent", "was fantastic", "was lovely", "was brilliant",
               "was great", "was superb", "was wonderful", "was perfect", "was smashing"]
GENERIC_NEG = ["was awful", "was terrible", "was rubbish", "was poor", "was disappointing",
               "was shocking", "was horrible", "was dreadful", "was a joke", "was useless"]
for _a in ASPECTS:
    POSITIVE_PRED[_a] += GENERIC_POS
    NEGATIVE_PRED[_a] += GENERIC_NEG

# Soft negatives and negated positives ("not so wow"), plus "not bad" style mild positives.
MILD_NEG = ["was not so wow", "was not that great", "was not great", "was not good",
            "was not as good as it used to be", "was underwhelming", "wasn't impressive",
            "was not up to scratch", "left a lot to be desired", "was meh", "wasn't brilliant",
            "was not amazing", "was not so good", "wasn't what I expected", "was not worth it",
            "wasn't up to much", "was not very good", "could have been so much better"]
MILD_POS = ["was not bad at all", "wasn't bad", "was not too bad", "was better than expected",
            "was pretty good", "was quite nice", "was really decent"]
for _a in ASPECTS:
    NEGATIVE_PRED[_a] += MILD_NEG
    POSITIVE_PRED[_a] += MILD_POS
NOUNS["store_environment"] += ["the in-store experience", "the whole in-store experience", "the shopping experience"]

# Verb-first phrasing: "Love the Percy Pigs", "Can't stand the queue".
SHORT_POS = ["love {n}", "always buy {n}", "can't beat {n}", "really like {n}",
             "big fan of {n}", "{n} is a must", "adore {n}"]
SHORT_NEG = ["hate {n}", "avoid {n}", "can't stand {n}", "not a fan of {n}",
             "fed up with {n}", "{n} is a joke", "{n} is not good enough"]
NEGATIVE_PRED["price_value"] += ["is a bit high", "is a little steep", "is too high", "is getting silly"]
NEGATIVE_PRED["checkout_payment"] += ["was completely off"]
NEGATIVE_PRED["product_quality"] += ["was completely off", "was way off"]
NOUNS["product_quality"] += ["the sizing on the trousers", "the sizing on the dress", "the sizing on the jacket"]

TIME_MARKERS = ["yesterday", "this morning", "this afternoon", "last Saturday",
                "yesterday evening", "on Tuesday", "earlier today", "last week"]

STORE_PREFIX = ["At Marble Arch", "At Stratford City", "At Bluewater", "In store",
                "At the food hall", "Visiting your Oxford Street branch"]

INTENSIFIERS_POS = ["really", "absolutely", "genuinely", "truly", "so", "very"]
INTENSIFIERS_NEG = ["really", "very", "absolutely", "incredibly", "pretty"]

# ---- Freeform phrase banks (no aspect, variety / robustness) ----

COMPLIMENT_PHRASES = [
    "The in-store experience was so good.",
    "I love shopping here, honestly.",
    "What a great visit this was.",
    "Everything was perfect from start to finish.",
    "Really impressed with the whole experience.",
    "Had a lovely time, as always.",
    "I was able to find everything I needed in the sizes I wanted.",
    "Glad that they have stocks of all the sizes in the stores.",
    "I always find what I'm looking for here.",
    "The quality of the products never disappoints.",
    "I'll definitely be coming back.",
    "Everything fitted perfectly.",
    "A really pleasant shop today.",
    "Can't fault the experience at all.",
    "I really liked the dresses and the fit was so perfect.",
    "The fit of the clothes was spot on.",
    "The quality of the fabric is lovely.",
    "The western dresses looked amazing.",
    "I was really pleased with my purchases.",
    "Found something lovely for a wedding.",
    "The food hall selection was wonderful today.",
    "The dessert section looks beautifully arranged.",
    "Such a calm and enjoyable shop.",
    "Lovely experience from start to finish.",
    "Top marks for today's visit.",
]

STRONG_COMPLIMENT_SUFFIX = [
    "I will be back.", "Truly exceptional service.", "This is why I shop here.",
    "Best visit in months.", "Honestly made my week.", "Beyond expectations.",
    "Hands down the best M&S I've been to.", "A proper 5-star trip.",
]

NEUTRAL_PHRASES = [
    "It was fine.", "Nothing to complain about.", "Standard experience really.",
    "Picked up what I needed and left.", "Just a normal shop.",
    "Nothing stood out either way.", "Can't rave or complain.",
    "An average visit.", "Did the job.",
    "It was okay, nothing special.", "Pretty average overall.",
    "Did what I needed to do.", "Normal M&S shop.",
    "Neither good nor bad really.", "Just popped in and out.",
]

COMPLAINT_PHRASES = [
    "Not a great visit at all.",
    "I'm pretty disappointed with my experience.",
    "This has put me off coming back for a while.",
    "Not what I expect from M&S.",
    "Rather let down today.",
    "Really frustrating experience.",
    "One thing which was concerning was the availability of sizes.",
    "The thing which bothered me was the lack of stock.",
    "Not available in all the sizes.",
    "Couldn't find my size anywhere.",
    "The shelves had hardly anything on them.",
    "Really wish you had more sizes in store.",
]


def _guess_aspect_from_hint(text: str = "") -> str:
    low = (text or "").lower()
    if any(k in low for k in ["queue", "till", "checkout"]):
        return "checkout_payment"
    if any(k in low for k in ["shelves", "shelf", "stock", "empty", "bare", "aisle still"]):
        return "availability"
    if any(k in low for k in ["staff", "colleague", "returns", "ignored"]):
        return "staff_service"
    if any(k in low for k in ["mould", "stale", "bread", "sandwich", "cake", "milk", "shirt", "dress"]):
        return "product_quality"
    if any(k in low for k in ["app", "website", "online", "login"]):
        return "online_app"
    if any(k in low for k in ["sparks", "points", "reward"]):
        return "loyalty_sparks"
    if any(k in low for k in ["gift", "flowers", "hamper", "bouquet"]):
        return "gifting"
    if any(k in low for k in ["table", "clean", "dirty"]):
        return "store_environment"
    return "store_environment"


# ---- Serious templates: (text, aspect) ----

SERIOUS_TEMPLATES: list[Callable[[random.Random], tuple[str, str]]] = [
    lambda r: (
        f"I found {r.choice(['glass','a shard of plastic','mould','a hair','a metal fragment'])} in "
        f"{r.choice(['my sandwich','the ready meal','the cake','my salad'])} "
        f"{r.choice(TIME_MARKERS)} and I had to see a doctor.",
        "product_quality",
    ),
    lambda r: (
        f"My child had an allergic reaction after eating {r.choice(['the biscuits','the ready meal','the sandwich'])}"
        f" - the allergen was not labelled correctly.",
        "product_quality",
    ),
    lambda r: (
        f"I've been overcharged twice on my card and no one has replied to my emails "
        f"in {r.choice(['weeks','a month','six weeks'])}.",
        "returns_refund",
    ),
    lambda r: (
        f"I was discriminated against by a member of staff at "
        f"{r.choice(['the till','the fitting room','returns'])} {r.choice(TIME_MARKERS)}.",
        "staff_service",
    ),
    lambda r: (
        f"My card was charged twice for the same order and the refund has still not arrived "
        f"after {r.choice(['two weeks','three weeks','a month'])}.",
        "returns_refund",
    ),
    lambda r: (
        f"I slipped on a wet floor near {r.choice(['the entrance','the dairy aisle','the bakery'])} "
        f"and injured my wrist - there was no warning sign.",
        "store_environment",
    ),
    lambda r: (
        "The delivery driver was aggressive and threatening when I asked about my missing parcel.",
        "delivery_online",
    ),
    lambda r: (
        f"I have been waiting {r.choice(['six weeks','two months','a month'])} for a refund that never came "
        f"and nobody responds to my messages.",
        "returns_refund",
    ),
    lambda r: (
        "Someone accessed my online account and placed orders I never made - this is a security breach.",
        "online_app",
    ),
]

# ---- Sarcasm templates: positive-sounding, actually negative. (text, aspect|fn) ----

SARCASM_TEMPLATES: list[Callable[[random.Random], tuple[str, object]]] = [
    lambda r: (
        f"Oh {r.choice(['great','wonderful','lovely','brilliant'])}, "
        f"{r.choice(['another long queue','a dirty table','a broken till','empty shelves again','no one at returns'])}. "
        f"Just what I needed today.",
        _guess_aspect_from_hint,
    ),
    lambda r: (
        f"Really 'impressed' with how {r.choice(['long','slow','painful'])} the "
        f"{r.choice(['queue','wait at the till','checkout'])} was today.",
        "checkout_payment",
    ),
    lambda r: (
        f"Love how {r.choice(['empty','bare','picked clean'])} the shelves are. "
        f"Really makes the shop feel {r.choice(['exciting','abundant','full'])}.",
        "availability",
    ),
    lambda r: (
        f"Wow, {r.choice(['so helpful','so attentive','so friendly'])} staff - "
        f"I only had to wait {r.choice(['30 minutes','an hour','forever'])} for anyone to notice me.",
        "staff_service",
    ),
    lambda r: (
        f"Thanks for the 'wonderful' {r.choice(['experience','service','welcome'])} - "
        f"I feel so {r.choice(['valued','looked after','appreciated'])} after being ignored by the staff.",
        "staff_service",
    ),
    lambda r: (
        f"Really 'enjoying' the {r.choice(['stale','mouldy','off'])} "
        f"{r.choice(['bread','sandwich','cake','milk'])} you sold me today.",
        "product_quality",
    ),
    lambda r: (
        f"{r.choice(['Great','Amazing','Lovely'])} to see the "
        f"{r.choice(['aisle still empty','mould on the bread','rude staff'])} again.",
        _guess_aspect_from_hint,
    ),
    lambda r: (
        f"Nothing says 'quality' like a {r.choice(['hole','rip','loose seam'])} in a "
        f"{r.choice(['brand new shirt','freshly bought dress','just-washed jumper'])}.",
        "product_quality",
    ),
    lambda r: (
        "Fantastic, the app crashed again at checkout. Such a 'seamless' online experience.",
        "online_app",
    ),
    lambda r: (
        "Love how my Sparks points vanished right when I wanted to use them. Really 'rewarding'.",
        "loyalty_sparks",
    ),
    lambda r: (
        "The 'beautiful' flowers I was gifted arrived completely wilted. Lovely.",
        "gifting",
    ),
    lambda r: (
        "Oh brilliant, the self-service till froze halfway through. 'Efficient' as always.",
        "checkout_payment",
    ),
]


# ---------------------------------------------------- Row + builders

_WEEKS = ['two weeks', 'three weeks', 'a month', 'six weeks']
SERIOUS_TEMPLATES += [
    lambda r: (f"I was charged {r.choice(['£25', '£40', '£60', '£120'])} for an order I never placed.", "checkout_payment"),
    lambda r: (f"The {r.choice(['chicken', 'salmon', 'sandwich', 'ready meal', 'pie'])} I bought {r.choice(TIME_MARKERS)} gave my whole family food poisoning.", "product_quality"),
    lambda r: (f"A colleague shouted at me in front of other customers {r.choice(TIME_MARKERS)} and refused to give me their name.", "staff_service"),
    lambda r: (f"I was told I could not come in with my {r.choice(['wheelchair', 'mobility scooter', 'pushchair'])} because the {r.choice(['ramp', 'lift', 'entrance'])} was blocked.", "accessibility"),
    lambda r: (f"My {r.choice(['mum', 'dad', 'son', 'daughter'])} fell on the {r.choice(['stairs', 'escalator', 'wet floor'])} and had to go to hospital.", "store_environment"),
    lambda r: (f"My card was charged {r.choice(['three', 'four', 'five'])} times for one order and I have heard nothing back in {r.choice(_WEEKS)}.", "checkout_payment"),
    lambda r: (f"The {r.choice(['milk', 'yogurt', 'chicken', 'ham'])} was out of date and smelled so bad I was sick.", "product_quality"),
    lambda r: (f"I reported a {r.choice(['security breach', 'fraud attempt', 'data leak'])} on my online account and nobody has replied.", "online_app"),
    lambda r: (f"There was {r.choice(['a wasp', 'a hair', 'a bone', 'glass'])} in my {r.choice(['cake', 'salad', 'sandwich', 'dessert'])} {r.choice(TIME_MARKERS)} and the manager just shrugged.", "product_quality"),
    lambda r: (f"I have been refused a refund on a faulty {r.choice(['coat', 'kettle', 'mattress', 'lamp'])} for {r.choice(_WEEKS)} even though I have the receipt.", "returns_refund"),
    lambda r: (f"Staff were {r.choice(['racist', 'sexist', 'abusive'])} towards me {r.choice(TIME_MARKERS)}.", "staff_service"),
    lambda r: (f"My Sparks account was {r.choice(['hacked', 'emptied', 'locked'])} and the money back in my wallet has gone.", "loyalty_sparks"),
    lambda r: (f"The courier left my parcel {r.choice(['outside in the rain', 'with a stranger', 'in a bin'])} and it had {r.choice(['medication', 'a birthday present', 'a laptop'])} inside.", "delivery_online"),
    lambda r: (f"I cut my {r.choice(['hand', 'finger', 'foot'])} on a broken {r.choice(['shelf', 'trolley', 'display'])} {r.choice(TIME_MARKERS)} and needed stitches.", "store_environment"),
    lambda r: (f"I am allergic to {r.choice(['nuts', 'milk', 'sesame', 'eggs'])} and the {r.choice(['label', 'packaging', 'staff'])} said it was safe, but I had a reaction.", "product_quality"),
]

OPENERS = ["Honestly,", "To be fair,", "Overall,", "In my opinion,", "Just to say,", "Quick note:",
           "Update:", "Visited today.", "Just back from M&S.", "Popped in on my lunch break."]
TAILS = ["Thanks.", "Just my opinion.", "Hope this helps.", "Will see next time.", "That's all.",
         "Thanks for listening."]

@dataclass
class Row:
    text: str
    stars: int
    category: str
    aspects: list[str] = field(default_factory=list)
    aspect_sentiments: list[str] = field(default_factory=list)
    aspect_clauses: list[str] = field(default_factory=list)
    has_detail: bool = False

    def to_csv(self) -> dict:
        return {
            "text": self.text,
            "stars": self.stars,
            "category": self.category,
            "aspects": ";".join(self.aspects),
            "aspect_sentiments": ";".join(self.aspect_sentiments),
            "aspect_clauses": ";".join(c.replace(";", ",") for c in self.aspect_clauses),
            "has_detail": "1" if self.has_detail else "0",
        }


def _detail_wrap(rng: random.Random, body: str) -> tuple[str, bool]:
    if rng.random() < 0.5:
        marker = rng.choice(STORE_PREFIX + [f"{t.capitalize()}," for t in TIME_MARKERS])
        return f"{marker} {body}", True
    return body, False


def _clause(rng: random.Random, aspect: str, polarity: str) -> str:
    noun = rng.choice(NOUNS[aspect])
    if polarity in ("positive", "negative") and rng.random() < 0.2:
        pool = SHORT_POS if polarity == "positive" else SHORT_NEG
        return rng.choice(pool).format(n=noun)
    if polarity == "positive":
        pred = rng.choice(POSITIVE_PRED[aspect])
        intens = rng.choice(INTENSIFIERS_POS + [""])
    elif polarity == "negative":
        pred = rng.choice(NEGATIVE_PRED[aspect])
        intens = rng.choice(INTENSIFIERS_NEG + [""])
    else:
        pred = rng.choice(NEUTRAL_PRED[aspect])
        intens = ""
    sep = " " if intens else ""
    return f"{noun} {intens}{sep}{pred}".strip()


def _stars_for(category: str, rng: random.Random) -> int:
    pool = {
        "minor_compliment":   [3, 4, 4, 4, 5],
        "major_compliment":   [4, 5, 5, 5, 5],
        "minor_complaint":    [1, 2, 2, 3, 3],
        "serious_complaint":  [1, 1, 1, 2],
        "gibberish":          [1, 2, 3, 4, 5],
    }[category]
    # Real customers often rate and write inconsistently, so the model must not lean on stars alone.
    if category != "gibberish" and rng.random() < (0.10 if category == "serious_complaint" else 0.20):
        return rng.randint(1, 5)
    return rng.choice(pool)


# ----- builders -------------------------------------------------------------

def gen_minor_compliment(rng: random.Random) -> Row:
    r = rng.random()
    stars = _stars_for("minor_compliment", rng)
    if r < 0.35:
        aspect = rng.choice(ASPECTS)
        clause = _clause(rng, aspect, "positive")
        body = clause.capitalize() + "."
        text, has_detail = _detail_wrap(rng, body)
        return Row(text=text, stars=stars, category="minor_compliment",
                   aspects=[aspect], aspect_sentiments=["positive"],
                   aspect_clauses=[clause], has_detail=has_detail)
    if r < 0.6:
        body = rng.choice(COMPLIMENT_PHRASES)
        text, has_detail = _detail_wrap(rng, body)
        return Row(text=text, stars=stars, category="minor_compliment", has_detail=has_detail)
    if r < 0.8:
        pieces = rng.sample(NEUTRAL_PHRASES, k=rng.randint(1, 2))
        body = " ".join(pieces)
        return Row(text=body, stars=max(3, stars - rng.randint(0, 1)),
                   category="minor_compliment", has_detail=False)
    a = rng.choice(COMPLIMENT_PHRASES)
    b = rng.choice(COMPLIMENT_PHRASES)
    while b == a:
        b = rng.choice(COMPLIMENT_PHRASES)
    body = f"{a} {b}"
    text, has_detail = _detail_wrap(rng, body)
    return Row(text=text, stars=stars, category="minor_compliment", has_detail=has_detail)


def gen_major_compliment(rng: random.Random) -> Row:
    stars = _stars_for("major_compliment", rng)
    a1, a2 = rng.sample(ASPECTS, 2)
    c1 = _clause(rng, a1, "positive")
    c2 = _clause(rng, a2, "positive")
    suffix = rng.choice(STRONG_COMPLIMENT_SUFFIX)
    body = f"{c1.capitalize()} and {c2} - {suffix}"
    text, has_detail = _detail_wrap(rng, body)
    return Row(text=text, stars=stars, category="major_compliment",
               aspects=[a1, a2], aspect_sentiments=["positive", "positive"],
               aspect_clauses=[c1, c2], has_detail=has_detail)


def gen_minor_complaint(rng: random.Random) -> Row:
    stars = _stars_for("minor_complaint", rng)
    r = rng.random()
    if r < 0.6:
        aspect = rng.choice(ASPECTS)
        clause = _clause(rng, aspect, "negative")
        body = clause.capitalize() + "."
        text, has_detail = _detail_wrap(rng, body)
        return Row(text=text, stars=stars, category="minor_complaint",
                   aspects=[aspect], aspect_sentiments=["negative"],
                   aspect_clauses=[clause], has_detail=has_detail)
    if r < 0.8:
        body = rng.choice(COMPLAINT_PHRASES)
        text, has_detail = _detail_wrap(rng, body)
        return Row(text=text, stars=stars, category="minor_complaint", has_detail=has_detail)
    tmpl = rng.choice(SARCASM_TEMPLATES)
    body, hint = tmpl(rng)
    aspect = hint(body) if callable(hint) else hint
    return Row(text=body, stars=stars, category="minor_complaint",
               aspects=[aspect], aspect_sentiments=["negative"],
               aspect_clauses=[body], has_detail=True)


def gen_serious_complaint(rng: random.Random) -> Row:
    stars = _stars_for("serious_complaint", rng)
    tmpl = rng.choice(SERIOUS_TEMPLATES)
    body, aspect = tmpl(rng)
    return Row(text=body, stars=stars, category="serious_complaint",
               aspects=[aspect], aspect_sentiments=["negative"],
               aspect_clauses=[body], has_detail=True)


def gen_gibberish(rng: random.Random) -> Row:
    stars = _stars_for("gibberish", rng)
    choice = rng.random()
    if choice < 0.5:
        text = "".join(rng.choice("abcdefghijklmnopqrstuvwxyz ") for _ in range(rng.randint(4, 24))).strip()
    elif choice < 0.75:
        text = "".join(rng.choice("0123456789!?.,#@ ") for _ in range(rng.randint(3, 16))).strip()
    elif choice < 0.9:
        text = rng.choice([
            "asdf asdf", "qwerty", "test test", "lorem ipsum",
            "hello hello hello", "123 456", "...", "?!?!", "ok", "fine", "no",
        ])
    else:
        text = rng.choice(["."]) * rng.randint(2, 10)
    return Row(text=text, stars=stars, category="gibberish", has_detail=False)


def gen_mixed_compliment(rng: random.Random) -> Row:
    """Two aspects, mixed polarity, dominant positive -> minor_compliment."""
    stars = _stars_for("minor_compliment", rng)
    a_pos, a_neg = rng.sample(ASPECTS, 2)
    pos = _clause(rng, a_pos, "positive")
    neg = _clause(rng, a_neg, "negative")
    conn = rng.choice([", but ", ". But ", ", although ", ", though "])
    body = f"{pos.capitalize()}{conn}{neg}."
    text, has_detail = _detail_wrap(rng, body)
    return Row(text=text, stars=stars, category="minor_compliment",
               aspects=[a_pos, a_neg], aspect_sentiments=["positive", "negative"],
               aspect_clauses=[pos, neg], has_detail=has_detail)


def gen_mixed_complaint(rng: random.Random) -> Row:
    """Two aspects, mixed polarity, dominant negative -> minor_complaint."""
    stars = _stars_for("minor_complaint", rng)
    a_pos, a_neg = rng.sample(ASPECTS, 2)
    pos = _clause(rng, a_pos, "positive")
    neg = _clause(rng, a_neg, "negative")
    conn = rng.choice([", but ", ". But ", ", however "])
    body = f"{neg.capitalize()}{conn}{pos}."
    text, has_detail = _detail_wrap(rng, body)
    return Row(text=text, stars=stars, category="minor_complaint",
               aspects=[a_pos, a_neg], aspect_sentiments=["positive", "negative"],
               aspect_clauses=[pos, neg], has_detail=has_detail)


def gen_neutral_aspect(rng: random.Random) -> Row:
    """One aspect mentioned neutrally -> labelled minor_compliment (not a complaint)."""
    aspect = rng.choice(ASPECTS)
    clause = _clause(rng, aspect, "neutral")
    body = clause.capitalize() + "."
    text, has_detail = _detail_wrap(rng, body)
    return Row(text=text, stars=rng.choice([3, 3, 4]), category="minor_compliment",
               aspects=[aspect], aspect_sentiments=["neutral"],
               aspect_clauses=[clause], has_detail=has_detail)


CATEGORY_BUILDERS: dict[str, list[tuple[Callable[[random.Random], Row], float]]] = {
    "minor_compliment":  [(gen_minor_compliment, 0.6), (gen_mixed_compliment, 0.25), (gen_neutral_aspect, 0.15)],
    "major_compliment":  [(gen_major_compliment, 1.0)],
    "minor_complaint":   [(gen_minor_complaint, 0.7), (gen_mixed_complaint, 0.3)],
    "serious_complaint": [(gen_serious_complaint, 1.0)],
    "gibberish":         [(gen_gibberish, 1.0)],
}


TYPOS = {"brilliant": "briliant", "definitely": "definately", "size": "siz",
         "queue": "que", "delicious": "delicous", "friendly": "freindly"}


def inject_human_noise(text: str, rng: random.Random, shout: bool = False) -> str:
    """Typos, dropped punctuation and the odd SHOUTING, like real customer text."""
    if rng.random() < 0.3:
        text = text.replace(".", "").replace(",", "")
    for correct, wrong in TYPOS.items():
        if rng.random() < 0.1:
            text = text.replace(correct, wrong)
    if shout and rng.random() < 0.15:
        text = text.upper()
    return text


def _add_noise(row: Row, rng: random.Random) -> Row:
    if row.category != "gibberish":
        if rng.random() < 0.3:
            row.text = f"{rng.choice(OPENERS)} {row.text}"
        if rng.random() < 0.2:
            row.text = f"{row.text} {rng.choice(TAILS)}"
    if row.category == "gibberish" or rng.random() > 0.35:
        return row
    shout = "negative" in row.aspect_sentiments
    row.text = inject_human_noise(row.text, rng, shout=shout)
    row.aspect_clauses = [inject_human_noise(c, rng) for c in row.aspect_clauses]
    return row


SHORTFALL: dict[str, int] = {}


def generate(per_class: int, seed: int = 42) -> list[Row]:
    """Unique rows only. Any category that runs out of fresh combinations is reported in SHORTFALL."""
    rng = random.Random(seed)
    out: list[Row] = []
    seen: set[str] = set()
    SHORTFALL.clear()
    for category, builders in CATEGORY_BUILDERS.items():
        target = per_class if category != "gibberish" else max(per_class // 2, 500)
        have, attempts = 0, 0
        while have < target and attempts < target * 15:
            attempts += 1
            builder = rng.choices([b for b, _ in builders], weights=[w for _, w in builders], k=1)[0]
            row = _add_noise(builder(rng), rng)
            text = row.text.strip()
            if len(text) < 2 or text in seen:
                continue
            seen.add(text)
            out.append(row)
            have += 1
        SHORTFALL[category] = target - have
    rng.shuffle(out)
    return out


def write_csv(rows: list[Row], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["text", "stars", "category", "aspects",
                        "aspect_sentiments", "aspect_clauses", "has_detail"],
        )
        writer.writeheader()
        for r in rows:
            writer.writerow(r.to_csv())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--per-class", type=int, default=12000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=Path, default=Path("data/retail_feedback.csv"))
    args = parser.parse_args()
    rows = generate(args.per_class, seed=args.seed)
    write_csv(rows, args.out)
    counts: dict[str, int] = {}
    stars_hist: dict[int, int] = {}
    for r in rows:
        counts[r.category] = counts.get(r.category, 0) + 1
        stars_hist[r.stars] = stars_hist.get(r.stars, 0) + 1
    print(f"Wrote {len(rows)} unique rows to {args.out}")
    short = {k: v for k, v in SHORTFALL.items() if v}
    if short:
        print(f"  (ran out of fresh combinations: {short})")
    for k, v in sorted(counts.items()):
        print(f"  {k:<20} {v:>6} ({v/len(rows):.1%})")
    print("Stars distribution:")
    for s in sorted(stars_hist):
        print(f"  {s}  {stars_hist[s]:>6}")


if __name__ == "__main__":
    main()
