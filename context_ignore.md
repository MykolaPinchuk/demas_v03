# Context Ignore Rules

# Purpose: Exclude large or generated content from agent context to avoid
#          exhausting the context window. Patterns follow .gitignore syntax.

## Build artifacts and caches
**/__pycache__/**
**/*.pyc
**/.pytest_cache/**
**/*.so

## VCS internals
**/.git/**

## Sandbox heavy directories (repos, logs, run outputs)
sandbox/project/**
sandbox/agent_batch_runs/**
sandbox/batch_runs/**
sandbox/runs/**

## Sandbox patch artifacts
sandbox/patch.*
sandbox/add_marker.diff

## Generic temporary or log files
*.tmp

## Other
human_notes.md

# Notes:
# - Keep small configuration and task files (e.g., sandbox/swe_tasks.jsonl,
#   sandbox/seed_tasks.jsonl) in context.
# - Keep core scripts and documentation in context.

