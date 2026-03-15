# Contributing to Heap Seance

Contributions welcome! Open an issue or submit a PR.

## Adding a new MCP tool

1. Add the tool function in `src/heap_seance_mcp/tools.py` — follow the existing pattern (return a `ToolResult` dict via `ok_result`/`error_result`).
2. Register it in `src/heap_seance_mcp/server.py` as an `@mcp.tool()`.
3. Add parser logic in `parsers.py` if the tool calls an external CLI.
4. Add unit tests in `tests/`.
5. Update the MCP Tools table in `README.md`.

## Improving a skill (slash command)

1. Edit the command in `.claude/commands/` (`leak-scan.md` or `leak-deep.md`).
2. Test by copying the updated command into a Java project and running it against a scenario from `examples/java-scenarios/`.

## Adding a new heuristic signal

1. Add the signal function in `src/heap_seance_mcp/heuristics.py`.
2. Wire it into `overall_confidence()`.
3. Add unit tests in `tests/test_heuristics.py`.
4. Update the confidence ladder in `README.md` if the signal changes the escalation model.

## Running tests

```bash
python3 -m unittest discover -s tests -p "test_*.py"
```

## Code style

- Python 3.10+ with type hints.
- No external dependencies beyond `mcp` — keep the tool lightweight.
- Prefer explicit error handling over silent failures.

## License

By contributing, you agree that your contributions will be dual-licensed under MIT and Apache 2.0, at the user's option.
