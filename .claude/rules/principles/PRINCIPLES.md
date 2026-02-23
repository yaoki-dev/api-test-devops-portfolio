# Software Engineering Principles

**Core Directive**: Evidence > assumptions | Code > documentation | Efficiency > verbosity

## Philosophy
- **Task-First Approach**: Understand → Plan → Execute → Validate
- **Evidence-Based Reasoning**: All claims verifiable through testing, metrics, or documentation
- **Parallel Thinking**: Maximize efficiency through intelligent batching and coordination
- **Context Awareness**: Maintain project understanding across sessions and operations

## Engineering Mindset

### SOLID
- **Single Responsibility**: Each component has one reason to change
- **Open/Closed**: Open for extension, closed for modification
- **Liskov Substitution**: Derived classes substitutable for base classes
- **Interface Segregation**: Don't depend on unused interfaces
- **Dependency Inversion**: Depend on abstractions, not concretions

### Core Patterns
- **DRY**: Abstract common functionality, eliminate duplication
- **KISS**: Prefer simplicity over complexity in design decisions
- **YAGNI**: Implement current requirements only, avoid speculation

### Systems Thinking
- **Ripple Effects**: Consider architecture-wide impact of decisions
- **Long-term Perspective**: Evaluate immediate vs. future trade-offs
- **Risk Calibration**: Balance acceptable risks with delivery constraints

## Decision Framework

### Data-Driven Choices
- **Measure First**: Base optimization on measurements, not assumptions
- **Hypothesis Testing**: Formulate and test systematically
- **Source Validation**: Verify information credibility
- **Bias Recognition**: Account for cognitive biases

### Trade-off Analysis
- **Temporal Impact**: Immediate vs. long-term consequences
- **Reversibility**: Classify as reversible, costly, or irreversible
- **Option Preservation**: Maintain future flexibility under uncertainty

### Risk Management
- **Proactive Identification**: Anticipate issues before manifestation
- **Impact Assessment**: Evaluate probability and severity
- **Mitigation Planning**: Develop risk reduction strategies

## Quality Philosophy

### Quality Quadrants
- **Functional**: Correctness, reliability, feature completeness
- **Structural**: Code organization, maintainability, technical debt
- **Performance**: Speed, scalability, resource efficiency
- **Security**: Vulnerability management, access control, data protection

### Quality Standards
- **Automated Enforcement**: Use tooling for consistent quality
- **Preventive Measures**: Catch issues early when cheaper to fix; if complexity metrics increase or tests become harder to maintain, ask: "Given current requirements, is there a simpler approach?" — YAGNI applies, do NOT expand scope.
- **Human-Centered Design**: Prioritize user welfare and autonomy

## Violation Signals (Self-Check)

These thoughts indicate potential principle violations - STOP and reconsider:

| Red Flag Thought | Violated Principle | Correct Response |
|------------------|-------------------|------------------|
| "This is obviously true" | Evidence-Based Reasoning | Find verifiable evidence first |
| "Being pragmatic here" | Core Patterns (KISS/DRY/YAGNI) | Check if compromising fundamentals |
| "Just this once" | All principles | Principles don't have exceptions |
| "They'll want this later" | YAGNI | Implement only current requirements |
| "I know from experience" | Measure First | Get actual measurements |
| "This feels right" | Hypothesis Testing | Formulate and test systematically |
| "Trust me on this" | Source Validation | Provide verifiable sources |
| "Everyone does it this way" | Bias Recognition | Question common assumptions |

**When in doubt**: Evidence > assumptions | Measurement > intuition | Verification > trust

