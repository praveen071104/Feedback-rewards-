// Feedback Rewards POC — Mongo setup. Run with:
//   mongosh "mongodb://127.0.0.1:27017" feedback-reward-poc/backend/db/mongo_init.js

const dbName = "ms_feedback_platform";
const target = db.getSiblingDB(dbName);

for (const name of ["feedback", "analysis"]) {
    if (!target.getCollectionNames().includes(name)) {
        target.createCollection(name);
    }
}

target.feedback.createIndex({ submission_id: 1 }, { unique: true });
target.feedback.createIndex({ created_at: -1 });
target.feedback.createIndex({ store_id: 1, created_at: -1 });

target.analysis.createIndex({ submission_id: 1 }, { unique: true });
target.analysis.createIndex({ category: 1, created_at: -1 });

print(`OK: ${dbName} ready. Collections: ${target.getCollectionNames().join(", ")}`);
