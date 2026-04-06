import factory
from uuid import uuid4

from app.models.case import Case
from app.models.message_record import MessageRecord
from app.models.notification_record import NotificationRecord
from app.models.contact_record import ContactRecord
from app.models.media_reference import MediaReference
from app.models.recovered_media import RecoveredMedia
from app.models.chain_of_custody_entry import ChainOfCustodyEntry


class CaseFactory(factory.Factory):
    class Meta:
        model = Case

    id = factory.LazyFunction(lambda: str(uuid4()))
    case_number = factory.Sequence(lambda n: f"CASE-{n:04d}")
    investigator_id = "test-investigator"
    device_serial = "TEST-SERIAL"
    device_imei = "123456789012345"
    os_version = "Android 13"
    notes = "[]"


class MessageRecordFactory(factory.Factory):
    class Meta:
        model = MessageRecord

    id = factory.LazyFunction(lambda: str(uuid4()))
    case_id = ""
    sender = factory.Sequence(lambda n: f"sender-{n}")
    content = factory.Sequence(lambda n: f"Message content {n}")
    timestamp = factory.Sequence(lambda n: 1700000000000 + n * 60000)
    status = "READ"
    is_deleted = False


class NotificationRecordFactory(factory.Factory):
    class Meta:
        model = NotificationRecord

    id = factory.LazyFunction(lambda: str(uuid4()))
    case_id = ""
    sender = factory.Sequence(lambda n: f"notif-sender-{n}")
    content = factory.Sequence(lambda n: f"Notification {n}")
    timestamp = factory.Sequence(lambda n: 1700000000000 + n * 30000)
    app_package = "com.whatsapp"


class ContactRecordFactory(factory.Factory):
    class Meta:
        model = ContactRecord

    id = factory.LazyFunction(lambda: str(uuid4()))
    case_id = ""
    phone_number = factory.Sequence(lambda n: f"+1555000{n:04d}")
    display_name = factory.Sequence(lambda n: f"Contact {n}")


class MediaReferenceFactory(factory.Factory):
    class Meta:
        model = MediaReference

    id = factory.LazyFunction(lambda: str(uuid4()))
    case_id = ""
    media_type = "image"
    file_name = factory.Sequence(lambda n: f"photo_{n}.jpg")


class RecoveredMediaFactory(factory.Factory):
    class Meta:
        model = RecoveredMedia

    id = factory.LazyFunction(lambda: str(uuid4()))
    case_id = ""
    media_type = "image"
    file_name = factory.Sequence(lambda n: f"recovered_{n}.jpg")
    device_path = factory.LazyAttribute(lambda o: f"/sdcard/WhatsApp/Media/{o.file_name}")
    local_path = factory.LazyAttribute(lambda o: f"recovered_media/{o.file_name}")
    evidence_hash = "a" * 64


class ChainOfCustodyEntryFactory(factory.Factory):
    class Meta:
        model = ChainOfCustodyEntry

    id = factory.LazyFunction(lambda: str(uuid4()))
    case_id = ""
    investigator_id = "test-investigator"
    action_type = "TEST_ACTION"
    artifact_id = factory.Sequence(lambda n: f"artifact-{n}")
    evidence_hash = ""
    description = "Test entry"
