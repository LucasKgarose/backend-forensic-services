# Requirements Document

## Introduction

Phase 2 of the Investigators Dashboard project delivers a standalone Python + FastAPI backend that provides real forensic investigation services to replace the mock JSON data used in Phase 1. The backend connects to Android devices via ADB, manipulates WhatsApp APK versions to extract encryption keys, decrypts WhatsApp encrypted databases, generates court-admissible PDF reports, enforces evidence integrity through cryptographic hashing and chain of custody, and recovers deleted media files. The backend exposes a REST API consumed by the Phase 1 React.js frontend.

## Glossary

- **Backend**: The Python FastAPI application providing forensic investigation REST API endpoints.
- **ADB_Bridge**: The service responsible for communicating with Android devices via Android Debug Bridge (ADB) protocol.
- **Device**: A connected Android phone or tablet identified by a unique serial number.
- **Device_Connection**: An active ADB session between the Backend and a Device.
- **APK_Downgrade_Service**: The service that manipulates WhatsApp APK versions on a Device to enable encryption key extraction.
- **Encryption_Key**: The cryptographic key extracted from an older WhatsApp version, required to decrypt WhatsApp database files.
- **Decryption_Service**: The service that decrypts WhatsApp crypt14/crypt15 database files using an extracted Encryption_Key.
- **Encrypted_Database**: A WhatsApp msgstore.db.crypt14 or msgstore.db.crypt15 file stored on the Device.
- **Decrypted_Database**: The resulting SQLite database after successful decryption of an Encrypted_Database.
- **Message_Record**: A single parsed message row from the Decrypted_Database, including sender, content, timestamps, and status metadata.
- **Contact_Record**: A parsed contact entry from the Decrypted_Database, including phone number and display name.
- **Media_Reference**: A reference to a media file (image, video, audio, document) associated with a Message_Record.
- **Report_Generator**: The service that produces PDF forensic reports from case data.
- **Forensic_Report**: A court-admissible PDF document containing evidence timelines, gap analysis, heatmap visualizations, chain of custody logs, and case metadata.
- **Legal_Lock_Service**: The service that enforces evidence integrity through cryptographic hashing, chain of custody, tamper detection, and digital signatures.
- **Evidence_Hash**: A SHA-256 cryptographic digest computed over an evidence artifact to verify data integrity.
- **Chain_of_Custody_Entry**: An immutable log record documenting an evidence handling action, including timestamp, actor, action, and artifact identifier.
- **Digital_Signature**: A cryptographic signature applied to an evidence artifact or report to prove authenticity and non-repudiation.
- **Tamper_Detection**: The process of comparing a stored Evidence_Hash against a recomputed hash to detect unauthorized modification.
- **Media_Recovery_Service**: The service that recovers deleted media files from WhatsApp media storage on the Device.
- **Recovered_Media**: A media file (image, video, audio, or document) recovered from the Device that may or may not still be referenced by a Message_Record.
- **Case**: An investigation case that groups all evidence artifacts, device connections, reports, and chain of custody entries.
- **Investigator**: A PI company employee who uses the system to conduct forensic investigations.
- **APK_Backup**: A saved copy of the current WhatsApp APK on the Device before downgrade.
- **Notification_Log_Service**: The service that extracts Android notification log data from a Device, capturing WhatsApp notifications that persist even after messages are deleted from the app.
- **Notification_Log**: A structured dataset of captured Android notifications for WhatsApp, including sender, content, and timestamp — used as the second evidence source for gap detection.
- **Notification_Record**: A single parsed notification entry from the Notification_Log, including sender, content, timestamp, and app package.

## Requirements

### Requirement 1: Device Discovery and Connection Management

**User Story:** As an Investigator, I want to discover and connect to Android devices via ADB, so that I can access device data for forensic investigation.

#### Acceptance Criteria

1. WHEN an Investigator requests device discovery, THE ADB_Bridge SHALL scan for connected Android devices and return a list of Device serial numbers, model names, and connection states.
2. WHEN an Investigator requests a connection to a Device by serial number, THE ADB_Bridge SHALL establish a Device_Connection and return the connection status.
3. WHILE a Device_Connection is active, THE ADB_Bridge SHALL maintain the connection and report the Device as connected in subsequent discovery requests.
4. WHEN an Investigator requests disconnection from a Device, THE ADB_Bridge SHALL terminate the Device_Connection and confirm the disconnection.
5. IF a Device becomes physically disconnected during an active Device_Connection, THEN THE ADB_Bridge SHALL detect the disconnection within 10 seconds and update the Device connection state to disconnected.
6. WHEN a Device_Connection is established, THE ADB_Bridge SHALL log a Chain_of_Custody_Entry recording the Device serial number, connection timestamp, and Investigator identifier.

### Requirement 2: ADB File Operations

**User Story:** As an Investigator, I want to pull files from a connected Android device and execute shell commands, so that I can extract forensic artifacts.

#### Acceptance Criteria

1. WHILE a Device_Connection is active, THE ADB_Bridge SHALL allow the Investigator to pull a file from a specified path on the Device to a local destination path.
2. WHEN a file is successfully pulled from the Device, THE ADB_Bridge SHALL compute and return the SHA-256 Evidence_Hash of the pulled file.
3. WHILE a Device_Connection is active, THE ADB_Bridge SHALL allow the Investigator to execute a shell command on the Device and return the command output.
4. IF a requested file path does not exist on the Device, THEN THE ADB_Bridge SHALL return an error response identifying the missing path.
5. IF a shell command fails on the Device, THEN THE ADB_Bridge SHALL return the error output and a non-zero exit code.
6. WHEN a file pull or shell command is executed, THE ADB_Bridge SHALL log a Chain_of_Custody_Entry recording the operation type, file path or command, timestamp, and Investigator identifier.

### Requirement 3: Notification Log Extraction

**User Story:** As an Investigator, I want to extract the Android notification log from a connected device, so that I can capture WhatsApp messages that may have been deleted from the app — enabling evidence gap detection when cross-referenced with the decrypted database.

#### Acceptance Criteria

1. WHILE a Device_Connection is active, THE Notification_Log_Service SHALL locate and pull the notification scraper database or notification listener storage from the Device.
2. WHEN the notification data is pulled, THE Notification_Log_Service SHALL parse it and extract Notification_Records including sender, content, timestamp, and app package (filtering for WhatsApp notifications: com.whatsapp).
3. THE Notification_Log_Service SHALL return Notification_Records in the same JSON structure as the Phase 1 Notification_Log mock format (deviceIMEI, exportDate, entries array).
4. WHEN notification extraction succeeds, THE Notification_Log_Service SHALL compute and store the SHA-256 Evidence_Hash of the raw notification data file.
5. WHEN notification extraction is performed, THE Notification_Log_Service SHALL log a Chain_of_Custody_Entry recording the extraction operation, Device serial number, record count, and timestamp.
6. IF the notification scraper database is not found on the Device, THEN THE Notification_Log_Service SHALL return an error indicating the notification source is unavailable and suggest installing a notification logging app.
7. IF the notification data is corrupted or unreadable, THEN THE Notification_Log_Service SHALL return an error describing the issue.
8. THE Notification_Log_Service SHALL persist extracted Notification_Records associated with their parent Case.

### Requirement 4: WhatsApp APK Downgrade for Key Extraction

**User Story:** As an Investigator, I want to downgrade the WhatsApp APK on a connected device to an older version, so that I can extract the encryption key needed for database decryption.

#### Acceptance Criteria

1. WHEN an Investigator initiates an APK downgrade, THE APK_Downgrade_Service SHALL create an APK_Backup of the currently installed WhatsApp version on the Device.
2. WHEN the APK_Backup is complete, THE APK_Downgrade_Service SHALL install a specified older WhatsApp APK version on the Device that permits Encryption_Key extraction.
3. WHEN the older WhatsApp version is installed, THE APK_Downgrade_Service SHALL extract the Encryption_Key from the Device and store it securely associated with the Case.
4. WHEN the Encryption_Key has been extracted, THE APK_Downgrade_Service SHALL restore the original WhatsApp APK from the APK_Backup on the Device.
5. IF the APK_Backup fails, THEN THE APK_Downgrade_Service SHALL abort the downgrade process and return an error without modifying the Device.
6. IF the older APK installation fails, THEN THE APK_Downgrade_Service SHALL restore the original WhatsApp APK from the APK_Backup and return an error.
7. IF the Encryption_Key extraction fails, THEN THE APK_Downgrade_Service SHALL restore the original WhatsApp APK from the APK_Backup and return an error.
8. THE APK_Downgrade_Service SHALL log a Chain_of_Custody_Entry for each step of the downgrade process: backup, install, extraction, and restoration.
9. WHEN the downgrade process completes (successfully or with error), THE APK_Downgrade_Service SHALL return a status report including each step's outcome and any extracted Encryption_Key identifier.

### Requirement 5: WhatsApp Database Decryption

**User Story:** As an Investigator, I want to decrypt WhatsApp encrypted database files, so that I can access message history and contacts for forensic analysis.

#### Acceptance Criteria

1. WHEN an Investigator provides an Encrypted_Database file and an Encryption_Key, THE Decryption_Service SHALL decrypt the file and produce a Decrypted_Database.
2. THE Decryption_Service SHALL support both crypt14 and crypt15 encryption formats.
3. WHEN decryption succeeds, THE Decryption_Service SHALL parse the Decrypted_Database and extract Message_Records including sender, content, timestamp, read status, delivery status, and deletion flag.
4. WHEN decryption succeeds, THE Decryption_Service SHALL parse the Decrypted_Database and extract Contact_Records including phone number and display name.
5. WHEN decryption succeeds, THE Decryption_Service SHALL parse the Decrypted_Database and extract Media_References including media type, file name, and associated Message_Record identifier.
6. IF the Encryption_Key does not match the Encrypted_Database, THEN THE Decryption_Service SHALL return an error indicating key mismatch.
7. IF the Encrypted_Database file is corrupted or unreadable, THEN THE Decryption_Service SHALL return an error describing the corruption.
8. WHEN decryption is performed, THE Decryption_Service SHALL compute and store the SHA-256 Evidence_Hash of both the Encrypted_Database and the Decrypted_Database.
9. WHEN decryption is performed, THE Decryption_Service SHALL log a Chain_of_Custody_Entry recording the decryption operation, file identifiers, and timestamp.
10. FOR ALL valid Encrypted_Database files, decrypting then serializing the Decrypted_Database to JSON then parsing the JSON SHALL produce Message_Records equivalent to the original parsed records (round-trip property).

### Requirement 6: REST API for Evidence Data

**User Story:** As a Frontend Developer, I want the Backend to expose REST API endpoints that serve evidence data in the same format the frontend expects, so that the frontend can replace mock JSON files with real data.

#### Acceptance Criteria

1. THE Backend SHALL expose a GET endpoint that returns a list of Message_Records for a given Case in the same JSON structure as the Phase 1 Decrypted_Database mock format.
2. THE Backend SHALL expose a GET endpoint that returns Notification_Records for a given Case in the same JSON structure as the Phase 1 Notification_Log mock format.
3. THE Backend SHALL expose a GET endpoint that returns Contact_Records for a given Case.
4. THE Backend SHALL expose a GET endpoint that returns Media_References for a given Case.
5. THE Backend SHALL expose a GET endpoint that returns Case metadata including case number, creation timestamp, Investigator identifier, Device serial number, and associated data sources.
6. THE Backend SHALL expose POST endpoints for creating Cases, initiating device connections, triggering APK downgrade, initiating notification log extraction, initiating decryption, and requesting report generation.
7. IF an API request references a Case or resource that does not exist, THEN THE Backend SHALL return an HTTP 404 response with a descriptive error message.
8. IF an API request contains invalid or missing parameters, THEN THE Backend SHALL return an HTTP 422 response with validation error details.
9. THE Backend SHALL include CORS headers allowing requests from the React frontend origin.

### Requirement 7: Case Database Persistence

**User Story:** As an Investigator, I want case data to persist across Backend restarts, so that I do not lose investigation progress.

#### Acceptance Criteria

1. THE Backend SHALL use SQLAlchemy with a relational database to persist Case metadata, Message_Records, Notification_Records, Contact_Records, Media_References, Chain_of_Custody_Entries, and Evidence_Hashes.
2. WHEN a Case is created, THE Backend SHALL assign a unique case identifier and persist the Case metadata.
3. WHEN evidence artifacts are ingested (decrypted messages, contacts, media references), THE Backend SHALL associate them with their parent Case and persist them.
4. WHEN the Backend restarts, THE Backend SHALL restore all previously persisted Cases and their associated data.
5. THE Backend SHALL enforce referential integrity between Cases and their associated evidence artifacts.

### Requirement 8: PDF Forensic Report Generation

**User Story:** As an Investigator, I want to generate court-admissible PDF reports from case data, so that I can present forensic findings in legal proceedings.

#### Acceptance Criteria

1. WHEN an Investigator requests a report for a Case, THE Report_Generator SHALL produce a Forensic_Report in PDF format.
2. THE Forensic_Report SHALL include a title page with Case number, Investigator name, report generation timestamp, and Device information.
3. THE Forensic_Report SHALL include an evidence timeline section listing all Message_Records in chronological order with sender, content, timestamp, and source provenance.
4. THE Forensic_Report SHALL include a gap analysis section listing all detected evidence gaps with notification timestamps and absence confirmations.
5. THE Forensic_Report SHALL include an activity heatmap visualization showing message frequency by day-of-week and hour-of-day.
6. THE Forensic_Report SHALL include a chain of custody section listing all Chain_of_Custody_Entries for the Case in chronological order.
7. THE Forensic_Report SHALL include SHA-256 hash verification values for all evidence artifacts referenced in the report.
8. WHEN a Forensic_Report is generated, THE Report_Generator SHALL compute and store the SHA-256 Evidence_Hash of the generated PDF file.
9. WHEN a Forensic_Report is generated, THE Report_Generator SHALL log a Chain_of_Custody_Entry recording the report generation event.

### Requirement 9: Evidence Integrity and Legal Lock

**User Story:** As an Investigator, I want all evidence artifacts cryptographically hashed and signed, so that I can prove evidence has not been tampered with.

#### Acceptance Criteria

1. WHEN any evidence artifact is ingested or created (pulled files, decrypted databases, parsed records, generated reports), THE Legal_Lock_Service SHALL compute and store a SHA-256 Evidence_Hash for that artifact.
2. WHEN an Investigator requests verification of an evidence artifact, THE Legal_Lock_Service SHALL recompute the SHA-256 hash and compare it against the stored Evidence_Hash.
3. IF the recomputed hash does not match the stored Evidence_Hash, THEN THE Legal_Lock_Service SHALL return a tamper detection alert identifying the artifact and the hash mismatch.
4. IF the recomputed hash matches the stored Evidence_Hash, THEN THE Legal_Lock_Service SHALL return a verification confirmation with the hash value and verification timestamp.
5. THE Legal_Lock_Service SHALL maintain an append-only Chain_of_Custody log for each Case where entries cannot be modified or deleted after creation.
6. WHEN any evidence handling action occurs (file pull, decryption, report generation, verification), THE Legal_Lock_Service SHALL create a Chain_of_Custody_Entry with timestamp, Investigator identifier, action type, artifact identifier, and computed Evidence_Hash.
7. THE Legal_Lock_Service SHALL apply a Digital_Signature to Forensic_Reports using a configurable signing key.
8. THE Backend SHALL expose a GET endpoint that returns the complete Chain_of_Custody log for a given Case.
9. THE Backend SHALL expose a POST endpoint that verifies a specific evidence artifact and returns the verification result.

### Requirement 10: Media Recovery

**User Story:** As an Investigator, I want to recover deleted media files from a connected Android device, so that I can include recovered media as evidence.

#### Acceptance Criteria

1. WHILE a Device_Connection is active, THE Media_Recovery_Service SHALL scan WhatsApp media storage directories on the Device for recoverable media files (images, videos, audio, documents).
2. WHEN recoverable media files are found, THE Media_Recovery_Service SHALL pull each file from the Device and store it locally associated with the Case.
3. WHEN a media file is recovered, THE Media_Recovery_Service SHALL compute and store the SHA-256 Evidence_Hash of the recovered file.
4. WHEN media recovery is complete, THE Media_Recovery_Service SHALL cross-reference recovered media files with parsed Message_Records to identify which messages reference which media files.
5. THE Media_Recovery_Service SHALL classify each Recovered_Media by type: image, video, audio, or document.
6. WHEN media files are recovered, THE Media_Recovery_Service SHALL log a Chain_of_Custody_Entry for each recovered file recording the file name, Device path, recovery timestamp, and Evidence_Hash.
7. THE Backend SHALL expose a GET endpoint that returns a list of Recovered_Media for a given Case, including media type, file name, associated Message_Record identifier (if any), and Evidence_Hash.
8. THE Backend SHALL expose a GET endpoint that serves the binary content of a specific Recovered_Media file.
9. IF no recoverable media files are found on the Device, THEN THE Media_Recovery_Service SHALL return an empty result set with a confirmation that the scan completed.

### Requirement 11: Backend Configuration and Startup

**User Story:** As a Developer, I want the Backend to be configurable and easy to start, so that I can deploy and develop against it efficiently.

#### Acceptance Criteria

1. THE Backend SHALL be implemented using Python 3.11+ and FastAPI.
2. THE Backend SHALL accept configuration through environment variables for: database URL, ADB binary path, CORS allowed origins, signing key path, and server port.
3. WHEN the Backend starts, THE Backend SHALL run database migrations to ensure the schema is up to date.
4. WHEN the Backend starts, THE Backend SHALL validate that required configuration values are present and return a descriptive error if any are missing.
5. THE Backend SHALL provide a health check endpoint that returns the server status, database connectivity, and ADB availability.
