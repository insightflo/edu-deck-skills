#!/usr/bin/env python3
"""Standard-library integration tests; fixtures isolate pack assets from legacy ones."""
import contextlib
import importlib
import io
from html.parser import HTMLParser
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

SHARED = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SHARED / 'scripts'))
build_deck = importlib.import_module('build_deck')


class ResourcePackTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.assets = self.root / 'shared' / 'assets'
        self.assets.mkdir(parents=True)
        self.deck = self.root / 'deck'
        (self.deck / 'src').mkdir(parents=True)
        (self.deck / 'src' / '01.html').write_text(
            '<section class="slide"><h1>Fixture</h1><aside class="notes">Note</aside></section>')
        self.original_base = build_deck.BASE
        build_deck.BASE = self.assets.parent
        self.addCleanup(setattr, build_deck, 'BASE', self.original_base)

    def config(self, pack: object = None, *, absent: bool = False) -> None:
        cfg = {'title': 'Fixture', 'output': 'result.html', 'summary': {'one': 'Test'}}
        if not absent:
            cfg['resource_pack'] = pack
        (self.deck / 'deck.json').write_text(json.dumps(cfg))

    def run_build(self) -> int:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return build_deck.main([str(self.deck)])

    def fixture_assets(self, *, legacy: bool) -> None:
        if legacy:
            (self.assets / 'shell.html').write_text(
                '<title>{{TITLE}}</title><style>LEGACY_VISUAL /*EXTRA_CSS*/</style>'
                '<!--ICONS--><!--STUDY_DATA--><!--SLIDES-->')
        else:
            shell = SHARED / 'assets' / 'pack-shell.html'
            self.assertTrue(shell.is_file(), 'independent pack shell is missing')
            shutil.copy2(shell, self.assets / shell.name)
            (self.assets / 'css').mkdir()
            shutil.copy2(SHARED / 'assets' / 'css' / 'pack-runtime.css', self.assets / 'css')
        pack = self.assets / 'packs' / 'editorial'
        pack.mkdir(parents=True)
        (pack.parent / 'base.css').write_text('/* PACK_BASE */')
        (pack / 'style.css').write_text('/* PACK_EDITORIAL */')

    def test_invalid_selection_fails_before_output(self) -> None:
        self.fixture_assets(legacy=True)
        invalid = [None, [], {}, {'design': '../editorial', 'flow': 'problem'},
                   {'design': 'editorial', 'flow': 'bogus'},
                   {'design': 'editorial', 'flow': 'problem', 'activities': 'case'},
                   {'design': 'editorial', 'flow': 'problem', 'activities': ['case'] * 3},
                   {'design': 'editorial', 'flow': 'problem', 'activities': ['problem']},
                   {'design': 'editorial', 'flow': 'problem', 'activities': ['bogus']},
                   {'design': 'editorial', 'flow': 'problem', 'activities': ['case', 'case']},
                   {'design': [], 'flow': 'problem'},
                   {'design': 'editorial', 'flow': 'problem', 'activities': [[]]}]
        for pack in invalid:
            with self.subTest(pack=pack):
                self.config(pack)
                self.assertEqual(self.run_build(), 1)
                self.assertFalse((self.deck / 'result.html').exists())

    def test_unknown_selection_fields_preserve_existing_output(self) -> None:
        self.fixture_assets(legacy=False)
        out = self.deck / 'result.html'
        for value in ('plain', '/*EXTRA_CSS*/', '<!--SLIDES-->', '{{TITLE}}',
                      '<!--ICONS-->', '<!--STUDY_DATA-->'):
            with self.subTest(value=value):
                out.write_text('prior build')
                self.config({'design': 'editorial', 'flow': 'problem', 'comment': value})
                self.assertEqual(self.run_build(), 1)
                self.assertEqual(out.read_text(), 'prior build')

    def test_supported_metadata_round_trips_without_mutating_config(self) -> None:
        self.fixture_assets(legacy=False)
        class MetadataParser(HTMLParser):
            selection = None
            def handle_starttag(self, tag, attrs):
                attrs = dict(attrs)
                if tag == 'meta' and attrs.get('name') == 'edu-deck-resource-pack':
                    self.selection = json.loads(attrs['content'])
        for activities in (None, [], ['case', 'discussion']):
            selection = {'design': 'editorial', 'flow': 'problem'}
            if activities is not None:
                selection['activities'] = activities
            self.config(selection)
            before = (self.deck / 'deck.json').read_bytes()
            self.assertEqual(self.run_build(), 0)
            parser = MetadataParser()
            parser.feed((self.deck / 'result.html').read_text())
            self.assertEqual(parser.selection, selection)
            self.assertEqual((self.deck / 'deck.json').read_bytes(), before)

    def test_catalog_ids_match_runtime_validation(self) -> None:
        from resource_packs import DESIGNS, FLOWS, validate_selection
        packs = SHARED / 'assets' / 'packs'
        designs = [item['id'] for item in json.loads((packs / 'catalog.json').read_text())['designs']]
        flows = [item['id'] for item in json.loads((packs / 'flows.json').read_text())['flows']]
        self.assertCountEqual(designs, DESIGNS)
        self.assertCountEqual(flows, FLOWS)
        for design in designs:
            for flow in flows:
                self.assertEqual(validate_selection({'design': design, 'flow': flow}),
                                 {'design': design, 'flow': flow})

    def test_legacy_build_unchanged_without_resource_pack(self) -> None:
        self.fixture_assets(legacy=True)
        self.config(absent=True)
        (self.assets / 'css').mkdir()
        (self.assets / 'css' / 'pack-runtime.css').write_text('PACK_ONLY_RUNTIME')
        self.assertEqual(self.run_build(), 0)
        self.assertNotIn('PACK_ONLY_RUNTIME', (self.deck / 'result.html').read_text())
        self.assertIn('LEGACY_VISUAL', (self.deck / 'result.html').read_text())
        self.assertEqual(len(build_deck.load_deck(self.deck)), 3)

    def test_pack_build_never_needs_legacy_assets(self) -> None:
        self.fixture_assets(legacy=False)
        self.config({'design': 'editorial', 'flow': 'problem', 'activities': ['case']})
        self.assertEqual(self.run_build(), 0)
        result = (self.deck / 'result.html').read_text()
        self.assertIn('PACK_BASE', result)
        self.assertIn('PACK_EDITORIAL', result)
        self.assertIn('window.deckGo', result)
        self.assertIn('window.studyApi', result)
        self.assertIn('window.EDU_STUDY', result)
        self.assertIn('data-crayon', result)
        self.assertNotIn('LEGACY_VISUAL', result)
        self.assertNotIn('.cx-blob', result)
        self.assertNotIn('<symbol', result)

    def test_missing_pack_asset_is_clean_failure_and_preserves_output(self) -> None:
        self.fixture_assets(legacy=True)
        self.config({'design': 'editorial', 'flow': 'problem'})
        out = self.deck / 'result.html'
        out.write_text('prior build')
        self.assertEqual(self.run_build(), 1)
        self.assertEqual(out.read_text(), 'prior build')

    def test_init_generates_flow_specific_sources_and_escapes_title(self) -> None:
        script = SHARED / 'scripts' / 'resource_packs.py'
        self.assertTrue(script.is_file(), 'resource pack generator is missing')
        # Copy the CLI into an isolated installed layout, using explicit tiny catalog fixtures.
        scripts = self.assets.parent / 'scripts'
        scripts.mkdir()
        shutil.copy2(script, scripts / script.name)
        packs = self.assets / 'packs'
        (packs / 'editorial').mkdir(parents=True)
        (packs / 'editorial' / 'template.html').write_text(
            '<section class="slide"><header>{{KICKER}}</header><h1>{{TITLE}}</h1>'
            '<h2>{{PROMPT}}</h2><p>{{BODY}}</p><p>{{EVIDENCE}}</p><p>{{ACTION}}</p></section>')
        (packs / 'flows.json').write_text(json.dumps({'flows': [
            {'id': 'problem', 'stages': [
                {'title': 'Observe', 'prompt': 'What happened?', 'body': 'Describe problem'},
                {'title': 'Resolve', 'prompt': 'What next?', 'action': 'Try solution'}]}]}))
        out = self.root / 'new'
        cmd = [sys.executable, str(scripts / script.name), 'init', str(out),
               '--design', 'editorial', '--flow', 'problem', '--title', '<Test & title>']
        result = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        cfg = json.loads((out / 'deck.json').read_text())
        self.assertEqual(cfg['resource_pack'], {'design': 'editorial', 'flow': 'problem'})
        sources = sorted((out / 'src').glob('*.html'))
        self.assertEqual(len(sources), 2)
        text = ''.join(p.read_text() for p in sources)
        self.assertIn('What happened?', text)
        self.assertIn('Try solution', text)
        self.assertIn('&lt;Test &amp; title&gt;', text)
        self.assertNotIn('{{', text)
        # Never overwrite existing work.
        self.assertNotEqual(subprocess.run(cmd, capture_output=True).returncode, 0)
        bad_out = self.root / 'invalid'
        bad = cmd.copy()
        bad[3] = str(bad_out)
        bad[5] = '../editorial'
        self.assertNotEqual(subprocess.run(bad, capture_output=True).returncode, 0)
        self.assertFalse(bad_out.exists())


if __name__ == '__main__':
    unittest.main()
