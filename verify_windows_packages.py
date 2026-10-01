"""Controleer productie-inhoud zonder de app of gebruikersgegevens te openen."""
import ast
from pathlib import Path


def verify(root=Path('.')):
    for name in ('EventHub', 'EventHub Server'):
        analysis = ast.literal_eval((root / 'build' / name / 'Analysis-00.toc').read_text(encoding='utf-8'))
        # Analysis bevat geneste TOC-lijsten; controleer de werkelijke modules,
        # niet de lijst met bewust uitgesloten modules.
        def modules(value):
            if isinstance(value, (list, tuple)):
                if len(value) == 3 and value[-1] in ('PYMODULE', 'PYSOURCE'):
                    yield value[0]
                else:
                    for item in value:
                        yield from modules(item)
        included = set(modules(analysis))
        assert not any(m == 'server.tests' or m.startswith('server.tests.') for m in included), name
        if name == 'EventHub':
            assert 'emt_updater' in included, 'EventHub: updater ontbreekt in het desktop-pakket'
        bundle = root / 'dist' / name
        assert (bundle / (name + '.exe')).is_file(), name
        engine = list(bundle.rglob('Qt6WebEngineCore.dll'))
        assert bool(engine) == (name == 'EventHub'), f'{name}: onverwachte WebEngine-inhoud'
        assert (bundle / '_internal/server/web/templates').is_dir(), name
        assert (bundle / '_internal/server/web/static').is_dir(), name
        # Windows levert de Universal CRT zelf. Een oude kopie uit een andere
        # tool op de bouwmachine kan Qt al vóór het startvenster laten crashen.
        assert not (bundle / '_internal/ucrtbase.dll').exists(), f'{name}: onverwachte externe Windows-runtime'
        files = [p for p in bundle.rglob('*') if p.is_file()]
        print(f'{name}: {len(files)} bestanden, {sum(p.stat().st_size for p in files) / 1024**2:.1f} MiB; controles geslaagd')


if __name__ == '__main__':
    verify()
