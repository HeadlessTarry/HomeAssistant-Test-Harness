# 🂡 Drop AppDaemon support

> **Status:** Active
> **Date:** 2026-10
> **Amends:** [2026-08-websocket-time-control](2026-08-websocket-time-control.md)

## 🂢 Context

The harness started an AppDaemon container alongside Home Assistant and exposed an `app_daemon` fixture, to support AppDaemon app development and testing
in downstream projects. That use case never materialised: the only known downstream project has no AppDaemon apps under test, and the fixture offered only
basic API access. Every session still paid for a second container, its startup wait, and an `appdaemon/apps/` directory that downstream projects had to provide.

## 🂢 Decision

Remove AppDaemon entirely: the container, the `app_daemon` fixture, the `AppDaemon` client, `AppDaemonClientError`, `DockerComposeManager.get_appdaemon_url()`
and the `APPDAEMON_CONFIG_ROOT` setting. The test environment runs Home Assistant only.

## 🂢 Consequences

- Faster, simpler startup: one container, one health check
- Downstream projects no longer need an `appdaemon/` directory
- Breaking change for any downstream project that used the removed API; it must stay on an earlier release
- [2026-08-websocket-time-control](2026-08-websocket-time-control.md) is amended: its AppDaemon time-control consequences no longer apply
