# Flagship evolution plan

> **Historical strategy note.** Superseded on 2026-10-08. This repository now contains the first davdeploy implementation. Preserved for history.

## Decision

After the ten public reference implementations are complete, evolve
`multi-tenant-ai-inference-platform` into the public flagship. Its public technical
identity can broaden from a gateway into a **governed multi-tenant AI platform**.

The remaining repositories remain public, independent laboratories and interview
evidence. They do not compete with the flagship or get copied wholesale into a new
monolith.

## Why this repository

It already has the strongest central request path:

```text
tenant identity -> quota/admission -> bounded queue -> model routing
-> real inference -> privacy-safe usage -> telemetry
```

That is the natural entry point for a broader platform spanning model lifecycle,
capacity, policy, reliability, agent governance and, later, edge operations.

## Engineering approach

Build vertical slices around stable APIs and events, preserving the executed local
inference platform at every stage.

1. **Release control** — connect approved model artifacts, offline evaluation,
   canary routing, promotion and rollback.
2. **Governed operations** — add durable plans, policy and approvals for protected
   operational actions.
3. **Capacity and economics** — expose scheduling/admission signals, SLO evidence and
   cost allocation without claiming real GPU measurements where no GPU exists.
4. **Secure agent participation** — let agents use narrowly delegated platform tools,
   not cloud or Kubernetes administrator credentials.
5. **Optional edge extension** — connect fleet-approved artifacts and local/cloud
   routing through a defined adapter, not a mandatory dependency.

Each slice must remain reproducible on a fresh GitHub Actions runner and
independently demonstrable before another is added. The PR's CI result is the
integration proof; a separate local Compose clean-room run is not required.

## Flagship demonstration

```text
tenant requests an approved model endpoint
  -> signed identity, quota and policy
  -> release plan selects a verified candidate
  -> local serving deployment receives canary traffic
  -> traces, metrics, SLO and cost evidence are evaluated
  -> independent approval promotes the candidate or rollback restores champion
```

The deliberate failure demonstration is equally important:

```text
candidate is service-healthy but violates quality or latency gate
  -> rollout stops
  -> prior champion remains active
  -> audit and evidence explain the decision
```

## Boundaries

The public flagship documents technical architecture and executed evidence only.
Commercial positioning, buyer strategy, packaging, pricing and acquisition options
remain in internal planning records. Do not copy those discussions into public READMEs,
issues, source comments or commit messages.
