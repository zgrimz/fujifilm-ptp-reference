#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Validate a public evidence report's schema and cross-field consistency.

Requires requirements-test.txt. Validity is not verification of the claimed hardware result.
"""
import argparse
import json
from pathlib import Path
import sys


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'duplicate JSON key: {key}')
        result[key] = value
    return result


def validate_document(doc):
    import jsonschema
    schema=json.loads((Path(__file__).resolve().parents[1]/'evidence/report.schema.json').read_text())
    validator=jsonschema.Draft202012Validator(schema,format_checker=jsonschema.FormatChecker())
    errors=[f"{'.'.join(map(str,e.absolute_path)) or '$'}: {e.message}" for e in validator.iter_errors(doc)]
    if errors:
        return errors
    connections=[c['id'] for c in doc['connections']]
    if len(set(connections)) != len(connections): errors.append('duplicate connection id')
    operations=set()
    for row in doc['observations']:
        op=row['operationId']
        if op in operations: errors.append(f'{op}: duplicate operation id')
        operations.add(op)
        if row['connectionId'] not in connections: errors.append(f'{op}: unknown connection id')
        expected, actual, state=row['expected'],row['readback'],row['verification']
        available={k for k,v in (actual or {}).items() if v is not None}
        differing=[k for k,v in expected.items() if k in available and v is not None and actual[k]!=v]
        complete=bool(expected) and all(v is not None and k in available for k,v in expected.items())
        if state=='matched' and (not complete or differing): errors.append(f'{op}: matched requires nonempty, complete, equal readback')
        if state=='mismatched' and not differing: errors.append(f'{op}: mismatched requires an observed difference')
        if not expected and state!='not_tested': errors.append(f'{op}: no expected fields means not_tested')
        command, code=row['commandOutcome'],row.get('responseCode')
        if command=='accepted' and code!=0x2001: errors.append(f'{op}: accepted needs OK response')
        if command=='refused' and (code is None or code==0x2001): errors.append(f'{op}: refused needs non-OK response')
        if command in ('not_attempted','outcome_unknown') and code is not None: errors.append(f'{op}: unavailable response expected')
    if doc['trace']['droppedCount'] and not doc['trace']['truncated']:
        errors.append('dropped trace entries require truncated=true')
    return errors


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('report');args=p.parse_args(argv)
    try:
        doc=json.loads(Path(args.report).read_text(),object_pairs_hook=unique_object)
        errors=validate_document(doc)
    except ImportError:
        print('Install requirements-test.txt to validate the evidence schema.',file=sys.stderr);return 2
    except (OSError,ValueError) as exc:
        print(f'evidence: {exc}',file=sys.stderr);return 2
    if errors:
        print('\n'.join(errors),file=sys.stderr);return 1
    print('evidence schema and consistency: ok');return 0


if __name__=='__main__': sys.exit(main())
