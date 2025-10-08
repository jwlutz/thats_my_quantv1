# V1 Backtester Project Rules

## Project Context
Building a GENERALIZED quantitative backtesting framework in Python. This is V1 - a rewrite from V0 that adds:
- Transaction-based position management (RoundTrip model)
- Support for DCA and partial exits
- Fractional shares support
- OHLCV data for better entry/exit rules
- CompositeExitRule for agent-driven strategy discovery

Full spec is in SPEC.md. Timeline: 11 weeks, building incrementally.

## Architecture Principles
1. Build piece by piece - one component at a time
2. Test everything before moving on
3. Follow the spec exactly - don't deviate
4. Prioritize correctness over cleverness
5. No premature optimization

## Code Style
- Use dataclasses where appropriate (Transaction, Signal)
- Type hints on all method signatures
- Docstrings for public methods
- Descriptive variable names
- Keep methods under 30 lines when possible

## Testing
- Write pytest tests for every component
- Test edge cases (zero shares, missing data, etc.)
- Use descriptive test names: test_roundtrip_dca_multiple_entries
- Assert on exact values, not just "truthy"

## What NOT to Do
- Don't generate entire classes - I write the structure, you review
- Don't suggest "improvements" that deviate from spec
- Don't add features not in the spec
- Don't use complex patterns when simple code works
- Don't assume I want the "clever" solution

## What TO Do
- Spot bugs in my logic
- Suggest better variable names
- Point out edge cases I missed
- Help write comprehensive tests
- Validate that my code matches the spec
- Explain why something won't work

## Current Phase
Week 1: Building Transaction + RoundTrip classes
Focus on: Immutability, cumulative cost tracking, P&L calculations

## Dependencies
- Python 3.11+
- pytest for testing
- pandas for data handling
- yfinance for market data
- pyyaml for config files
- Will add more as needed

## When I'm Stuck
Ask me:
1. What error are you seeing?
2. What did you expect to happen?
3. Can you show me the code?

Then help me debug, don't rewrite.

## Review Checklist
When reviewing my code, check:
- [ ] Matches spec exactly
- [ ] Handles edge cases (None, zero, negative)
- [ ] Type hints present
- [ ] Has docstring
- [ ] Tests exist and pass
- [ ] No obvious bugs

## Remember
I'm learning by building this. Help me understand WHY something is wrong, not just WHAT is wrong. The goal is for me to deeply understand this backtester, not just have working code.