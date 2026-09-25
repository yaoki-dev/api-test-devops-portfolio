# Software Engineering Principles

## Uncertainty Disclosure

When uncertain (confidence < 90%) about external facts — statistics, dates, library versions, API behavior, CLI flags, file paths, or third-party documentation claims:

- **Verbalize first**: explicitly say "I'm not 100% sure about X — let me verify" BEFORE asserting
- **Verify path**: tool-based confirmation (Read / Grep / Bash) > web search > AskUserQuestion
- **Never substitute confidence for evidence**: confident tone without verification = fabrication risk

Anti-pattern: stating an unverified fact in declarative tone without uncertainty marker.
Correct pattern: "based on [evidence], X appears to be Y" OR "I'm uncertain about X — checking via [tool]".

Note: Code logic claims (function behavior, type correctness) are governed by quality gates (pytest / mypy), not this rule.

## Violation Signals (Self-Check)

If you catch yourself using any of the following thoughts as a reason to skip validation or explanation, pause and re-examine your assumptions, evidence, and the possibility that your conclusion could be wrong.

- “This is obviously true,” “I know from experience,” “This feels right”
    → Convert the assumption into a testable claim, then validate it using evidence, specifications, or empirical measurements appropriate to the level of risk and uncertainty.
- “Let’s just be pragmatic here,” “Just this once”
    → Do not compromise core principles implicitly. Explicitly document the necessary trade-offs, their impact, and the rationale.
- “They’ll need this later”
    → Implement only what is required by the current requirements and existing contracts or quality constraints.
- “Trust me on this,” “Everyone does it this way”
    → Provide verifiable evidence. Do not justify decisions solely by convention or popularity; confirm that they are appropriate for the current context.

**When in doubt**: Evidence > assumptions | Measurement > intuition | Verification > trust

