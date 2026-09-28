from datetime import datetime, timezone
import os

from pymongo import MongoClient, ReturnDocument
from pymongo.errors import DuplicateKeyError


STORES = {
    "marble-arch": {"name": "M&S Marble Arch", "location": "London"},
    "stratford-city": {"name": "M&S Stratford City", "location": "London"},
    "bluewater": {"name": "M&S Bluewater", "location": "Greenhithe, Kent"},
    "unspecified": {"name": "Not specified", "location": ""},
}


class FeedbackStore:
    def __init__(self):
        self.client = MongoClient(
            os.environ.get("MONGODB_URI", "mongodb://127.0.0.1:27017/"),
            serverSelectionTimeoutMS=3000, connectTimeoutMS=3000, socketTimeoutMS=5000,
            tz_aware=True,
        )
        self.collection = self.client[os.environ.get("MONGODB_DATABASE", "feedback_reward_poc")]["feedback"]

    def ping(self):
        self.client.admin.command("ping")

    def close(self):
        self.client.close()

    @staticmethod
    def public(document):
        return {key: value for key, value in document.items() if key not in {"_id", "operations", "initialRequest"}}

    def get(self, feedback_id):
        document = self.collection.find_one({"_id": feedback_id})
        if document is None:
            raise KeyError(feedback_id)
        return self.public(document)

    def initial(self, submission_id, request):
        document = self.collection.find_one({"_id": submission_id})
        if document is None:
            return None
        if document["initialRequest"] != request:
            raise ValueError("This submission ID was already used for different feedback, store or loyalty details.")
        return self.public(document)

    def save(self, submission_id, request, result):
        now = int(datetime.now(timezone.utc).timestamp() * 1000)
        document = {
            **result, "ticket": result.get("ticket"),
            "_id": submission_id, "feedbackId": submission_id,
            "feedback": request["feedback"], "storeId": request["storeId"],
            "store": STORES[request["storeId"]], "loyalCustomer": request["loyalCustomer"],
            "createdAt": now, "updatedAt": now, "revision": 0,
            "initialRequest": request, "operations": [],
        }
        try:
            self.collection.insert_one(document)
        except DuplicateKeyError:
            return self.initial(submission_id, request)
        return self.public(document)

    def clarification(self, feedback_id, operation_id, request):
        document = self.collection.find_one({"_id": feedback_id})
        if document is None:
            raise KeyError(feedback_id)
        for operation in document["operations"]:
            if operation["id"] == operation_id:
                if operation["request"] != request:
                    raise ValueError("This clarification ID was already used for different details.")
                return operation["response"]
        if (document["feedback"] != request["originalFeedback"] or
                document["storeId"] != request["storeId"] or
                document["loyalCustomer"] != request["loyalCustomer"] or
                (document.get("ticket") or {}).get("id") != request["ticketId"]):
            raise ValueError("Feedback has changed. Reload the saved record before replying.")
        return None

    def update(self, feedback_id, operation_id, request, result):
        cached = self.clarification(feedback_id, operation_id, request)
        if cached is not None:
            return cached
        original = self.get(feedback_id)
        updated = {
            **original, **result, "ticket": result.get("ticket"),
            "feedback": request["originalFeedback"] + "\n\n" + request["feedback"],
            "updatedAt": int(datetime.now(timezone.utc).timestamp() * 1000),
            "revision": original["revision"] + 1,
        }
        saved = self.collection.find_one_and_update(
            {"_id": feedback_id, "revision": original["revision"], "feedback": request["originalFeedback"]},
            {"$set": updated, "$push": {"operations": {"id": operation_id, "request": request, "response": updated}}},
            return_document=ReturnDocument.AFTER,
        )
        if saved is None:
            cached = self.clarification(feedback_id, operation_id, request)
            if cached is not None:
                return cached
            raise ValueError("Feedback changed during reassessment. Reload before replying.")
        return self.public(saved)

    def list(self, before=None, limit=100):
        query = {}
        if before:
            anchor = self.get(before)
            query = {"$or": [
                {"createdAt": {"$lt": anchor["createdAt"]}},
                {"createdAt": anchor["createdAt"], "_id": {"$lt": before}},
            ]}
        documents = list(self.collection.find(query).sort([("createdAt", -1), ("_id", -1)]).limit(limit + 1))
        return {
            "items": [self.public(document) for document in documents[:limit]],
            "nextCursor": documents[limit - 1]["feedbackId"] if len(documents) > limit else None,
        }