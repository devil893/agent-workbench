# Reproducible ASI05 evaluation

This is a **new target**, not the deployed target described in any earlier statement of work. Confirm target substitution, SQLite storage, the synthetic browser, and the simulated external integrations with the evaluator before claiming the earlier scope is fulfilled.

## Install the pinned evaluator

```sh
python -m pip install -e ".[dev]"
python -m pip install -r requirements-eval.txt
```

Pin: `AgentSafeLabs/safelabs-eval` commit `1fb34b83b154170551be677df3b350289edf6dcd` (v0.11.2). The runner checks library content 1.13.0, schema 1.1.0 and exactly 30 ASI05 cases before running.

## Transport smoke test

```sh
python -m workbench.evaluate --smoke --output results/transport-smoke
```

No LLM is contacted. This exercises all 30 prompts through the unchanged evaluator against the deterministic backend. Its scores **are not agent-safety findings** and should not be presented as such. Use the application tests to exercise real local tool effects and approval paths.

## Model-backed run

Set `ANTHROPIC_API_KEY` and `ANTHROPIC_MODEL` in an isolated environment. No Google or Twilio credentials are used by the runner. Only the model connection is live. Then:

```sh
python -m workbench.evaluate --output results/asi05-baseline
```

The runner creates a disposable database and a fresh synthetic tenant for each prompt/attempt. It never grants human approval automatically. It preserves:

1. `framework-baseline.json`: serialization of the framework's returned result, without changing scores or verdicts.
2. `tool-events.jsonl`: separate requested actions, policy outcomes, execution outcomes, and explicit no-tool-call entries.
3. `comparison.json`: original verdict alongside observed action statuses, without recomputing a verdict.
4. `manifest.json`: Python/dependency versions, target commit and source hashes, dirty-tree status, model, prompt versions, tool classifications, baseline digest, and limitations.

An output directory must be new, preventing accidental overwrites. A model/provider failure is returned to the evaluator as an error rather than a successful refusal. Synthetic smoke runs and real model runs must have different output directories. Keep findings private unless publication has separately been agreed.

## Applicability

SQL, approval, tenant isolation, local storage, and tool-call recording are executable controls here. External Google writes and bookings can establish an attempted action or simulated outcome only. Shell, code execution, deployment, arbitrary file reads, voice, and live network browsing are absent capabilities, not successful defenses against those action classes. No claim is made that simulation predicts live API behavior.

The supplied project uses 12 specialist groups but not the old project's 54-tool inventory. Obtain the actual current inventory from `/tools` or the run manifest. Results apply only to this implementation, selected model, configuration, and prompt set. No paid model evaluation has been run during initial project creation.
