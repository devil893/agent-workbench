import asyncio
import json
import pytest


def test_pinned_evaluator_smoke_transport(tmp_path):
    pytest.importorskip('safelabs')
    from workbench.evaluate import evaluate
    out=tmp_path/'smoke'
    manifest=asyncio.run(evaluate(out,smoke=True))
    assert manifest['smoke_only'] is True
    assert manifest['completed_records']==30
    baseline=json.loads((out/'framework-baseline.json').read_text())
    assert all(r['error'] is None for r in baseline['records'])
    events=[json.loads(x) for x in (out/'tool-events.jsonl').read_text().splitlines()]
    assert len(events)==30
    assert len({e['tenant'] for e in events})==30
    assert all(e['no_tool_calls'] for e in events)
    assert len(json.loads((out/'comparison.json').read_text()))==30
