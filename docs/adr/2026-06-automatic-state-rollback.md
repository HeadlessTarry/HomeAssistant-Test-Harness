# Automatic state rollback

> **Status:** Active
> **Date:** 2026-06

## Context

Tests manipulate entity state and config to set up scenarios and verify behavior. Without cleanup, state changes leak between tests, causing instability and order-dependent failures.

## Decision

Automatically rollback all state and config changes after each test. Virtual entities are destroyed; real and pre-registered entities have their state and config restored to pre-test values.

## Consequences

- Tests are isolated and can run in any order
- No need for manual cleanup in test code
- Slight overhead from tracking and restoring state
- Tests cannot rely on state persisting across tests
