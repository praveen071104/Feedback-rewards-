from pathlib import Path
import hashlib
import re

import joblib
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from triage import triage_feedback


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
RETAIL_SENTIMENT = re.compile(
    r"\b(?:sold\s*out|out of stock|no stock|not available|not arrived|did not arrive|"
    r"hasn't arrived|never arrived|charged twice|double charged|too dim|eye strain|"
    r"too small to read|not clear|would not close|could not enter|couldn't enter|"
    r"no response|no reply|no refund|wash well|stayed soft|kept their shape|"
    r"resolved my issue|resolved the issue|fasten securely)\b"
)
POSITIVE_RETAIL = {"wash well", "stayed soft", "kept their shape", "resolved my issue", "resolved the issue", "fasten securely"}


class FeedbackPredictor:
    def __init__(self, model_dir: Path = BASE_DIR):
        sentiment_path = model_dir / "sentiment_model.pkl"
        genuine_path = model_dir / "genuine_model.pkl"
        if not sentiment_path.is_file():
            raise FileNotFoundError("Run train_sentiment.py before predicting.")
        if not genuine_path.is_file():
            raise FileNotFoundError("Run train_genuine.py before predicting.")
        self.sentiment_model = joblib.load(sentiment_path)
        self.genuine_model = joblib.load(genuine_path)
        self.metadata = {}
        for name, path in (("sentiment", sentiment_path), ("genuine", genuine_path)):
            with path.open("rb") as artifact:
                self.metadata[name] = "local-v1-" + hashlib.file_digest(artifact, "sha256").hexdigest()[:12]
        self.sentiment_analyzer = SentimentIntensityAnalyzer()
        self.sentiment_analyzer.lexicon.update({
            "faulty": -2.2, "overcharged": -2.5, "unhelpful": -2.0,
            "stale": -1.8, "unavailable": -1.8, "inaccessible": -2.3,
        })
        if not hasattr(self.genuine_model, "named_steps"):
            raise ValueError("Run train_genuine.py to create a local scikit-learn model.")

    @staticmethod
    def classify(model, feedback: str) -> tuple[str, float]:
        probabilities = model.predict_proba([feedback])[0]
        index = max(range(len(probabilities)), key=probabilities.__getitem__)
        return str(model.classes_[index]), float(probabilities[index])

    def has_feedback_details(self, feedback: str) -> bool:
        if "features" in self.genuine_model.named_steps:
            vectorizer = dict(self.genuine_model.named_steps["features"].transformer_list)["words"]
        else:
            vectorizer = self.genuine_model.named_steps["tfidf"]
        tokens = set(vectorizer.build_tokenizer()(vectorizer.build_preprocessor()(feedback)))
        informative = {token for token in tokens if token.isalpha()} - ENGLISH_STOP_WORDS - GENERIC_WORDS
        recognised = informative.intersection(vectorizer.vocabulary_)
        return len(recognised) >= 2 or (len(recognised) >= 1 and len(informative) >= 4)

    def classify_sentiment(self, feedback: str) -> tuple[str, float]:
        text = feedback.lower().replace("\u2019", "'")
        text = re.sub(r"\b(?:thank you|thanks|thankfully|hello|hi|please)\b[!,]?", "", text)
        text = RETAIL_SENTIMENT.sub(
            lambda match: "excellent" if match.group() in POSITIVE_RETAIL else "disappointing", text,
        )
        clauses = re.split(r"[.!?;\n]|\b(?:but|however|although|and)\b", text)
        scores = [self.sentiment_analyzer.polarity_scores(clause)["compound"] for clause in clauses if clause.strip()]
        positive = any(score >= 0.05 for score in scores)
        negative = any(score <= -0.05 for score in scores)
        sentiment = "Neutral" if positive == negative else "Positive" if positive else "Negative"
        probabilities = self.sentiment_model.predict_proba([feedback])[0]
        return sentiment, float(probabilities[list(self.sentiment_model.classes_).index(sentiment)])

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

    def predict(self, feedback: str, loyal_customer: bool = False) -> dict:
        sentiment, sentiment_confidence = self.classify_sentiment(feedback)
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
        return {
            "sentiment": sentiment,
            "sentimentConfidence": sentiment_confidence,
            "genuineFeedback": genuine,
            "genuineConfidence": genuine_confidence,
            **triage_feedback(feedback, has_details, genuine == "Yes", loyal_customer),
        }