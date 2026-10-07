import unittest
from unittest.mock import Mock, patch

import pandas as pd

from app.llm.train_absa import train_sentiment


class SentimentSplitTests(unittest.TestCase):
    def test_sentiment_uses_parent_review_split(self):
        train = pd.DataFrame([
            {"text": "Training review", "stars": 3,
             "aspects_list": ["staff_service", "product_quality"],
             "sentiments_list": ["positive", "negative"],
             "clauses_list": ["Training staff praise", "Training damaged meal"]},
        ])
        test = pd.DataFrame([
            {"text": "Held out review", "stars": 3,
             "aspects_list": ["staff_service", "product_quality"],
             "sentiments_list": ["positive", "negative"],
             "clauses_list": ["Held out staff praise", "Held out damaged meal"]},
        ])
        vectorizer = Mock()
        classifier = Mock()
        classifier.predict.return_value = ["positive", "negative"]

        with patch("app.llm.train_absa.LogisticRegression", return_value=classifier):
            _, metrics = train_sentiment(train, test, vectorizer)

        training_texts = list(vectorizer.transform.call_args_list[0].args[0])
        testing_texts = list(vectorizer.transform.call_args_list[1].args[0])
        self.assertTrue(all("Training" in text for text in training_texts))
        self.assertTrue(all("Held out" in text for text in testing_texts))
        self.assertTrue(set(training_texts).isdisjoint(testing_texts))
        self.assertEqual(list(classifier.fit.call_args.args[1]), ["positive", "negative"])
        self.assertEqual(metrics["report"]["accuracy"], 1.0)


if __name__ == "__main__":
    unittest.main()