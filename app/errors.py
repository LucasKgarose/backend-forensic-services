class ForensicServiceError(Exception):
    """Base exception for all forensic service errors."""
    def __init__(self, message: str, details: dict | None = None):
        self.message = message
        self.details = details or {}
        super().__init__(message)


class DeviceNotFoundError(ForensicServiceError):
    """Raised when a device serial is not found or not connected."""


class DeviceConnectionError(ForensicServiceError):
    """Raised when ADB connection to a device fails."""


class FileNotFoundOnDeviceError(ForensicServiceError):
    """Raised when a requested file path does not exist on the device."""
    def __init__(self, message: str, file_path: str = "", details: dict | None = None):
        merged = dict(details or {})
        merged.setdefault("file_path", file_path)
        super().__init__(message, merged)
        self.file_path = file_path


class ShellCommandError(ForensicServiceError):
    """Raised when a shell command fails on the device."""
    def __init__(self, message: str, exit_code: int = -1, stderr: str = "", details: dict | None = None):
        merged = dict(details or {})
        merged.setdefault("exit_code", exit_code)
        merged.setdefault("stderr", stderr)
        super().__init__(message, merged)
        self.exit_code = exit_code
        self.stderr = stderr


class APKDowngradeError(ForensicServiceError):
    """Raised when any step of the APK downgrade process fails."""
    def __init__(self, message: str, failed_step: str = "", steps_completed: list[dict] | None = None, details: dict | None = None):
        merged = dict(details or {})
        merged.setdefault("failed_step", failed_step)
        merged.setdefault("steps_completed", steps_completed or [])
        super().__init__(message, merged)
        self.failed_step = failed_step
        self.steps_completed = steps_completed or []


class DecryptionError(ForensicServiceError):
    """Raised when database decryption fails."""


class KeyMismatchError(DecryptionError):
    """Raised when the encryption key does not match the database."""


class CorruptedDatabaseError(DecryptionError):
    """Raised when the encrypted database file is corrupted."""


class NotificationSourceUnavailableError(ForensicServiceError):
    """Raised when the notification scraper database is not found on the device."""


class TamperDetectedError(ForensicServiceError):
    """Raised when evidence hash verification detects tampering."""
    def __init__(self, artifact_id: str, expected_hash: str, actual_hash: str):
        super().__init__(
            f"Tamper detected for artifact {artifact_id}",
            {"expected_hash": expected_hash, "actual_hash": actual_hash},
        )
        self.artifact_id = artifact_id
        self.expected_hash = expected_hash
        self.actual_hash = actual_hash


class CaseNotFoundError(ForensicServiceError):
    """Raised when a case ID does not exist."""


class ReportGenerationError(ForensicServiceError):
    """Raised when PDF report generation fails."""


class ConfigurationError(ForensicServiceError):
    """Raised when required configuration is missing or invalid."""
