from pathlib import Path
import re

import joblib
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS


BASE_DIR = Path(__file__).resolve().parent
GENERIC_WORDS = frozenset({
    "hi", "hello", "hey", "greetings", "morning", "afternoon", "evening",
    "thank", "thanks", "thankyou", "please", "good", "nice", "okay", "ok",
    "fine", "great", "excellent", "awesome", "perfect", "amazing", "fantastic",
    "wonderful", "bad", "poor", "terrible", "awful", "love", "like", "hate",
    "really", "store", "shop", "shopping", "product", "products", "service",
    "experience", "feedback", "quality", "happy", "unhappy", "satisfied",
})
PRODUCT_WORDS = frozenset({
    "cake", "cakes", "cookie", "cookies", "bread", "milk", "sandwich", "sandwiches",
    "bakery", "fruit", "vegetables", "produce", "meal", "meals", "item", "items",
    "product", "products", "groceries", "eggs", "cheese", "pastries", "pastry",
})
AVAILABILITY_PATTERN = re.compile(
    r"\b(?:sold\s*out|out\s+of\s+stock|no\s+stock|not\s+in\s+stock|"
    r"never\s+in\s+stock|unavailable|restock(?:ed|ing)?|replenish(?:ed|ing)?)\b"
)
NEGATED_AVAILABILITY_PATTERN = re.compile(
    r"\b(?:not|never|no\s+longer|isnt|aren't|isn't|arent)\s+(?:\w+\s+){0,2}$"
    r"|\b(?:do\s+not|don't|dont|no\s+need\s+to)\s+(?:\w+\s+){0,2}$"
)
STOCK_CONTEXT_PATTERN = re.compile(
    r"\b(?:always|often|frequently|repeatedly|daily|whenever|lunchtime|evening|"
    r"morning|afternoon|today|yesterday)\b|"
    r"\bevery\s+(?:time|visit|day|week)\b|"
    r"\b(?:by|at|after|before|around)\s+(?:\d{1,2}(?::\d{2})?\s*(?:am|pm)?|"
    r"lunch|dinner|opening|closing)\b|"
    r"\b(?:had\s+to|have\s+to)\s+(?:visit|go|buy|leave|return)\b|"
    r"\b(?:could\s+not|couldn't|couldnt)\s+(?:buy|get|find)\b"
)
RESTOCK_REQUEST_PATTERN = re.compile(r"\b(?:restock|replenish|stocked|replenished)\b")


class FeedbackPredictor:
    def __init__(self, model_dir: Path = BASE_DIR):
        paths = [model_dir / "sentiment_model.pkl", model_dir / "genuine_model.pkl"]
        if not all(path.is_file() for path in paths):
            raise FileNotFoundError("Run train_sentiment.py and train_genuine.py before predicting.")
        self.sentiment_model = joblib.load(paths[0])
        self.genuine_model = joblib.load(paths[1])

    @staticmethod
    def classify(model, feedback: str) -> tuple[str, float]:
        probabilities = model.predict_proba([feedback])[0]
        index = int(probabilities.argmax())
        return str(model.classes_[index]), float(probabilities[index])

    def has_feedback_details(self, feedback: str) -> bool:
        vectorizer = self.genuine_model.named_steps["tfidf"]
        tokens = set(vectorizer.build_tokenizer()(vectorizer.build_preprocessor()(feedback)))
        informative = {token for token in tokens if token.isalpha()} - ENGLISH_STOP_WORDS - GENERIC_WORDS
        recognised = informative.intersection(vectorizer.vocabulary_)
        return len(recognised) >= 2 or (len(recognised) >= 1 and len(informative) >= 4)

    @staticmethod
    def stock_feedback_context(feedback: str) -> tuple[bool, bool]:
        clauses = re.split(r"[.!?;\n]", feedback.lower().replace("\u2019", "'"))
        mentions_stock = False
        for index, clause in enumerate(clauses):
            tokens = set(re.findall(r"[a-z]+", clause))
            if not tokens.intersection(PRODUCT_WORDS):
                continue
            for match in AVAILABILITY_PATTERN.finditer(clause):
                if not NEGATED_AVAILABILITY_PATTERN.search(clause[:match.start()]):
                    mentions_stock = True
                    if STOCK_CONTEXT_PATTERN.search(clause):
                        return True, True
                    following = clauses[index + 1] if index + 1 < len(clauses) else ""
                    if RESTOCK_REQUEST_PATTERN.search(following) and STOCK_CONTEXT_PATTERN.search(following):
                        return True, True
        return mentions_stock, False

    @staticmethod
    def describes_stock_feedback(feedback: str) -> bool:
        return FeedbackPredictor.stock_feedback_context(feedback)[0]

    def predict(self, feedback: str) -> dict:
        sentiment, sentiment_confidence = self.classify(self.sentiment_model, feedback)
        genuine, genuine_confidence = self.classify(self.genuine_model, feedback)
        has_details = self.has_feedback_details(feedback)
        stock_feedback, stock_has_context = self.stock_feedback_context(feedback)
        if stock_has_context:
            genuine = "Yes"
            yes_index = list(self.genuine_model.classes_).index("Yes")
            genuine_confidence = float(self.genuine_model.predict_proba([feedback])[0][yes_index])
        elif stock_feedback or not has_details:
            genuine = "No"
            no_index = list(self.genuine_model.classes_).index("No")
            genuine_confidence = float(self.genuine_model.predict_proba([feedback])[0][no_index])
        eligible = genuine == "Yes"
        reason = (
            "Predicted to be genuine, specific and useful feedback; eligible regardless of sentiment."
            if eligible else
            "Predicted to be generic or insufficiently specific feedback; sentiment alone does not qualify for a reward."
        )
        if stock_has_context:
            reason = (
            "Product availability feedback includes timing, frequency, impact, or a contextual restocking suggestion. Eligible regardless of sentiment, "
                "sentence length, or accompanying generic praise. The stock-feedback rule takes precedence "
                "over the model; genuine confidence shows the model's probability for Yes."
            )
        elif stock_feedback:
            reason = (
                "A product availability statement alone is too generic for a reward. Add when or how often "
                "it happens, its impact, or a specific restocking improvement. Praise, repetition, and extra "
                "filler do not add useful detail. The stock-feedback rule takes precedence over the model; "
                "genuine confidence shows the model's probability for No."
            )
        elif not has_details:
            reason = (
                "Not enough specific feedback details supported by this model. Greetings or thanks alone, "
                "generic comments, and repeated words do not qualify; greetings alongside detailed feedback "
                "are allowed. The minimum-detail rule takes precedence "
                "over the model; genuine confidence shows the model's probability for No."
            )
        return {
            "sentiment": sentiment,
            "sentimentConfidence": sentiment_confidence,
            "genuineFeedback": genuine,
            "genuineConfidence": genuine_confidence,
            "rewardEligible": eligible,
            "reason": reason,
        }