-- ClickHouse initialization script for Langfuse
-- This script creates the database and user for Langfuse in single-node mode

-- Create database if it doesn't exist
CREATE DATABASE IF NOT EXISTS langfuse;

-- Switch to langfuse database
USE langfuse;

-- Create the schema_migrations table that Langfuse expects (single-node version)
-- Using MergeTree instead of ReplicatedMergeTree to avoid Zookeeper requirement
CREATE TABLE IF NOT EXISTS schema_migrations (
    version    Int64,
    dirty      UInt8,
    sequence   UInt64
) Engine=MergeTree()
ORDER BY sequence;

-- Create user for Langfuse if it doesn't exist
-- This is handled by environment variables, but we ensure the database exists