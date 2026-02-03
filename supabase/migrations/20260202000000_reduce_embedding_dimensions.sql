-- Reduce vector columns from 1536 to 512 dimensions
-- Existing embeddings must be re-generated at new dimensions

-- Drop existing indexes (they reference the old dimension)
DROP INDEX IF EXISTS interactions_embedding_idx;
DROP INDEX IF EXISTS profiles_embedding_idx;

-- Alter columns to 512 dimensions
ALTER TABLE interactions ALTER COLUMN embedding TYPE vector(512);
ALTER TABLE profiles ALTER COLUMN embedding TYPE vector(512);
ALTER TABLE feedbacks ALTER COLUMN embedding TYPE vector(512);
ALTER TABLE raw_feedbacks ALTER COLUMN embedding TYPE vector(512);
ALTER TABLE agent_success_evaluation_result ALTER COLUMN embedding TYPE vector(512);

-- Null out existing embeddings (they need re-generation at new dimensions)
UPDATE interactions SET embedding = NULL;
UPDATE profiles SET embedding = NULL;
UPDATE feedbacks SET embedding = NULL;
UPDATE raw_feedbacks SET embedding = NULL;
UPDATE agent_success_evaluation_result SET embedding = NULL;

-- Recreate indexes with new dimensions
CREATE INDEX interactions_embedding_idx ON interactions
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = '100');
CREATE INDEX profiles_embedding_idx ON profiles
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = '100');
