# Docker for isolation

> **Status:** Active
> **Date:** 2026-06

## Context

Integration tests for Home Assistant configurations need a real HA instance to validate automations, templates, scripts, and entity interactions. The alternative is mocking HA's behavior.

## Decision

Run HA in Docker containers to provide a real but isolated test environment. The Docker instance is ephemeral — created for the test session and destroyed after.

## Consequences

- Tests run against real HA behavior, not mocks
- No risk of interfering with production HA instances
- Tests require Docker to be available
- Startup overhead from container creation
