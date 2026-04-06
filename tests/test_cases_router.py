"""Tests for the Cases router."""

import json
from uuid import uuid4

import pytest

from tests.factories import (
    CaseFactory,
    MessageRecordFactory,
    NotificationRecordFactory,
    ContactRecordFactory,
    MediaReferenceFactory,
    ChainOfCustodyEntryFactory,
)


class TestCreateCase:
    def test_create_case_returns_case_response(self, client):
        resp = client.post("/api/v1/cases/", json={
            "caseNumber": "CASE-0001",
            "investigatorId": "inv-1",
            "deviceIMEI": "123456789012345",
            "osVersion": "Android 13",
            "notes": ["Initial note"],
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["caseNumber"] == "CASE-0001"
        assert body["investigatorId"] == "inv-1"
        assert body["deviceIMEI"] == "123456789012345"
        assert body["osVersion"] == "Android 13"
        assert body["notes"] == ["Initial note"]
        assert isinstance(body["createdAt"], int)
        assert body["dataSources"] == []

    def test_create_case_minimal_fields(self, client):
        resp = client.post("/api/v1/cases/", json={
            "caseNumber": "CASE-0002",
            "investigatorId": "inv-2",
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["caseNumber"] == "CASE-0002"
        assert body["deviceIMEI"] == ""
        assert body["osVersion"] == ""
        assert body["notes"] == []


class TestListCases:
    def test_list_empty(self, client):
        resp = client.get("/api/v1/cases/")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_returns_created_cases(self, client, db_session):
        case = CaseFactory()
        db_session.add(case)
        db_session.commit()

        resp = client.get("/api/v1/cases/")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["caseNumber"] == case.case_number
        assert data[0]["investigatorId"] == case.investigator_id


class TestGetCase:
    def test_get_existing_case(self, client, db_session):
        case = CaseFactory(notes='["note1"]')
        db_session.add(case)
        db_session.commit()

        resp = client.get(f"/api/v1/cases/{case.id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["caseNumber"] == case.case_number
        assert body["notes"] == ["note1"]

    def test_get_nonexistent_case_returns_404(self, client):
        fake_id = str(uuid4())
        resp = client.get(f"/api/v1/cases/{fake_id}")
        assert resp.status_code == 404

    def test_get_case_with_data_sources(self, client, db_session):
        case = CaseFactory()
        db_session.add(case)
        db_session.flush()

        msg = MessageRecordFactory(case_id=case.id)
        notif = NotificationRecordFactory(case_id=case.id)
        db_session.add_all([msg, notif])
        db_session.commit()

        resp = client.get(f"/api/v1/cases/{case.id}")
        assert resp.status_code == 200
        body = resp.json()
        types = [ds["type"] for ds in body["dataSources"]]
        assert "DECRYPTED_DATABASE" in types
        assert "NOTIFICATION_LOG" in types


class TestGetMessages:
    def test_messages_for_case(self, client, db_session):
        case = CaseFactory()
        db_session.add(case)
        db_session.flush()

        msg = MessageRecordFactory(case_id=case.id, sender="Alice", content="Hello")
        db_session.add(msg)
        db_session.commit()

        resp = client.get(f"/api/v1/cases/{case.id}/messages")
        assert resp.status_code == 200
        body = resp.json()
        assert "deviceIMEI" in body
        assert "exportDate" in body
        assert len(body["entries"]) == 1
        assert body["entries"][0]["sender"] == "Alice"

    def test_messages_nonexistent_case(self, client):
        resp = client.get(f"/api/v1/cases/{uuid4()}/messages")
        assert resp.status_code == 404


class TestGetNotifications:
    def test_notifications_for_case(self, client, db_session):
        case = CaseFactory()
        db_session.add(case)
        db_session.flush()

        notif = NotificationRecordFactory(case_id=case.id, sender="Bob")
        db_session.add(notif)
        db_session.commit()

        resp = client.get(f"/api/v1/cases/{case.id}/notifications")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["entries"]) == 1
        assert body["entries"][0]["sender"] == "Bob"
        assert "appPackage" in body["entries"][0]

    def test_notifications_nonexistent_case(self, client):
        resp = client.get(f"/api/v1/cases/{uuid4()}/notifications")
        assert resp.status_code == 404


class TestGetContacts:
    def test_contacts_for_case(self, client, db_session):
        case = CaseFactory()
        db_session.add(case)
        db_session.flush()

        contact = ContactRecordFactory(case_id=case.id, display_name="Charlie")
        db_session.add(contact)
        db_session.commit()

        resp = client.get(f"/api/v1/cases/{case.id}/contacts")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["displayName"] == "Charlie"

    def test_contacts_nonexistent_case(self, client):
        resp = client.get(f"/api/v1/cases/{uuid4()}/contacts")
        assert resp.status_code == 404


class TestGetMediaReferences:
    def test_media_refs_for_case(self, client, db_session):
        case = CaseFactory()
        db_session.add(case)
        db_session.flush()

        ref = MediaReferenceFactory(case_id=case.id, file_name="photo.jpg", media_type="image")
        db_session.add(ref)
        db_session.commit()

        resp = client.get(f"/api/v1/cases/{case.id}/media-references")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["fileName"] == "photo.jpg"
        assert data[0]["mediaType"] == "image"

    def test_media_refs_nonexistent_case(self, client):
        resp = client.get(f"/api/v1/cases/{uuid4()}/media-references")
        assert resp.status_code == 404


class TestGetChainOfCustody:
    def test_chain_of_custody_for_case(self, client, db_session):
        case = CaseFactory()
        db_session.add(case)
        db_session.flush()

        entry = ChainOfCustodyEntryFactory(case_id=case.id, action_type="EXTRACTION")
        db_session.add(entry)
        db_session.commit()

        resp = client.get(f"/api/v1/cases/{case.id}/chain-of-custody")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["actionType"] == "EXTRACTION"
        assert "timestamp" in data[0]
        assert "evidenceHash" in data[0]

    def test_chain_of_custody_nonexistent_case(self, client):
        resp = client.get(f"/api/v1/cases/{uuid4()}/chain-of-custody")
        assert resp.status_code == 404
