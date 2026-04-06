"""Tests for FastAPI exception handlers."""

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.api.exception_handlers import (
    EXCEPTION_STATUS_MAP,
    forensic_exception_handler,
    register_exception_handlers,
)
from app.errors import (
    APKDowngradeError,
    CaseNotFoundError,
    ConfigurationError,
    CorruptedDatabaseError,
    DecryptionError,
    DeviceConnectionError,
    DeviceNotFoundError,
    FileNotFoundOnDeviceError,
    ForensicServiceError,
    KeyMismatchError,
    NotificationSourceUnavailableError,
    ReportGenerationError,
    ShellCommandError,
    TamperDetectedError,
)


def _make_app_with_handlers():
    """Create a minimal FastAPI app with exception handlers and test routes."""
    test_app = FastAPI()
    register_exception_handlers(test_app)

    @test_app.get("/raise-base")
    async def raise_base():
        raise ForensicServiceError("base error", {"key": "value"})

    @test_app.get("/raise-case-not-found")
    async def raise_case_not_found():
        raise CaseNotFoundError("Case XYZ not found")

    @test_app.get("/raise-device-not-found")
    async def raise_device_not_found():
        raise DeviceNotFoundError("Device ABC not found")

    @test_app.get("/raise-file-not-found")
    async def raise_file_not_found():
        raise FileNotFoundOnDeviceError("File missing", file_path="/sdcard/test.db")

    @test_app.get("/raise-key-mismatch")
    async def raise_key_mismatch():
        raise KeyMismatchError("Wrong key")

    @test_app.get("/raise-corrupted-db")
    async def raise_corrupted_db():
        raise CorruptedDatabaseError("DB corrupted")

    @test_app.get("/raise-device-connection")
    async def raise_device_connection():
        raise DeviceConnectionError("Connection failed")

    @test_app.get("/raise-shell-command")
    async def raise_shell_command():
        raise ShellCommandError("Command failed", exit_code=1, stderr="error output")

    @test_app.get("/raise-tamper-detected")
    async def raise_tamper_detected():
        raise TamperDetectedError("art-1", "aaa", "bbb")

    @test_app.get("/raise-apk-downgrade")
    async def raise_apk_downgrade():
        raise APKDowngradeError("Downgrade failed", failed_step="install")

    @test_app.get("/raise-decryption")
    async def raise_decryption():
        raise DecryptionError("Decryption failed")

    @test_app.get("/raise-report-generation")
    async def raise_report_generation():
        raise ReportGenerationError("Report failed")

    @test_app.get("/raise-configuration")
    async def raise_configuration():
        raise ConfigurationError("Missing DATABASE_URL")

    @test_app.get("/raise-notification-unavailable")
    async def raise_notification_unavailable():
        raise NotificationSourceUnavailableError("No notification DB")

    return test_app


@pytest.fixture
def test_client():
    return TestClient(_make_app_with_handlers())


class TestExceptionStatusMap:
    def test_all_domain_exceptions_are_mapped(self):
        expected_exceptions = {
            CaseNotFoundError, DeviceNotFoundError, FileNotFoundOnDeviceError,
            NotificationSourceUnavailableError, KeyMismatchError, CorruptedDatabaseError,
            DeviceConnectionError, ShellCommandError, APKDowngradeError, DecryptionError,
            TamperDetectedError, ReportGenerationError, ConfigurationError,
            ForensicServiceError,
        }
        assert set(EXCEPTION_STATUS_MAP.keys()) == expected_exceptions

    def test_404_exceptions(self):
        assert EXCEPTION_STATUS_MAP[CaseNotFoundError] == 404
        assert EXCEPTION_STATUS_MAP[DeviceNotFoundError] == 404
        assert EXCEPTION_STATUS_MAP[FileNotFoundOnDeviceError] == 404
        assert EXCEPTION_STATUS_MAP[NotificationSourceUnavailableError] == 404

    def test_400_exceptions(self):
        assert EXCEPTION_STATUS_MAP[KeyMismatchError] == 400
        assert EXCEPTION_STATUS_MAP[CorruptedDatabaseError] == 400

    def test_502_exceptions(self):
        assert EXCEPTION_STATUS_MAP[DeviceConnectionError] == 502
        assert EXCEPTION_STATUS_MAP[ShellCommandError] == 502

    def test_409_exceptions(self):
        assert EXCEPTION_STATUS_MAP[TamperDetectedError] == 409

    def test_500_exceptions(self):
        assert EXCEPTION_STATUS_MAP[APKDowngradeError] == 500
        assert EXCEPTION_STATUS_MAP[DecryptionError] == 500
        assert EXCEPTION_STATUS_MAP[ReportGenerationError] == 500
        assert EXCEPTION_STATUS_MAP[ConfigurationError] == 500
        assert EXCEPTION_STATUS_MAP[ForensicServiceError] == 500


class TestForensicExceptionHandler:
    def test_base_error_returns_500(self, test_client):
        resp = test_client.get("/raise-base")
        assert resp.status_code == 500
        body = resp.json()
        assert body["detail"] == "base error"
        assert body["error_type"] == "ForensicServiceError"
        assert body["details"] == {"key": "value"}

    def test_case_not_found_returns_404(self, test_client):
        resp = test_client.get("/raise-case-not-found")
        assert resp.status_code == 404
        assert resp.json()["error_type"] == "CaseNotFoundError"

    def test_device_not_found_returns_404(self, test_client):
        resp = test_client.get("/raise-device-not-found")
        assert resp.status_code == 404
        assert resp.json()["error_type"] == "DeviceNotFoundError"

    def test_file_not_found_returns_404_with_path(self, test_client):
        resp = test_client.get("/raise-file-not-found")
        assert resp.status_code == 404
        body = resp.json()
        assert body["error_type"] == "FileNotFoundOnDeviceError"
        assert body["details"]["file_path"] == "/sdcard/test.db"

    def test_key_mismatch_returns_400(self, test_client):
        resp = test_client.get("/raise-key-mismatch")
        assert resp.status_code == 400
        assert resp.json()["error_type"] == "KeyMismatchError"

    def test_corrupted_db_returns_400(self, test_client):
        resp = test_client.get("/raise-corrupted-db")
        assert resp.status_code == 400
        assert resp.json()["error_type"] == "CorruptedDatabaseError"

    def test_device_connection_returns_502(self, test_client):
        resp = test_client.get("/raise-device-connection")
        assert resp.status_code == 502

    def test_shell_command_returns_502(self, test_client):
        resp = test_client.get("/raise-shell-command")
        assert resp.status_code == 502
        body = resp.json()
        assert body["details"]["exit_code"] == 1
        assert body["details"]["stderr"] == "error output"

    def test_tamper_detected_returns_409(self, test_client):
        resp = test_client.get("/raise-tamper-detected")
        assert resp.status_code == 409
        body = resp.json()
        assert body["details"]["expected_hash"] == "aaa"
        assert body["details"]["actual_hash"] == "bbb"

    def test_apk_downgrade_returns_500(self, test_client):
        resp = test_client.get("/raise-apk-downgrade")
        assert resp.status_code == 500
        assert resp.json()["details"]["failed_step"] == "install"

    def test_decryption_returns_500(self, test_client):
        resp = test_client.get("/raise-decryption")
        assert resp.status_code == 500

    def test_report_generation_returns_500(self, test_client):
        resp = test_client.get("/raise-report-generation")
        assert resp.status_code == 500

    def test_configuration_returns_500(self, test_client):
        resp = test_client.get("/raise-configuration")
        assert resp.status_code == 500

    def test_notification_unavailable_returns_404(self, test_client):
        resp = test_client.get("/raise-notification-unavailable")
        assert resp.status_code == 404


class TestRegisterExceptionHandlers:
    def test_registers_handler_on_app(self):
        test_app = FastAPI()
        register_exception_handlers(test_app)
        # Verify the handler is registered by checking exception_handlers dict
        assert ForensicServiceError in test_app.exception_handlers
