# Websocket for virtual entity registration

> **Status:** Active
> **Date:** 2026-06

## Context

Virtual entities need to be registered with HA at runtime during test execution. The alternative approaches include:

- Modifying HA config files and restarting
- Using HA's REST API (limited entity registration support)
- Direct database manipulation

## Decision

Use HA's websocket API with a custom component to register virtual entities dynamically.
The custom component exposes additional websocket commands that the test harness invokes to create and manage virtual entities.

## Consequences

- Entities can be created and destroyed per-test without restarting HA
- No file I/O or restart overhead during tests
- Requires shipping a custom component with the harness
- Consumers don't need to understand the websocket mechanism
