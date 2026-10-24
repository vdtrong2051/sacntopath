"""Regression for the 07.11 PowerShell -c broken-quote acceptance defect."""
from __future__ import annotations
import sys
from pathlib import Path
from xml.etree.ElementTree import Element,SubElement,ElementTree

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from check_qt_acceptance_xml import REQUIRED,validate


def _fake_xml(path,skip=None,missing=None):
    root=Element('testsuite')
    for name in REQUIRED:
        if name==missing:continue
        node=SubElement(root,'testcase',name=name)
        if name==skip:SubElement(node,'skipped',message='not installed')
    for i in range(350):SubElement(root,'testcase',name=f'test_old_{i}')
    ElementTree(root).write(path,encoding='utf-8',xml_declaration=True)


def test_0712_junit_qt_parser_accepts_only_real_executions(tmp_path):
    f=tmp_path/'r.xml';_fake_xml(f)
    result=validate(f)
    assert result['errors']==[] and result['qt_required']==4


def test_0712_junit_qt_parser_fails_on_skipped_qt(tmp_path):
    f=tmp_path/'r.xml';_fake_xml(f,skip=REQUIRED[-1])
    assert any('skipped' in x for x in validate(f)['errors'])


def test_0712_junit_qt_parser_fails_on_missing_qt(tmp_path):
    f=tmp_path/'r.xml';_fake_xml(f,missing=REQUIRED[0])
    assert validate(f)['errors']
