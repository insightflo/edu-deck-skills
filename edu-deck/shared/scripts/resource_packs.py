#!/usr/bin/env python3
"""Validate resource-pack selections and scaffold editable, flow-led slide sources.

Catalog contract: flows.json contains {"flows": [{"id": ..., "stages": [...]}]}.
Each stage is a string or an object with title/prompt/body/evidence/action strings.
Templates are local HTML; all six replacement values are escaped plain text.
No legacy visual assets, network access, or third-party dependencies are used.
"""
import argparse
import html
import json
from pathlib import Path
import re
import sys

BASE = Path(__file__).resolve().parent.parent
DESIGNS = ('editorial', 'lab', 'field', 'casebook', 'atlas', 'workbook', 'briefing', 'seminar')
FLOWS = ('problem', 'case', 'follow', 'inquiry', 'compare', 'diagnose', 'discussion', 'project')


class PackError(ValueError):
    """An invalid selection or incomplete installed pack; no output should be written."""


def validate_selection(value: object) -> dict:
    """Reject unknown IDs and unsafe paths before looking up any pack file."""
    if not isinstance(value, dict):
        raise PackError('resource_pack must be an object')
    if any(key not in ('design', 'flow', 'activities') for key in value):
        raise PackError('resource_pack supports only design, flow, activities')
    for key, choices in (('design', DESIGNS), ('flow', FLOWS)):
        if not isinstance(value.get(key), str) or value[key] not in choices:
            raise PackError(f'resource_pack.{key} must be one of: {", ".join(choices)}')
    activities = value.get('activities', [])
    if not isinstance(activities, list) or len(activities) > 2:
        raise PackError('resource_pack.activities must be an array with at most two flow IDs')
    if any(not isinstance(item, str) or item not in FLOWS or item == value['flow']
           for item in activities):
        raise PackError('activities must use other valid flow IDs, not the main flow')
    if len(set(activities)) != len(activities):
        raise PackError('activities must not contain duplicate flow IDs')
    return dict(value)


def load_flow(pack_dir: Path, flow_id: str) -> dict:
    """Read the selected teaching flow, not a fixed sequence shared by every design."""
    catalog = json.loads((pack_dir / 'flows.json').read_text(encoding='utf-8'))
    flows = catalog.get('flows', []) if isinstance(catalog, dict) else catalog
    if isinstance(flows, dict):
        flow = flows.get(flow_id)
    elif isinstance(flows, list):
        flow = next((item for item in flows if isinstance(item, dict) and item.get('id') == flow_id), None)
    else:
        flow = None
    if not isinstance(flow, dict) or not isinstance(flow.get('stages'), list) or not flow['stages']:
        raise PackError(f'flows.json: {flow_id} needs a nonempty stages array')
    return flow


def init_deck(out: Path, design: str, flow: str, title: str) -> Path:
    """Prepare all sources before creating OUT; refuse to overwrite a nonempty folder."""
    selection = validate_selection({'design': design, 'flow': flow})
    if not title.strip():
        raise PackError('title must not be empty')
    if out.exists() and (not out.is_dir() or any(out.iterdir())):
        raise PackError(f'output directory is not empty: {out}')
    packs = BASE / 'assets' / 'packs'
    template = (packs / design / 'template.html').read_text(encoding='utf-8')
    if not re.search(r'<section\b[^>]*\bclass="slide[\s"]', template):
        raise PackError('pack template must contain a section with class="slide"')
    if re.search(r'<script\b', re.sub(r'<!--.*?-->', '', template, flags=re.S), re.I):
        raise PackError('pack templates must not contain scripts')
    flow_data = load_flow(packs, flow)
    sources = []
    for index, stage in enumerate(flow_data['stages'], 1):
        if isinstance(stage, str):
            stage = {'title': stage}
        if not isinstance(stage, dict):
            raise PackError('each flow stage must be a string or object')
        values = {
            'TITLE': title.strip(),
            'KICKER': f'{index:02d} · {stage.get("title", stage.get("label", flow))}',
            'PROMPT': stage.get('prompt', '«이 단계에서 답할 질문»'),
            'BODY': stage.get('body', '«학습자가 알아야 할 내용과 예시»'),
            'EVIDENCE': stage.get('evidence', '«확인할 자료·근거»'),
            'ACTION': stage.get('action', '«학습자가 직접 할 일»'),
        }
        if any(not isinstance(value, str) for value in values.values()):
            raise PackError('flow stage template values must be plain strings')
        def replace_token(match: re.Match[str]) -> str:
            key = match.group(1)
            return html.escape(values[key]) if key in values else match.group(0)

        rendered = re.sub(r'\{\{([A-Z_]+)\}\}', replace_token, template)
        if re.search(r'\{\{[A-Z_]+\}\}', rendered):
            raise PackError('unknown template token')
        sources.append(rendered)
    cfg = {'title': title.strip(), 'output': 'deck.html', 'resource_pack': selection}
    (out / 'src').mkdir(parents=True, exist_ok=True)
    for index, source in enumerate(sources, 1):
        (out / 'src' / f'{index:02d}-{flow}.html').write_text(source, encoding='utf-8')
    (out / 'deck.json').write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return out / 'deck.json'


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    init = commands.add_parser('init', help='create deck.json and editable src/*.html')
    init.add_argument('out', type=Path)
    init.add_argument('--design', required=True, choices=DESIGNS)
    init.add_argument('--flow', required=True, choices=FLOWS)
    init.add_argument('--title', default='새 교육 덱')
    args = parser.parse_args(argv)
    try:
        path = init_deck(args.out.resolve(), args.design, args.flow, args.title)
    except (PackError, OSError, ValueError) as exc:
        print(f'ERROR  {exc}', file=sys.stderr)
        return 1
    print(f'OK     {path}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
