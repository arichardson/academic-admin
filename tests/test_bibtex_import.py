import logging
import tempfile
from pathlib import Path

import bibtexparser
from bibtexparser.bparser import BibTexParser

from academic import cli


bibtex_dir = Path(__file__).parent / 'data'

def test_bibtex_import():
    cli.parse_args(['import', '--dry-run', '--bibtex', 'tests/data/article.bib'])


def _process_bibtex(file, expected_count=1):
    parser = BibTexParser(common_strings=True)
    parser.customization = cli.convert_to_unicode
    parser.ignore_nonstandard_types = False
    with Path(bibtex_dir, file).open("r", encoding="utf-8") as bibtex_file:
        bib_database = bibtexparser.load(bibtex_file, parser=parser)
        results = []
        for entry in bib_database.entries:
            results.append(cli.parse_bibtex_entry(entry, dry_run=True))
        assert len(results) == expected_count
        return results

def _test_publication_type(metadata, expected_type: cli.PublicationType):
    assert f'publication_types: ["{expected_type.value}"]' in metadata

def test_bibtex_types():
    _test_publication_type(_process_bibtex('article.bib')[0], cli.PublicationType.JournalArticle)
    _test_publication_type(_process_bibtex('report.bib')[0], cli.PublicationType.Report)
