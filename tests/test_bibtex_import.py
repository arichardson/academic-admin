import typing
from io import StringIO
from pathlib import Path

import bibtexparser
from bibtexparser.bparser import BibTexParser

from academic import cli, import_bibtex
from academic.editFM import EditableFM

bibtex_dir = Path(__file__).parent / "data"


def test_bibtex_import():
    cli.parse_args(["import", "--dry-run", "--bibtex", "tests/data/article.bib"])


def _process_bibtex(file, expected_count=1, normalize=False) -> "typing.List[EditableFM]":
    """
    Parse a BibTeX .bib file and return the parsed metadata
    :param file: The .bib file to parse
    :param expected_count: The expected number of entries inside the .bib
    :param normalize: Whether to normalize the case of tags
    :return: The parsed metadata as a list of EditableFM
    """
    parser = BibTexParser(common_strings=True)
    parser.customization = import_bibtex.convert_to_unicode
    parser.ignore_nonstandard_types = False
    with Path(bibtex_dir, file).open("r", encoding="utf-8") as bibtex_file:
        bib_database = bibtexparser.load(bibtex_file, parser=parser)
        results = []
        for entry in bib_database.entries:
            results.append(import_bibtex.parse_bibtex_entry(entry, dry_run=True, normalize=normalize))
        assert len(results) == expected_count
        return results


def _test_publication_type(metadata: EditableFM, expected_type: import_bibtex.PublicationType):
    """
    Check that the publication_types field of the parsed metadata is set to the expected type.
    """
    assert metadata.fm["publication_types"] == [str(expected_type.value)]


def test_bibtex_types():
    """
    This test uses the import_bibtex functions to parse a .bib file and checks that the
    resulting metadata has the correct publication type set.
    """
    _test_publication_type(_process_bibtex("article.bib")[0], import_bibtex.PublicationType.JournalArticle)
    for metadata in _process_bibtex("report.bib", expected_count=3):
        _test_publication_type(metadata, import_bibtex.PublicationType.Report)
    for metadata in _process_bibtex("thesis.bib", expected_count=3):
        _test_publication_type(metadata, import_bibtex.PublicationType.Thesis)
    _test_publication_type(_process_bibtex("book.bib")[0], import_bibtex.PublicationType.Book)


def test_resulting_yaml_output():
    """
    This test checks that the YAML generated for a .bib file looks as expected and that newlines are not filtered out.
    """
    result = _process_bibtex("book.bib", normalize=True)[0]

    # Check that the paragraph breaks were not stripped from the YAML:
    assert result.fm["abstract"] == "Paragraph one.\n\nParagraph two.\n\nParagraph three."
    assert result.fm["authors"] == ["Nelson Bigetti", "Firstname von Book-Author, Jr.", "Someone Else"]
    assert result.fm["featured"] is True

    # Don't check the full string for publishDate since that is not constant.
    del result.fm["publishDate"]

    with StringIO() as output:
        result.write_to_file(output)
        output.seek(0)
        lines = output.readlines()

    lines = [line.strip() for line in lines]  # .strip() to remove newline at end
    assert lines == [
        "---",
        "title: The title of the book",
        "date: '2019-01-01'",
        "authors:",
        "- Nelson Bigetti",
        "- Firstname von Book-Author, Jr.",
        "- Someone Else",
        "publication_types:",
        "- '5'",
        'abstract: "Paragraph one.\\n\\nParagraph two.\\n\\nParagraph three."',
        "featured: true",
        "publication: ''",
        "tags:",
        "- Tag1",
        "- Tag with spaces",
        "- Mixedcase",
        "---",
    ]
