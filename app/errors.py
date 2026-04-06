class ForensicServiceError(Exception):
    pass

class DeviceNotFoundError(ForensicServiceError):
    pass

class DeviceConnectionError(ForensicServiceError):
    pass

class FileNotFoundOnDeviceError(ForensicServiceError):
    pass

class ShellCommandError(ForensicServiceError):
    pass

class APKDowngradeError(ForensicServiceError):
    pass

class DecryptionError(ForensicServiceError):
    pass

class KeyMismatchError(ForensicServiceError):
    pass

class CorruptedDatabaseError(ForensicServiceError):
    pass

class NotificationSourceUnavailableError(ForensicServiceError):
    pass

class TamperDetectedError(ForensicServiceError):
    pass

class CaseNotFoundError(ForensicServiceError):
    pass

class ReportGenerationError(ForensicServiceError):
    pass

class ConfigurationError(ForensicServiceError):
    pass
