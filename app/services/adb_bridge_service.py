import hashlib
import subprocess
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.errors import (
    DeviceNotFoundError,
    FileNotFoundOnDeviceError,
    ShellCommandError,
)
from app.services.legal_lock_service import LegalLockService


@dataclass
class DeviceInfo:
    serial: str
    model: str
    state: str


@dataclass
class ConnectionResult:
    serial: str
    status: str
    message: str


@dataclass
class ConnectionState:
    serial: str
    connected: bool
    investigator_id: str | None = None
    connected_at: datetime | None = None


@dataclass
class FilePullResult:
    remote_path: str
    local_path: str
    evidence_hash: str
    success: bool


@dataclass
class ShellResult:
    output: str
    exit_code: int


class ADBBridgeService:
    """Service for communicating with Android devices via ADB."""

    def __init__(self, db: Session, legal_lock: LegalLockService):
        self.db = db
        self.legal_lock = legal_lock
        self._connections: dict[str, dict] = {}

        from app.config import get_settings
        self._adb_path = get_settings().ADB_PATH

    def _run_adb(self, *args: str, timeout: int = 30) -> subprocess.CompletedProcess:
        """Run an ADB command and return the completed process."""
        cmd = [self._adb_path, *args]
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

    def _require_connection(self, serial: str) -> dict:
        """Raise DeviceNotFoundError if the serial is not in _connections."""
        if serial not in self._connections:
            raise DeviceNotFoundError(
                f"Device {serial} is not connected",
                details={"serial": serial},
            )
        return self._connections[serial]

    def discover_devices(self) -> list[DeviceInfo]:
        """Run `adb devices -l` and parse output to get serial, model, state."""
        result = self._run_adb("devices", "-l")
        devices: list[DeviceInfo] = []
        for line in result.stdout.strip().splitlines()[1:]:
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) < 2:
                continue
            serial = parts[0]
            state = parts[1]
            model = "unknown"
            for part in parts[2:]:
                if part.startswith("model:"):
                    model = part.split(":", 1)[1]
                    break
            devices.append(DeviceInfo(serial=serial, model=model, state=state))
        return devices

    def connect(self, serial: str, investigator_id: str) -> ConnectionResult:
        """Track connection in memory and log chain of custody entry."""
        now = datetime.utcnow()
        self._connections[serial] = {
            "serial": serial,
            "investigator_id": investigator_id,
            "connected_at": now,
        }
        # We need a case_id for custody logging; use serial as artifact_id
        self.legal_lock.log_custody_entry(
            case_id=serial,
            investigator_id=investigator_id,
            action_type="DEVICE_CONNECTED",
            artifact_id=serial,
            evidence_hash="",
        )
        return ConnectionResult(
            serial=serial,
            status="connected",
            message=f"Connected to device {serial}",
        )

    def disconnect(self, serial: str, investigator_id: str) -> bool:
        """Remove from _connections and log chain of custody."""
        self._require_connection(serial)
        del self._connections[serial]
        self.legal_lock.log_custody_entry(
            case_id=serial,
            investigator_id=investigator_id,
            action_type="DEVICE_DISCONNECTED",
            artifact_id=serial,
            evidence_hash="",
        )
        return True

    def get_connection_status(self, serial: str) -> ConnectionState:
        """Check _connections dict for the given serial."""
        if serial in self._connections:
            info = self._connections[serial]
            return ConnectionState(
                serial=serial,
                connected=True,
                investigator_id=info["investigator_id"],
                connected_at=info["connected_at"],
            )
        return ConnectionState(serial=serial, connected=False)

    def pull_file(
        self,
        serial: str,
        remote_path: str,
        local_path: str,
        investigator_id: str,
    ) -> FilePullResult:
        """Pull a file from the device, compute SHA-256, log chain of custody."""
        self._require_connection(serial)
        result = self._run_adb("-s", serial, "pull", remote_path, local_path)
        if result.returncode != 0:
            stderr = result.stderr.strip()
            if "does not exist" in stderr or "No such file" in stderr:
                raise FileNotFoundOnDeviceError(
                    f"File not found on device: {remote_path}",
                    file_path=remote_path,
                )
            raise FileNotFoundOnDeviceError(
                f"Failed to pull file: {remote_path}. {stderr}",
                file_path=remote_path,
            )

        with open(local_path, "rb") as f:
            file_data = f.read()
        evidence_hash = hashlib.sha256(file_data).hexdigest()

        self.legal_lock.log_custody_entry(
            case_id=serial,
            investigator_id=investigator_id,
            action_type="FILE_PULL",
            artifact_id=remote_path,
            evidence_hash=evidence_hash,
        )
        return FilePullResult(
            remote_path=remote_path,
            local_path=local_path,
            evidence_hash=evidence_hash,
            success=True,
        )

    def execute_shell(
        self,
        serial: str,
        command: str,
        investigator_id: str,
    ) -> ShellResult:
        """Execute a shell command on the device, return output and exit code."""
        self._require_connection(serial)
        # Use 'adb -s {serial} shell {command}; echo $?' to capture exit code
        # ADB shell doesn't propagate exit codes, so we append echo $?
        wrapped = f"{command}; echo __EXIT_CODE__$?"
        result = self._run_adb("-s", serial, "shell", wrapped)

        output = result.stdout
        exit_code = 0

        # Parse exit code from the output
        lines = output.rstrip("\n").split("\n")
        if lines and lines[-1].startswith("__EXIT_CODE__"):
            try:
                exit_code = int(lines[-1].replace("__EXIT_CODE__", ""))
            except ValueError:
                exit_code = -1
            output = "\n".join(lines[:-1])

        if exit_code != 0:
            self.legal_lock.log_custody_entry(
                case_id=serial,
                investigator_id=investigator_id,
                action_type="SHELL_COMMAND_FAILED",
                artifact_id=command,
                evidence_hash="",
            )
            raise ShellCommandError(
                f"Shell command failed: {command}",
                exit_code=exit_code,
                stderr=result.stderr.strip() or output,
            )

        self.legal_lock.log_custody_entry(
            case_id=serial,
            investigator_id=investigator_id,
            action_type="SHELL_COMMAND",
            artifact_id=command,
            evidence_hash="",
        )
        return ShellResult(output=output, exit_code=exit_code)
