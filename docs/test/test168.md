# test168 — Bounded pricing-evidence cache

## Execution boundary

Local automated tests only. No AWS customer role, Cost Explorer request, cloud resource, or
customer record was changed.

## Commands executed

```text
.venv/bin/pytest tests/test_customer_cloud_lifecycle.py
make verify
```

## Result

Passed. The regression test proves two discovery evidence requests for the same customer account
and region call Cost Explorer once and label the second result as a cache hit.

## Known limitations

The cache is process-local and intentionally short-lived. It is not a billing system or a promise
that estimates match a future AWS invoice.
