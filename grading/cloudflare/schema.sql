-- Cloudflare D1: persistent shared annotation database
CREATE TABLE IF NOT EXISTS dialogues (
  id TEXT PRIMARY KEY,
  topic TEXT NOT NULL,
  transcript_json TEXT NOT NULL,
  condition TEXT NOT NULL CHECK (condition IN ('neutral','sycophantic')),
  policy_version TEXT NOT NULL,
  model TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ratings (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  dialogue_id TEXT NOT NULL REFERENCES dialogues(id),
  grader_id TEXT NOT NULL,
  grader_name TEXT NOT NULL,
  score INTEGER NOT NULL CHECK (score BETWEEN 1 AND 5),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(dialogue_id, grader_id)
);
CREATE INDEX IF NOT EXISTS idx_ratings_dialogue ON ratings(dialogue_id);
