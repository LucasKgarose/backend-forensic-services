# Implementation Plan: Backend Forensic Services

## Overview

Build a standalone Python 3.11+ FastAPI backend in `backend/` that provides forensic investigation REST API services. The implementation proceeds bottom-up: project scaffolding → data layer → service layer → API layer → integration wiring, with property and unit tests alongside each component.

## Tasks

- [ ] 1. Project scaffolding and configuration
  - [ ] 1.1 Create backend project structure with pyproject.toml and dependencies
    - Create `backend/` directory with `pyproject.toml` listing FastAPI, SQLAlchemy, Alembic, adb-shell, pycryptodome, reportlab, hypothesis, pytest, httpx, factory-boy, pytest-asyncio
    - Create package structure: `backend/app/`, `backend/app/api/`, `backend/app/services/`, `backend/app/models/`, `backend/app/schemas/`, `backend/tests/`
    - Create `backend/app/__init__.py`, `backend/app/main.py` with minimal FastAPI app
    - _Requirements: 11.1_

  - [ ] 1.2 Implement configuration module with environment variable loading
    - Create `backend/app/config.py` with Pydantic `Settings` class loading DATABASE_URL, ADB_PATH, CORS_ORIGINS, SIGNING_KEY_PATH, SERVER_PORT from environment
    - Raise `ConfigurationError` with the missing key name when required values are absent
    - _Requirements: 11.2, 11.4_

  - [ ]* 1.3 Write property tests for configuration (Properties 21, 22)
    - **Property 21: Configuration Loading from Environment Variables**
    - **Validates: Requirements 11.2**
    - **Property 22: Configuration Validation for Missing Values**
    - **Validates: Requirements 11.4**

  - [ ] 1.4 Set up SQLAlchemy engine, session factory, and Alembic migrations
    - Create `backend/app/database.py` with engine creation, `SessionLocal`, and `Base` declarative base
    - Initialize Alembic in `backend/alembic/` with `env.py` pointing to app models
    - Create initial migration
    - _Requirements: 7.1, 11.3_

- [ ] 2. Data models and error hierarchy
  - [ ] 2.1 Implement all SQLAlchemy ORM models
    - Create `backend/app/models/` with Case, MessageRecord, NotificationRecord, ContactRecord, MediaReference, RecoveredMedia, ChainOfCustodyEntry, EvidenceHash, EncryptionKey, ForensicReport as defined in design
    - Implement all relationships, foreign keys, and cascade rules
    - Add ORM event listener on ChainOfCustodyEntry to prevent UPDATE and DELETE (append-only enforcement)
    - _Requirements: 7.1, 7.5, 9.5_

  - [ ]* 2.2 Write property tests for data integrity (Properties 3, 14, 15, 16)
    - **Property 3: Chain of Custody Append-Only Immutability**
    - **Validates: Requirements 9.5**
    - **Property 14: Case ID Uniqueness**
    - **Validates: Requirements 7.2**
    - **Property 15: Data Persistence Round-Trip**
    - **Validates: Requirements 3.8, 7.3**
    - **Property 16: Referential Integrity Enforcement**
    - **Validates: Requirements 7.5**

  - [ ] 2.3 Implement error hierarchy
    - Create `backend/app/errors.py` with ForensicServiceError base and all subclasses: DeviceNotFoundError, DeviceConnectionError, FileNotFoundOnDeviceError, ShellCommandError, APKDowngradeError, DecryptionError, KeyMismatchError, CorruptedDatabaseError, NotificationSourceUnavailableError, TamperDetectedError, CaseNotFoundError, ReportGenerationError, ConfigurationError
    - _Requirements: 2.4, 2.5, 3.6, 3.7, 4.5, 4.6, 4.7, 5.6, 5.7, 6.7, 6.8_

- [ ] 3. Pydantic schemas
  - [ ] 3.1 Implement all Pydantic request/response schemas
    - Create `backend/app/schemas/` with request models (CreateCaseRequest, ConnectRequest, PullFileRequest, ShellCommandRequest, ExtractNotificationsRequest, APKDowngradeRequest, DecryptRequest, VerifyRequest, GenerateReportRequest, RecoverMediaRequest) and response models (CaseResponse, NotificationLogEnvelope, DecryptedDatabaseEnvelope, ChainOfCustodyResponse, HealthResponse, etc.) matching the design document
    - Ensure envelope formats match Phase 1 frontend expectations (camelCase field names, Unix epoch ms timestamps)
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

  - [ ]* 3.2 Write property tests for serialization (Properties 5, 6)
    - **Property 5: Notification Envelope Format Compliance**
    - **Validates: Requirements 3.3, 6.2**
    - **Property 6: Message Record Serialization Round-Trip**
    - **Validates: Requirements 5.10, 6.1**

- [ ] 4. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 5. Legal Lock Service (core dependency for other services)
  - [ ] 5.1 Implement Legal_Lock_Service
    - Create `backend/app/services/legal_lock_service.py` implementing compute_and_store_hash, verify_artifact, get_chain_of_custody, log_custody_entry, sign_report
    - SHA-256 hashing via hashlib, digital signatures via pycryptodome RSA
    - Persist EvidenceHash and ChainOfCustodyEntry records to database
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7_

  - [ ]* 5.2 Write property tests for hashing and verification (Properties 1, 10, 11)
    - **Property 1: SHA-256 Hash Determinism**
    - **Validates: Requirements 2.2, 3.4, 5.8, 8.8, 9.1, 10.3**
    - **Property 10: Evidence Verification Correctness**
    - **Validates: Requirements 9.2, 9.3, 9.4**
    - **Property 11: Digital Signature Round-Trip**
    - **Validates: Requirements 9.7**

  - [ ]* 5.3 Write property test for chain of custody entry completeness (Property 2)
    - **Property 2: Chain of Custody Entry Completeness**
    - **Validates: Requirements 1.6, 2.6, 3.5, 4.8, 5.9, 8.9, 9.6, 10.6**

- [ ] 6. ADB Bridge Service
  - [ ] 6.1 Implement ADB_Bridge_Service
    - Create `backend/app/services/adb_bridge_service.py` implementing discover_devices, connect, disconnect, get_connection_status, pull_file, execute_shell
    - Use adb-shell or subprocess calls to ADB binary
    - Compute SHA-256 hash on pulled files, log chain of custody entries for all operations
    - Track active connections in memory, detect disconnections
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_

  - [ ]* 6.2 Write property test for error response file path (Property 23)
    - **Property 23: Error Response Includes Missing File Path**
    - **Validates: Requirements 2.4**

  - [ ]* 6.3 Write unit tests for ADB Bridge Service
    - Test device discovery, connection lifecycle, file pull with hash computation, shell command execution, error paths (missing file, failed command)
    - Mock subprocess/adb-shell calls
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 2.1, 2.3_

- [ ] 7. Notification Log Service
  - [ ] 7.1 Implement Notification_Log_Service
    - Create `backend/app/services/notification_log_service.py` implementing extract_notifications and get_notifications
    - Pull notification scraper DB from device via ADB_Bridge, parse SQLite, filter for com.whatsapp, compute evidence hash, log chain of custody, persist NotificationRecords
    - Return data in Phase 1 envelope format (deviceIMEI, exportDate, entries)
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8_

  - [ ]* 7.2 Write property test for notification filtering (Property 4)
    - **Property 4: Notification WhatsApp Filtering**
    - **Validates: Requirements 3.2**

- [ ] 8. APK Downgrade Service
  - [ ] 8.1 Implement APK_Downgrade_Service
    - Create `backend/app/services/apk_downgrade_service.py` implementing execute_downgrade and get_downgrade_status
    - Steps: backup current APK → install old APK → extract encryption key → restore original APK
    - Rollback on any step failure (restore from backup), log chain of custody for each step
    - Return DowngradeResult with step-by-step status report
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8, 4.9_

  - [ ]* 8.2 Write property tests for APK downgrade (Properties 8, 9)
    - **Property 8: APK Downgrade Rollback on Failure**
    - **Validates: Requirements 4.5, 4.6, 4.7**
    - **Property 9: APK Downgrade Status Report Completeness**
    - **Validates: Requirements 4.9**

- [ ] 9. Decryption Service
  - [ ] 9.1 Implement Decryption_Service
    - Create `backend/app/services/decryption_service.py` implementing decrypt_database, get_messages, get_contacts, get_media_references
    - Support crypt14 and crypt15 formats using pycryptodome
    - Parse decrypted SQLite DB to extract MessageRecords, ContactRecords, MediaReferences
    - Compute evidence hashes for encrypted and decrypted files, log chain of custody
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8, 5.9, 5.10_

  - [ ]* 9.2 Write property test for DB parser field extraction (Property 7)
    - **Property 7: WhatsApp DB Parser Field Extraction**
    - **Validates: Requirements 5.3, 5.4, 5.5**

- [ ] 10. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 11. Media Recovery Service
  - [ ] 11.1 Implement Media_Recovery_Service
    - Create `backend/app/services/media_recovery_service.py` implementing scan_and_recover, get_recovered_media, get_media_file
    - Scan WhatsApp media directories via ADB, pull files, classify by extension, compute evidence hashes, cross-reference with MessageRecords, log chain of custody
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.9_

  - [ ]* 11.2 Write property tests for media (Properties 18, 19, 20)
    - **Property 18: Media Type Classification**
    - **Validates: Requirements 10.5**
    - **Property 19: Media Cross-Referencing**
    - **Validates: Requirements 10.4**
    - **Property 20: Media File Serving Round-Trip**
    - **Validates: Requirements 10.8**

- [ ] 12. Report Generator Service
  - [ ] 12.1 Implement Report_Generator_Service
    - Create `backend/app/services/report_generator_service.py` implementing generate_report and get_report
    - Use ReportLab to produce PDF with: title page (case number, investigator, timestamp, device info), evidence timeline, gap analysis, activity heatmap, chain of custody section, SHA-256 hash verification values
    - Compute evidence hash of generated PDF, apply digital signature, log chain of custody
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7, 8.8, 8.9_

  - [ ]* 12.2 Write property test for report generation (Property 17)
    - **Property 17: Forensic Report Valid PDF with Required Content**
    - **Validates: Requirements 8.1, 8.2, 8.3, 8.6, 8.7**

- [ ] 13. Test fixtures and factories
  - [ ] 13.1 Create shared test infrastructure
    - Create `backend/tests/conftest.py` with in-memory SQLite test database, SQLAlchemy session fixture, FastAPI TestClient fixture
    - Create `backend/tests/factories.py` with factory_boy factories for Case, MessageRecord, NotificationRecord, ContactRecord, MediaReference, RecoveredMedia, ChainOfCustodyEntry
    - Create Hypothesis strategies module at `backend/tests/strategies.py` with message_records, notification_records, artifact_bytes, case_inputs, media_file_names strategies as defined in design
    - _Requirements: all (testing infrastructure)_

- [ ] 14. API layer - routers and exception handlers
  - [ ] 14.1 Implement FastAPI exception handlers
    - Create `backend/app/api/exception_handlers.py` mapping all domain exceptions to HTTP responses per the design error handling table
    - Register handlers in the FastAPI app
    - _Requirements: 6.7, 6.8_

  - [ ] 14.2 Implement Cases router
    - Create `backend/app/api/cases.py` with POST / (create case), GET / (list cases), GET /{case_id} (case metadata), GET /{case_id}/messages, GET /{case_id}/notifications, GET /{case_id}/contacts, GET /{case_id}/media-references, GET /{case_id}/chain-of-custody
    - Wire to services, return Pydantic response models
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 9.8_

  - [ ] 14.3 Implement Devices router
    - Create `backend/app/api/devices.py` with GET / (discover), POST /{serial}/connect, POST /{serial}/disconnect, POST /{serial}/pull-file, POST /{serial}/shell, POST /{serial}/extract-notifications, POST /{serial}/apk-downgrade, POST /{serial}/recover-media
    - Wire to ADB_Bridge, Notification_Log, APK_Downgrade, Media_Recovery services
    - _Requirements: 6.6_

  - [ ] 14.4 Implement Evidence router
    - Create `backend/app/api/evidence.py` with POST /decrypt, POST /verify, GET /{case_id}/recovered-media, GET /{case_id}/recovered-media/{media_id}
    - Wire to Decryption_Service, Legal_Lock_Service, Media_Recovery_Service
    - _Requirements: 6.6, 9.9, 10.7, 10.8_

  - [ ] 14.5 Implement Reports router
    - Create `backend/app/api/reports.py` with POST / (generate report), GET /{case_id}/{report_id} (download PDF)
    - Wire to Report_Generator_Service
    - _Requirements: 6.6_

  - [ ] 14.6 Implement Health router
    - Create `backend/app/api/health.py` with GET / returning server status, database connectivity, ADB availability
    - _Requirements: 11.5_

  - [ ]* 14.7 Write property tests for API error responses (Properties 12, 13)
    - **Property 12: API 404 for Missing Resources**
    - **Validates: Requirements 6.7**
    - **Property 13: API 422 for Invalid Input**
    - **Validates: Requirements 6.8**

- [ ] 15. App wiring and startup
  - [ ] 15.1 Wire FastAPI app with all routers, CORS, and startup events
    - Update `backend/app/main.py` to include all routers under `/api/v1/` prefix, register exception handlers, configure CORS middleware from settings, run Alembic migrations on startup, validate configuration on startup
    - Create dependency injection setup for services (FastAPI `Depends`)
    - _Requirements: 6.9, 11.1, 11.3, 11.4_

- [ ] 16. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- All services use dependency injection via FastAPI's `Depends` for testability
- The `backend/` directory is a self-contained Python project with its own dependencies
