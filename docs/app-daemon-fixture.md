# AppDaemon Fixture

## `app_daemon` (session scope)

AppDaemon API client.

## API

Currently provides basic initialization. Future versions will add methods for interacting with AppDaemon apps.

```python
def test_appdaemon(app_daemon):
    # Access base URL
    print(app_daemon.base_url)
```
