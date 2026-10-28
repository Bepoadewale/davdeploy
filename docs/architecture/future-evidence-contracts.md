# Future evidence contracts

DavDeploy tests the shape and safety of future provider evidence without activating a customer
integration. These contracts are deliberately useful before a provider capability is enabled:

- pricing evidence has a source, timestamp/cache boundary, execution state and limitations; a
  fixture or unavailable adapter must not be presented as a customer bill;
- observed outputs retain a source and status, redact sensitive values before customer readback,
  and attach resources to one tenant environment; and
- GitHub webhook fixtures require event, delivery ID, bounded payload and signature validation,
  record duplicate delivery IDs safely, and do not prove that a public callback is configured.

The tests use in-memory databases and fixture adapters only. They do not assume a customer role,
contact a pricing API, create a public webhook, or change cloud resources. A provider remains
unavailable until it passes the enablement gate in [the provider model](provider-model.md).
