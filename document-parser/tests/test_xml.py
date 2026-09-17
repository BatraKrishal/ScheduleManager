import pytest
from app.models.canonical import ActivityStatus, RelationshipType
from app.parsers.p6_xml_parser import P6XmlParser

SAMPLE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<APM xmlns="http://xmlns.oracle.com/Primavera/P6/V19.12/API/BusinessObjects">
    <Project>
        <ObjectId>100</ObjectId>
        <Id>EXP-2024</Id>
        <Name>Facility Expansion</Name>
        <PlannedStartDate>2024-03-01T08:00:00</PlannedStartDate>
        <PlannedFinishDate>2024-11-30T17:00:00</PlannedFinishDate>
    </Project>
    <WBS>
        <ObjectId>200</ObjectId>
        <Code>WBS-ENG</Code>
        <Name>Engineering Phase</Name>
    </WBS>
    <Activity>
        <ObjectId>301</ObjectId>
        <Id>ACT-101</Id>
        <Name>Design Review</Name>
        <WBSObjectId>200</WBSObjectId>
        <Status>Completed</Status>
        <PlannedDuration>40.0</PlannedDuration>
        <PercentComplete>100</PercentComplete>
    </Activity>
    <Activity>
        <ObjectId>302</ObjectId>
        <Id>ACT-102</Id>
        <Name>Procurement Spec</Name>
        <WBSObjectId>200</WBSObjectId>
        <Status>In Progress</Status>
        <PlannedDuration>80.0</PlannedDuration>
        <PercentComplete>50</PercentComplete>
    </Activity>
    <Relationship>
        <ObjectId>401</ObjectId>
        <PredecessorActivityObjectId>301</PredecessorActivityObjectId>
        <SuccessorActivityObjectId>302</SuccessorActivityObjectId>
        <Type>Finish to Start</Type>
        <Lag>0</Lag>
    </Relationship>
</APM>
"""

def test_parse_valid_xml():
    parser = P6XmlParser()
    result = parser.parse(SAMPLE_XML.encode("utf-8"), "project.xml")

    assert result.project.project_code == "EXP-2024"
    assert result.project.name == "Facility Expansion"
    assert len(result.wbs) == 1
    assert result.wbs[0].code == "WBS-ENG"

    assert len(result.activities) == 2
    assert result.activities[0].activity_code == "ACT-101"
    assert result.activities[0].status == ActivityStatus.COMPLETED
    assert result.activities[0].wbs_code == "WBS-ENG"

    assert result.activities[1].activity_code == "ACT-102"
    assert result.activities[1].status == ActivityStatus.IN_PROGRESS

    assert len(result.relationships) == 1
    rel = result.relationships[0]
    assert rel.predecessor_code == "ACT-101"
    assert rel.successor_code == "ACT-102"
    assert rel.relationship_type == RelationshipType.FS
