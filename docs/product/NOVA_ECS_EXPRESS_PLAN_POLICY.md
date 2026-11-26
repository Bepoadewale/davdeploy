# Nova ECS Express actual-plan policy

## Objective

Add deterministic actual-plan checks for the bounded ECS Express pilot. The
checks must bind the service to its planned image, roles, log group, and
project-scoped network resources, and reject unknown or unsupported shapes.

This policy package must not enable customer dispatch. Regional cost coverage,
IAM authorization, runner integration, and an authorized customer lifecycle
remain separate gates.
