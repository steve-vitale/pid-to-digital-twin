"""Offline, descriptive review-effort records. No model calls or efficacy claims."""
import argparse
import hashlib
import json
import math
import statistics
import sys
from datetime import datetime
from pathlib import Path

ARMS = ('baseline', 'ai_assisted')
STATUSES = ('complete', 'abstained', 'failed', 'missing')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def sha(value):
    return isinstance(value, str) and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


def digest(protocol):
    return hashlib.sha256(json.dumps(protocol, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def number(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def validate_protocol(p):
    require(isinstance(p, dict) and p.get('schema') == 'review-effort-1', 'unsupported protocol schema')
    for field in ('study_id', 'baseline_workflow', 'assisted_workflow', 'task_definition',
                  'timing_rule', 'assignment_rule', 'analysis_plan', 'critical_error_rubric',
                  'quality_acceptance_rule', 'exclusion_rule', 'sample_size_rationale', 'eligible_information_rule'):
        require(nonempty(p.get(field)), f'protocol requires {field}')
    try:
        frozen = datetime.fromisoformat(p['frozen_at'].replace('Z', '+00:00'))
        require(frozen.tzinfo is not None, 'frozen_at needs timezone')
    except (KeyError, AttributeError, TypeError, ValueError) as exc:
        raise ValueError('protocol requires timezone-aware frozen_at') from exc
    require(type(p.get('synthetic')) is bool, 'synthetic must be explicitly true or false')
    tasks = p.get('tasks')
    assignments = p.get('assignments')
    require(isinstance(tasks, list) and tasks, 'register at least one task')
    require(isinstance(assignments, list) and assignments, 'register assignments')
    task_ids = set()
    for task in tasks:
        require(isinstance(task, dict), 'task must be an object')
        tid = task.get('task_id')
        require(nonempty(tid) and tid not in task_ids, 'invalid/duplicate task_id')
        task_ids.add(tid)
        require(sha(task.get('source_bundle_sha256')), 'task requires eligible source bundle hash')
        require(nonempty(task.get('truth_reference')), 'task requires independent truth reference')
    ids, cells, exposures = set(), set(), set()
    for a in assignments:
        require(isinstance(a, dict), 'assignment must be an object')
        aid, tid, arm, reviewer = (a.get(k) for k in ('assignment_id', 'task_id', 'arm', 'reviewer_id'))
        require(nonempty(aid) and aid not in ids, 'invalid/duplicate assignment_id')
        require(nonempty(tid) and tid in task_ids and arm in ARMS and nonempty(reviewer), 'invalid assignment task/arm/reviewer')
        require(type(a.get('period')) is int and a['period'] > 0, 'period must be positive integer')
        require((tid, arm) not in cells, 'one assignment per task and arm in this bounded design')
        require((tid, reviewer) not in exposures, 'same reviewer cannot see both arms of same task')
        ids.add(aid); cells.add((tid, arm)); exposures.add((tid, reviewer))
    require(cells == {(tid, arm) for tid in task_ids for arm in ARMS}, 'each task needs both arms')
    return {a['assignment_id']: a for a in assignments}, {t['task_id']: t for t in tasks}


def summarize(protocol, records):
    assignments, tasks = validate_protocol(protocol)
    require(isinstance(records, list), 'records must be an array')
    protocol_hash = digest(protocol)
    seen = {}
    for r in records:
        require(isinstance(r, dict), 'record must be an object')
        aid = r.get('assignment_id')
        require(nonempty(aid) and aid in assignments and aid not in seen, 'unknown/duplicate assignment record')
        a = assignments[aid]
        require(r.get('protocol_sha256') == protocol_hash, 'record protocol hash mismatch')
        require(r.get('source_bundle_sha256') == tasks[a['task_id']]['source_bundle_sha256'], 'eligible source hash mismatch')
        require(r.get('status') in STATUSES, 'invalid status')
        require(r.get('evidence_kind') == ('synthetic' if protocol['synthetic'] else 'human_observation'), 'record evidence_kind must match protocol; do not mix synthetic and human records')
        for field in ('preparation_minutes', 'review_minutes'):
            require(r.get(field) is None or number(r[field]), f'{field} must be null or finite nonnegative number')
        errors = r.get('residual_critical_errors')
        require(errors is None or (type(errors) is int and errors >= 0), 'critical errors must be null or nonnegative integer')
        audit = r.get('audit')
        if errors is not None:
            require(isinstance(audit, dict), 'critical error count requires independent audit')
            require(nonempty(audit.get('reviewer_id')) and audit['reviewer_id'] != a['reviewer_id'], 'auditor must differ from task reviewer')
            require(audit.get('truth_reference') == tasks[a['task_id']]['truth_reference'], 'audit truth reference mismatch')
            require(nonempty(audit.get('artifact_reference')) and nonempty(audit.get('evidence_reference')), 'audit needs final artifact and evidence references')
        if r['status'] == 'complete':
            require(all(r.get(k) is not None for k in ('preparation_minutes', 'review_minutes', 'residual_critical_errors')), 'complete requires timings and audited critical errors')
        else:
            require(nonempty(r.get('reason')), 'noncomplete record needs reason')
        seen[aid] = r
    rows, arms = [], {}
    for aid, a in assignments.items():
        r = seen.get(aid, {'status': 'missing', 'reason': 'no record supplied'})
        row = {**a, **{k: r.get(k) for k in ('status', 'reason', 'preparation_minutes', 'review_minutes', 'residual_critical_errors', 'evidence_kind', 'source_bundle_sha256', 'audit')}}
        row['total_labor_minutes'] = (r['preparation_minutes'] + r['review_minutes']
                                      if r.get('preparation_minutes') is not None and r.get('review_minutes') is not None else None)
        require(row['total_labor_minutes'] is None or number(row['total_labor_minutes']), 'total labor overflow')
        rows.append(row)
    for arm in ARMS:
        group = [r for r in rows if r['arm'] == arm]
        arms[arm] = {'assigned': len(group), 'statuses': {s: sum(r['status'] == s for r in group) for s in STATUSES}}
        for field in ('review_minutes', 'total_labor_minutes', 'residual_critical_errors'):
            values = [r[field] for r in group if r[field] is not None]
            require(not values or number(sum(values)), f'{field} sum overflow')
            arms[arm][field] = {'observed_n': len(values), 'missing_n': len(group) - len(values),
                                'sum': sum(values) if values else None,
                                'median': statistics.median(values) if values else None}
    paired = []
    for tid in tasks:
        pair = {r['arm']: r for r in rows if r['task_id'] == tid}
        if all(r['status'] == 'complete' for r in pair.values()):
            paired.append({'task_id': tid, **{f'{k}_ai_minus_baseline': pair['ai_assisted'][k] - pair['baseline'][k]
                                            for k in ('review_minutes', 'total_labor_minutes', 'residual_critical_errors')}})
    return {'schema': 'review-effort-report-1', 'protocol_sha256': protocol_hash,
            'evidence_label': 'SYNTHETIC TOOL TEST ONLY; NOT HUMAN RESULTS' if protocol['synthetic'] else 'SUPPLIED HUMAN RECORDS; NOT INDEPENDENTLY VERIFIED BY TOOL',
            'claims': 'Descriptive only. No benefit, safety, noninferiority, or operator-usability conclusion.',
            'limitations': ['Source equality, independent review and preregistration are supplied assertions, not verified by hashing.',
                           'Complete-pair deltas exclude incomplete pairs; inspect all assignment statuses and missing counts.',
                           'Task pairing does not remove reviewer, period, learning or order confounding.'],
            'arms': arms, 'assignments': rows, 'complete_task_pairs': paired,
            'incomplete_task_pairs': len(tasks) - len(paired)}


def template():
    return {'schema': 'review-effort-1', 'study_id': '', 'synthetic': False, 'frozen_at': None,
            **{k: '' for k in ('baseline_workflow', 'assisted_workflow', 'task_definition', 'timing_rule',
                               'assignment_rule', 'analysis_plan', 'critical_error_rubric', 'quality_acceptance_rule',
                               'exclusion_rule', 'sample_size_rationale', 'eligible_information_rule')}, 'tasks': [], 'assignments': []}


def read_json(path):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, f'duplicate JSON key: {key}')
            result[key] = value
        return result

    def constant(value):
        raise ValueError(f'nonfinite JSON constant: {value}')

    return json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=pairs, parse_constant=constant)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('template')
    freeze = sub.add_parser('validate')
    freeze.add_argument('protocol', type=Path)
    report = sub.add_parser('report')
    report.add_argument('protocol', type=Path)
    report.add_argument('records', type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == 'template':
            result = template()
        else:
            p = read_json(args.protocol)
            validate_protocol(p)
            result = ({'protocol_sha256': digest(p), 'status': 'valid; freeze history not verified'}
                      if args.command == 'validate' else summarize(p, read_json(args.records)))
        print(json.dumps(result, indent=2, allow_nan=False))
        return 0
    except (ValueError, OSError, TypeError, KeyError) as exc:
        print(f'INVALID: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
