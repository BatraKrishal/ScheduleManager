import pytest
from app.main import detect_parser
from app.parsers.base import ParserError
from app.parsers.csv_parser import CsvParser
from app.parsers.p6_xml_parser import P6XmlParser
from app.parsers.xer_parser import XerParser

def test_empty_xer():
    parser = XerParser()
    with pytest.raises(ParserError) as exc:
        parser.parse(b"", "empty.xer")
    assert "Empty XER file" in str(exc.value)

def test_invalid_xer_header():
    parser = XerParser()
    with pytest.raises(ParserError) as exc:
        parser.parse(b"This is just some random text", "bad.xer")
    assert "Invalid XER format" in str(exc.value)

def test_corrupt_xml():
    parser = P6XmlParser()
    with pytest.raises(ParserError) as exc:
        parser.parse(b"<UnclosedTag><Project></Project>", "bad.xml")
    assert "Malformed or invalid XML" in str(exc.value)

def test_csv_missing_required_columns():
    parser = CsvParser()
    csv_missing_id = "ColA,ColB,ColC\n1,2,3"
    with pytest.raises(ParserError) as exc:
        parser.parse(csv_missing_id.encode("utf-8"), "missing.csv")
    assert "Unable to map required schedule columns" in str(exc.value)
    assert "Missing required columns" in str(exc.value)

def test_detect_unsupported_format():
    with pytest.raises(ParserError) as exc:
        detect_parser("archive.zip", b"dummy binary content without headers")
    assert "Unsupported or unrecognized schedule file format" in str(exc.value)
