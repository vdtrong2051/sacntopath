"""Kiểm kê chú thích Python; chỉ đọc mã nguồn và xuất báo cáo ngoài repository."""
from __future__ import annotations

import argparse
import ast
import csv
import io
import json
from datetime import datetime, timezone
from pathlib import Path
import tokenize

# Heuristic phục vụ chỉ dẫn người biên tập; không phải bộ phân loại ngôn ngữ tin cậy.
VI_CHARS = set('ăâđêôơưĂÂĐÊÔƠƯ')
DIACRITICS = set('àáảãạằắẳẵặầấẩẫậèéẻẽẹềếểễệìíỉĩịòóỏõọồốổỗộờớởỡợùúủũụừứửữựỳýỷỹỵ')


def language_hint(text: str) -> str:
    letters = sum(ch.isalpha() for ch in text)
    hints = sum(ch in VI_CHARS or ch in DIACRITICS for ch in text)
    if letters < 8:
        return 'KHONG_RO'
    if hints >= 2:
        return 'CO_TIENG_VIET'
    return 'CAN_DOC_THU_CONG'


def _doc_nodes(tree: ast.AST) -> list[str]:
    docs = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            x = ast.get_docstring(node, clean=False)
            if x is not None:
                docs.append(x)
    return docs


def inspect(root: Path) -> dict:
    files = sorted((root / 'src/scantopath').rglob('*.py'))
    records: list[dict] = []
    failures: list[dict] = []
    for p in files:
        rel = p.relative_to(root).as_posix()
        if p.is_symlink():
            failures.append({'duong_dan': rel, 'loi': 'SYMLINK'})
            continue
        try:
            raw = p.read_bytes()
            tree = ast.parse(raw.decode('utf-8-sig'))
            comments = [token.string.lstrip('#').strip() for token in tokenize.tokenize(io.BytesIO(raw).readline)
                        if token.type == tokenize.COMMENT]
            docs = _doc_nodes(tree)
            module_doc = ast.get_docstring(tree, clean=False)
            records.append({
                'duong_dan': rel,
                'so_dong': len(raw.splitlines()),
                'so_chu_thich': len(comments),
                'so_docstring': len(docs),
                'co_docstring_module': bool(module_doc),
                'goi_y_ngon_ngu': language_hint(' '.join(comments + docs)),
                'ghi_chu': 'Ưu tiên kiểm tra an toàn' if any(x in rel for x in
                            ('resident_poc/', 'session_store.py', 'metadata/store.py',
                             'acquisition/native.py', 'project_workspace/application/service.py')) else '',
            })
        except (SyntaxError, UnicodeError, tokenize.TokenError, OSError) as exc:
            failures.append({'duong_dan': rel, 'loi': type(exc).__name__})
    return {
        'schema': 'scantopath-r7c-source-comment-inventory-v1',
        'tao_luc_utc': datetime.now(timezone.utc).isoformat(),
        'so_tap_python': len(files),
        'so_tap_doc_duoc': len(records),
        'so_tap_chua_docstring_module': sum(not x['co_docstring_module'] for x in records),
        'so_docstring': sum(x['so_docstring'] for x in records),
        'so_chu_thich': sum(x['so_chu_thich'] for x in records),
        'tap_tin': records,
        'loi_doc': failures,
        'gioi_han': 'Gợi ý ngôn ngữ chỉ là heuristic; không được tính là chứng nhận Việt hóa 100%.',
    }


def main() -> int:
    p = argparse.ArgumentParser(description='Kiểm kê docstring/comment ScanToPath')
    p.add_argument('--project-root', required=True, type=Path)
    p.add_argument('--out-dir', required=True, type=Path)
    a = p.parse_args()
    root = a.project_root.resolve(strict=True)
    evidence = a.out_dir.resolve()
    if evidence == root or root in evidence.parents:
        raise ValueError('EVIDENCE_MUST_BE_OUTSIDE_REPOSITORY')
    result = inspect(root)
    evidence.mkdir(parents=True, exist_ok=True)
    (evidence / 'R7C_KIEM_KE_CHU_THICH.json').write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    with (evidence / 'R7C_KIEM_KE_CHU_THICH.csv').open('w', encoding='utf-8-sig', newline='') as stream:
        fields = ['duong_dan', 'so_dong', 'so_chu_thich', 'so_docstring',
                  'co_docstring_module', 'goi_y_ngon_ngu', 'ghi_chu']
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(result['tap_tin'])
    status = 'PASS' if not result['loi_doc'] else 'FAIL'
    print(f"R7-C KIEM KE {status}: {result['so_tap_doc_duoc']}/{result['so_tap_python']} tep Python; "
          f"{result['so_docstring']} docstring; {result['so_chu_thich']} comment")
    return 0 if status == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
