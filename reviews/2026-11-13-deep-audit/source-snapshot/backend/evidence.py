"""Immutable, server-time evidence packages; native provider history stays separate."""
from copy import deepcopy
import hashlib
import json


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode('utf-8')).hexdigest()


class EvidenceStore:
    def __init__(self, trace):
        self.trace = trace
        self._items = []
        self._package_count = 0

    def add(self, kind, content, *, captured_at, available_at=None,
            source_request_id=None, chart_revision=None, response_id=None,
            clock_uncertainty=0, raw_clock=None, calibration_id=None):
        item = deepcopy(dict(kind=kind, content=content, captured_at=captured_at,
                             available_at=self.trace.now_ms() if available_at is None else available_at,
                             source_request_id=source_request_id, chart_revision=chart_revision,
                             response_id=response_id, clock_uncertainty=clock_uncertainty,
                             raw_clock=raw_clock, calibration_id=calibration_id))
        item['content_sha256'] = digest(item['content'])
        item['evidence_id'] = f'{self.trace.session_id}:evidence:{len(self._items)}'
        self._items.append(item)
        return deepcopy(item)

    def package(self, cutoff, *, request_id=None):
        items, excluded = [], []
        for item in self._items:
            capture, error = item['captured_at'], item['clock_uncertainty']
            if item['available_at'] > cutoff:
                reason = 'not_available'
            elif capture is None or error is None:
                reason = 'unknown_capture'
            elif capture - error > cutoff:
                reason = 'future_capture'
            elif capture + error > cutoff:
                reason = 'clock_uncertain'
            else:
                items.append(deepcopy(item))
                continue
            excluded.append({'evidence_id': item['evidence_id'], 'reason': reason})
        self._package_count += 1
        package = dict(package_id=f'{self.trace.session_id}:package:{self._package_count}',
                       cutoff=cutoff, request_id=request_id, items=items, excluded=excluded)
        package['content_sha256'] = digest(package)
        package['file'] = f'evidence-package-{self._package_count:05d}.json'
        self.trace.save(package['file'], package)
        self.trace.record('evidence_package', package_id=package['package_id'], cutoff=cutoff,
                          request_id=request_id, file=package['file'],
                          content_sha256=package['content_sha256'],
                          evidence_ids=[item['evidence_id'] for item in items], excluded=excluded)
        return deepcopy(package)
