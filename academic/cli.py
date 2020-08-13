#!/usr/bin/env python3

import argparse
import calendar
import logging
import os
import re
import subprocess
import sys
from argparse import RawTextHelpFormatter
from datetime import datetime
from enum import Enum
from pathlib import Path

import bibtexparser
import toml
from bibtexparser.bibdatabase import BibDatabase
from bibtexparser.bparser import BibTexParser
from bibtexparser.bwriter import BibTexWriter
from bibtexparser.customization import convert_to_unicode

from academic import __version__ as version
from academic.import_assets import import_assets


# Map BibTeX to Academic publication types.

class PublicationType(Enum):
    Uncategorized = 0,
    ConferencePaper = 1
    JournalArticle = 2
    Preprint = 3
    Report = 4
    Book = 5
    BookSection = 6
    Thesis = 7  # (v4.2+ required)
    Patent = 8  # (v4.2+ required)

PUB_TYPES = {
    "article": PublicationType.JournalArticle,
    "book": PublicationType.Book,
    "conference": PublicationType.ConferencePaper,
    "inbook": PublicationType.BookSection,
    "incollection": PublicationType.BookSection,
    "inproceedings": PublicationType.ConferencePaper,
    "manual": PublicationType.Report,
    "mastersthesis": PublicationType.Thesis,
    "misc": PublicationType.Uncategorized,
    "patent": PublicationType.Patent,
    "phdthesis": PublicationType.Thesis,
    "proceedings": PublicationType.Uncategorized,
    "report": PublicationType.Report,
    "thesis": PublicationType.Thesis,
    "techreport": PublicationType.Report,
    "unpublished": PublicationType.Preprint,
}

# Initialise logger.
logging.basicConfig(format="%(asctime)s %(levelname)s: %(message)s", level=logging.WARNING, datefmt="%I:%M:%S%p")
log = logging.getLogger(__name__)


class AcademicError(Exception):
    pass


def main():
    parse_args(sys.argv[1:])  # Strip command name, leave just args.


def parse_args(args):
    """Parse command-line arguments"""

    # Initialise command parser.
    parser = argparse.ArgumentParser(
        description=f"Academic Admin Tool v{version}\nhttps://sourcethemes.com/academic/", formatter_class=RawTextHelpFormatter
    )
    subparsers = parser.add_subparsers(help="Sub-commands", dest="command")

    # Sub-parser for import command.
    parser_a = subparsers.add_parser("import", help="Import data into Academic")
    parser_a.add_argument("--assets", action="store_true", help="Import third-party JS and CSS for generating an offline site")
    parser_a.add_argument("--bibtex", required=False, type=str, help="File path to your BibTeX file")
    parser_a.add_argument(
        "--publication-dir",
        required=False,
        type=str,
        default="publication",
        help="Directory that your publications are stored in (default `publication`)",
    )
    parser_a.add_argument("--featured", action="store_true", help="Flag publications as featured")
    parser_a.add_argument("--overwrite", action="store_true", help="Overwrite existing publications")
    parser_a.add_argument("--normalize", action="store_true", help="Normalize each keyword to lowercase with uppercase first letter")
    parser_a.add_argument("-v", "--verbose", action="store_true", required=False, help="Verbose mode")
    parser_a.add_argument("-dr", "--dry-run", action="store_true", required=False, help="Perform a dry run (Bibtex only)")

    known_args, unknown = parser.parse_known_args(args)

    # If no arguments, show help.
    if len(args) == 0:
        parser.print_help()
        parser.exit()

    # If no known arguments, wrap Hugo command.
    elif known_args is None and unknown:
        cmd = []
        cmd.append("hugo")
        if args:
            cmd.append(args)
        subprocess.call(cmd)
    else:
        # The command has been recognised, proceed to parse it.
        if known_args.command and known_args.verbose:
            # Set logging level to debug if verbose mode activated.
            logging.getLogger().setLevel(logging.DEBUG)
        if known_args.command and known_args.assets:
            # Run command to import assets.
            import_assets()
        elif known_args.command and known_args.bibtex:
            # Run command to import bibtex.
            import_bibtex(
                known_args.bibtex,
                pub_dir=known_args.publication_dir,
                featured=known_args.featured,
                overwrite=known_args.overwrite,
                normalize=known_args.normalize,
                dry_run=known_args.dry_run,
            )


def import_bibtex(bibtex, pub_dir="publication", featured=False, overwrite=False, normalize=False, dry_run=False):
    """Import publications from BibTeX file"""

    # Check BibTeX file exists.
    if not Path(bibtex).is_file():
        err = "Please check the path to your BibTeX file and re-run"
        log.error(err)
        raise AcademicError(err)

    # Load BibTeX file for parsing.
    with open(bibtex, "r", encoding="utf-8") as bibtex_file:
        parser = BibTexParser(common_strings=True)
        parser.customization = convert_to_unicode
        parser.ignore_nonstandard_types = False
        bib_database = bibtexparser.load(bibtex_file, parser=parser)
        for entry in bib_database.entries:
            parse_bibtex_entry(entry, pub_dir=pub_dir, featured=featured, overwrite=overwrite, normalize=normalize, dry_run=dry_run)


def parse_bibtex_entry(entry, pub_dir="publication", featured=False, overwrite=False, normalize=False, dry_run=False):
    """Parse a bibtex entry and generate corresponding publication bundle"""
    log.info(f"Parsing entry {entry['ID']}")

    bundle_path = f"content/{pub_dir}/{slugify(entry['ID'])}"
    markdown_path = os.path.join(bundle_path, "index.md")
    cite_path = os.path.join(bundle_path, "cite.bib")
    date = datetime.utcnow()
    timestamp = date.isoformat("T") + "Z"  # RFC 3339 timestamp.

    # Do not overwrite publication bundle if it already exists.
    if not overwrite and os.path.isdir(bundle_path):
        log.warning(f"Skipping creation of {bundle_path} as it already exists. " f"To overwrite, add the `--overwrite` argument.")
        return

    # Create bundle dir.
    log.info(f"Creating folder {bundle_path}")
    if not dry_run:
        Path(bundle_path).mkdir(parents=True, exist_ok=True)

    # Save citation file.
    log.info(f"Saving citation to {cite_path}")
    db = BibDatabase()
    db.entries = [entry]
    writer = BibTexWriter()
    if not dry_run:
        with open(cite_path, "w", encoding="utf-8") as f:
            f.write(writer.write(db))

    # Prepare TOML front matter for Markdown file.
    year = ""
    month = "01"
    day = "01"
    if "date" in entry:
        dateparts = entry["date"].split("-")
        if len(dateparts) == 3:
            year, month, day = dateparts[0], dateparts[1], dateparts[2]
        elif len(dateparts) == 2:
            year, month = dateparts[0], dateparts[1]
        elif len(dateparts) == 1:
            year = dateparts[0]
    if "month" in entry and month == "01":
        month = month2number(entry["month"])
    if "year" in entry and year == "":
        year = entry["year"]
    if len(year) == 0:
        log.error(f'Invalid date for entry `{entry["ID"]}`.')

    metadata = {
        'title': entry['title'],
        'date': f'{year}-{month}-{day}',
        'publishDate': str(timestamp)
        }

    authors = None
    if "author" in entry:
        authors = entry["author"]
    elif "editor" in entry:
        authors = entry["editor"]
    if authors:
        metadata['authors'] = clean_bibtex_authors(authors)

    pubtype = PUB_TYPES.get(entry["ENTRYTYPE"], PublicationType.Uncategorized)
    metadata['publication_types'] = [str(pubtype.value)]

    if "abstract" in entry:
        metadata['abstract'] = entry["abstract"]
    else:
        metadata['abstract'] = ''

    featured_from_bibtex = featured
    if 'options' in entry:
        try:
            options = entry['options'].split(',')
            for option in options:
                assert isinstance(option, str)
                if "=" in option:
                    k, v = option.split("=", )
                    if k.strip() == "featured":
                        featured_from_bibtex = bool(v.strip())
                        break
                elif option.strip() == "featured":
                    featured_from_bibtex = True
                    break
        except Exception as e:
            log.warning("Could not parse options field: " + option, exc_info=e)

    metadata['featured'] = featured_from_bibtex

    # Publication name.
    if "booktitle" in entry:
        metadata['publication'] = f'*{entry["booktitle"]}*'
    elif "journal" in entry:
        metadata['publication'] = f'*{entry["journal"]}*'
    elif "publisher" in entry:
        metadata['publication'] = f'*{entry["publisher"]}*'
    elif "institution" in entry:
        metadata['publication'] = f'*{entry["institution"]}*'
    else:
        metadata['publication'] = ''

    if "keywords" in entry:
        metadata['tags'] = clean_bibtex_tags(entry['keywords'], normalize)

    if "url" in entry:
        metadata['url_pdf'] = entry['url']

    if "doi" in entry:
        metadata['doi'] = entry['doi']

    frontmatter = '+++\n'
    frontmatter += toml.dumps(metadata)
    frontmatter += '+++\n\n'

    # Save Markdown file.
    try:
        log.info(f"Saving Markdown to '{markdown_path}'")
        if not dry_run:
            with open(markdown_path, "w", encoding="utf-8") as f:
                f.write(frontmatter)
    except IOError:
        log.error("Could not save file.")

    return metadata, frontmatter


def slugify(s, lower=True):
    bad_symbols = (".", "_", ":")  # Symbols to replace with hyphen delimiter.
    delimiter = "-"
    good_symbols = (delimiter,)  # Symbols to keep.
    for r in bad_symbols:
        s = s.replace(r, delimiter)

    s = re.sub(r"(\D+)(\d+)", r"\1\-\2", s)  # Delimit non-number, number.
    s = re.sub(r"(\d+)(\D+)", r"\1\-\2", s)  # Delimit number, non-number.
    s = re.sub(r"((?<=[a-z])[A-Z]|(?<!\A)[A-Z](?=[a-z]))", r"\-\1", s)  # Delimit camelcase.
    s = "".join(c for c in s if c.isalnum() or c in good_symbols).strip()  # Strip non-alphanumeric and non-hyphen.
    s = re.sub("-{2,}", "-", s)  # Remove consecutive hyphens.

    if lower:
        s = s.lower()
    return s


def clean_bibtex_authors(author_str):
    """Convert author names to `firstname(s) lastname` format."""
    authors = []
    for author in author_str.replace('\n', ' ').split(" and "):
        name_parts = bibtexparser.customization.splitname(author)
        fullname = ' '.join(name_parts['first'] + name_parts['von'] + name_parts['last'])
        if name_parts['jr']:
            fullname += ', ' + ' '.join(name_parts['jr'])
        authors.append(fullname)
    return authors


def clean_bibtex_tags(s, normalize=False):
    """Clean BibTeX keywords and convert to TOML tags"""
    tags = [tag.strip() for tag in s.split(",")]
    if normalize:
        tags = [tag.lower().capitalize() for tag in tags]
    return tags


def month2number(month):
    """Convert BibTeX or BibLateX month to numeric"""
    if len(month) <= 2:  # Assume a 1 or 2 digit numeric month has been given.
        return month.zfill(2)
    else:  # Assume a textual month has been given.
        month_abbr = month.strip()[:3].title()
        try:
            return str(list(calendar.month_abbr).index(month_abbr)).zfill(2)
        except ValueError:
            raise log.error("Please update the entry with a valid month.")


if __name__ == "__main__":
    main()
