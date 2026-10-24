"""PowerShell-safe JUnit acceptance parser: never embed Python quoting in -c."""
from __future__ import annotations
import argparse
from pathlib import Path
import xml.etree.ElementTree as ET

REQUIRED = (
    'test_shell_composes_feature_controller_without_autoload',
    'test_project_flow_through_composed_controller_in_v1_view_mode',
    'test_0712_qt_collaborators_share_only_the_feature_qobject',
    'test_0712_qt_shell_retains_controller_legacy_delegates',
)

def validate(path: Path) -> dict:
    tests=list(ET.parse(path).iter('testcase'))
    issues=[]
    for name in REQUIRED:
        matching=[case for case in tests if case.get('name')==name]
        if len(matching)!=1 or list(matching[0]):
            issues.append(f'Qt test missing, skipped, failed or duplicated: {name}')
    skips=[case for case in tests if case.find('skipped') is not None]
    for case in skips:
        reason=(case.find('skipped').get('message','') or '')+' '+(case.find('skipped').text or '')
        if 'symlink' not in reason.lower():
            issues.append(f'Unexpected skip: {case.get("name")}: {reason[:180]}')
    if len(skips)>2:issues.append(f'Too many skipped tests: {len(skips)}')
    if any(case.find('failure') is not None or case.find('error') is not None for case in tests):
        issues.append('At least one JUnit failure/error')
    if len(tests)<350:issues.append('Regression suite appears incomplete: fewer than 350 tests')
    return {'cases':len(tests),'qt_required':len(REQUIRED),'skips':len(skips),'errors':issues}

def main():
    p=argparse.ArgumentParser();p.add_argument('--junit',type=Path,required=True);a=p.parse_args()
    try:r=validate(a.junit)
    except (OSError,ET.ParseError) as e:print('Qt acceptance XML error:',e);return 1
    print('Qt acceptance:',r)
    return 1 if r['errors'] else 0
if __name__=='__main__':raise SystemExit(main())
