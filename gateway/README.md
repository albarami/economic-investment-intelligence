# gateway/ — offline typed-decision gateway `eii_gateway`

This folder will hold `eii_gateway`, an offline package used only by build and evaluation tooling.

## Rules

- It is imported only by tooling under `evals/` and `scripts/`. Nothing under `core/`, `custodian/` or `product/` imports it or reads its settings (BE-102).
- The default provider is `none`. Version 1 makes no run-time gateway call.
- A gateway answer is decision evidence only: never a fact, a number, a privacy decision or a gate.

Status: scaffolding only (task S0-T01). This folder holds no code yet.

Read: [0014-typed-decision-gateway.md](../docs/decisions/0014-typed-decision-gateway.md)
