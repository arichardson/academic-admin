from pathlib import Path

import bibtexparser
from bibtexparser.bparser import BibTexParser

from academic import cli

bibtex_dir = Path(__file__).parent / 'data'

def test_bibtex_import():
    cli.parse_args(['import', '--dry-run', '--bibtex', 'tests/data/article.bib'])


def _process_bibtex(file, expected_count=1, return_str=False, normalize=False):
    parser = BibTexParser(common_strings=True)
    parser.customization = cli.convert_to_unicode
    parser.ignore_nonstandard_types = False
    with Path(bibtex_dir, file).open("r", encoding="utf-8") as bibtex_file:
        bib_database = bibtexparser.load(bibtex_file, parser=parser)
        results = []
        for entry in bib_database.entries:
            metadata, strval = cli.parse_bibtex_entry(entry, dry_run=True, normalize=normalize)
            if return_str:
                results.append(strval)
            else:
                results.append(metadata)
        assert len(results) == expected_count
        return results

def _test_publication_type(metadata, expected_type: cli.PublicationType):
    assert metadata['publication_types'] == [str(expected_type.value)]

def test_bibtex_types():
    _test_publication_type(_process_bibtex('article.bib')[0], cli.PublicationType.JournalArticle)
    for metadata in _process_bibtex('report.bib', expected_count=3):
        _test_publication_type(metadata, cli.PublicationType.Report)
    for metadata in _process_bibtex('thesis.bib', expected_count=3):
        _test_publication_type(metadata, cli.PublicationType.Thesis)
    _test_publication_type(_process_bibtex('book.bib')[0], cli.PublicationType.Book)


def test_long_abstract():
    lines = _process_bibtex('book.bib', return_str=True, normalize=True)[0].split("\n")
    # Don't check the full string publishDate since that is not constant.
    assert lines[3].startswith('publishDate = "')
    del lines[3]
    assert lines == [
        '+++',
        'title = "The title of the book"',
        'date = "2019-01-01"',
        'authors = [ "Nelson Bigetti",]',
        'publication_types = [ "5",]',
        'abstract = "Paragraph one.\\n\\nParagraph two.\\n\\nParagraph three."',
        'featured = "false"',
        'publication = ""',
        'tags = [ "Tag1", "Tag with spaces", "Mixedcase",]',
        '+++', '', '']
