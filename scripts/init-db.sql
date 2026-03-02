-- SignalOps — PostgreSQL initialization script
-- This runs once when the postgres container is first created.
-- Actual schema migrations are managed by Alembic in packages/traceability-store.
-- This script only ensures the database and user exist with proper permissions.

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Grant privileges (user and db already created by POSTGRES_* env vars)
GRANT ALL PRIVILEGES ON DATABASE signalops TO signalops;
