from .case import *
from .message_record import *
from .notification_record import *
from .contact_record import *
from .media_reference import *
from .recovered_media import *
from .chain_of_custody_entry import *
from .evidence_hash import *
from .encryption_key import *
from .forensic_report import *

# Append-only event listener for ChainOfCustodyEntry
from sqlalchemy import event
from .chain_of_custody_entry import ChainOfCustodyEntry

def _raise_on_update_delete(mapper, connection, target):
    raise Exception("ChainOfCustodyEntry is append-only and cannot be updated or deleted.")

event.listen(ChainOfCustodyEntry, 'before_update', _raise_on_update_delete)
event.listen(ChainOfCustodyEntry, 'before_delete', _raise_on_update_delete)
