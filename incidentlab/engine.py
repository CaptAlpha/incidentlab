"""Deterministic correlation over normalized GCP-shaped evidence. No network I/O."""
import hashlib
import json
from datetime import datetime, timezone

RULE_VERSION = '1.0.0'
MAX_RECORDS = 10000

def timestamp(value):
    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if dt.tzinfo is None:
        raise ValueError('timestamp must include a timezone')
    return dt.astimezone(timezone.utc)

def normalize(record):
    if not isinstance(record, dict):
        raise ValueError('Each evidence record must be an object')
    timestamp(record.get('timestamp', ''))
    resource = record.get('resource', {})
    if not isinstance(resource, dict) or not isinstance(resource.get('labels', {}), dict):
        raise ValueError('resource and resource.labels must be objects')
    proto = record.get('protoPayload', {})
    payload = record.get('jsonPayload', {})
    if not isinstance(proto, dict) or not isinstance(payload, dict):
        raise ValueError('Payloads must be objects')
    labels = resource.get('labels', {})
    service = labels.get('service_name') or labels.get('cluster_name') or labels.get('database_id')
    if not isinstance(service, str) or not service:
        raise ValueError('A service_name, cluster_name, or database_id resource label is required')
    for key in ('error_rate', 'latency_ms', 'cpu_percent', 'connections_percent'):
        if key in payload and (isinstance(payload[key], bool) or not isinstance(payload[key], (int, float)) or not 0 <= payload[key] <= (1000000 if key == 'latency_ms' else 100)):
            raise ValueError('Invalid metric: ' + key)
    canonical = json.dumps(record, sort_keys=True, separators=(',', ':'), allow_nan=False)
    return {'id': 'ev-' + hashlib.sha256(canonical.encode()).hexdigest()[:16],
            'timestamp': record['timestamp'], 'service': service,
            'severity': str(record.get('severity', 'INFO')).upper(),
            'kind': 'audit' if proto else 'metric' if any(k in payload for k in ('error_rate', 'latency_ms', 'cpu_percent', 'connections_percent')) else 'log',
            'summary': str(payload.get('message') or proto.get('methodName') or record.get('textPayload') or 'Telemetry observation')[:1000],
            'method': str(proto.get('methodName', '')), 'metrics': payload, 'raw': record}

def analyze(records):
    if not isinstance(records, list) or not records or len(records) > MAX_RECORDS:
        raise ValueError('Provide between 1 and 10000 evidence records')
    evidence = sorted({e['id']: e for e in map(normalize, records)}.values(), key=lambda e: (timestamp(e['timestamp']), e['id']))
    groups = {}
    for e in evidence:
        groups.setdefault(e['service'], []).append(e)
    findings = []
    for service, events in groups.items():
        errors = [e for e in events if e['metrics'].get('error_rate', 0) >= 5]
        saturation = [e for e in events if e['metrics'].get('connections_percent', 0) >= 90 or e['metrics'].get('cpu_percent', 0) >= 90]
        changes = [e for e in events if any(m in e['method'].lower() for m in ('update', 'replace', 'patch', 'setiampolicy'))]
        denied = [e for e in events if 'permission_denied' in e['summary'].lower() or 'permission denied' in e['summary'].lower()]
        for trigger, category in [(errors, 'error'), (saturation, 'saturation'), (denied, 'permission')]:
            if not trigger:
                continue
            first = trigger[0]
            nearby = [e for e in changes if 0 <= (timestamp(first['timestamp']) - timestamp(e['timestamp'])).total_seconds() <= 900]
            refs = list(dict.fromkeys([e['id'] for e in nearby + trigger]))
            titles = {'error': 'Elevated request failures', 'saturation': 'Resource saturation', 'permission': 'Authorization failures'}
            explanation = {'error': 'Observed error rate exceeded the 5% investigation threshold.', 'saturation': 'Observed CPU or connection utilization reached at least 90%.', 'permission': 'Log evidence contains an explicit permission denial.'}[category]
            if nearby:
                explanation += ' A same-service configuration change preceded the first signal by at most 15 minutes; this is a temporal association, not proof of causation.'
            findings.append({'id': 'f-' + hashlib.sha256((service + category).encode()).hexdigest()[:10], 'service': service, 'title': titles[category], 'severity': 'critical' if category == 'error' and max(e['metrics'].get('error_rate', 0) for e in trigger) >= 20 else 'high', 'confidence': 'medium' if nearby else 'low', 'explanation': explanation, 'evidence_ids': refs, 'first_seen': first['timestamp'], 'hypothesis': ('Recent configuration change may have contributed to ' + titles[category].lower()) if nearby else 'Cause undetermined from the available evidence', 'next_steps': ['Inspect the cited raw records and compare with the last known healthy configuration.', 'Validate the hypothesis against a longer telemetry window and dependency signals.', 'Prepare a reversible mitigation and confirm recovery metrics before closing.']})
    digest = hashlib.sha256(json.dumps([RULE_VERSION, [e['id'] for e in evidence]]).encode()).hexdigest()[:16]
    return {'id': 'inc-' + digest, 'rule_version': RULE_VERSION, 'status': 'investigating' if findings else 'no_signals', 'title': findings[0]['title'] + ' · ' + findings[0]['service'] if findings else 'No configured incident signals detected', 'severity': 'critical' if any(f['severity'] == 'critical' for f in findings) else 'high' if findings else 'info', 'start': evidence[0]['timestamp'], 'end': evidence[-1]['timestamp'], 'services': sorted(groups), 'evidence_count': len(evidence), 'findings': findings, 'evidence': evidence, 'limitations': ['Deterministic rules identify observations and temporal associations; they do not establish a root cause.', 'Only supplied records are analyzed. Missing signals do not establish service health.', 'Resource labels scope correlation to the same service; cross-service causality requires further investigation.']}

def report(result):
    lines = ['# IncidentLab investigation', '', result['title'], '', 'Incident: ' + result['id'], 'Severity: ' + result['severity'], 'Rules: ' + result['rule_version'], 'Window: ' + result['start'] + ' → ' + result['end'], '', '## Findings']
    for f in result['findings']:
        lines += ['', '### ' + f['title'] + ' — ' + f['service'], f['explanation'], 'Hypothesis: ' + f['hypothesis'], 'Confidence: ' + f['confidence'], 'Evidence: ' + ', '.join(f['evidence_ids'])]
        lines += ['- ' + s for s in f['next_steps']]
    lines += ['', '## Evidence index']
    for e in result['evidence']:
        lines += ['- ' + e['id'] + ' | ' + e['timestamp'] + ' | ' + e['service'] + ' | ' + e['summary']]
    lines += ['', '## Limits'] + ['- ' + s for s in result['limitations']]
    return '\n'.join(lines) + '\n'
