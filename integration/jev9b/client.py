"""EX-085 identity bound transport, retaining exact request IDs and wire retries."""
from integration.jev27b import client as shared
from .config import ENDPOINT, MODEL_ID, REVISION

PROTOCOL = 'jev9b-local-v1'
TIMEOUT = shared.TIMEOUT
RETRY_DELAYS = shared.RETRY_DELAYS
DEFAULT_ENDPOINT = ENDPOINT
LocalRequestError = shared.LocalRequestError
base_url = shared.base_url


def request_bytes(payload):
    return shared.request_bytes(payload, model_id=MODEL_ID)


class LocalClient(shared.LocalClient):
    request_bytes = staticmethod(request_bytes)

    def __init__(self, endpoint=DEFAULT_ENDPOINT, *, expected_identity=None,
                 timeout=TIMEOUT, record=None, transport=None):
        super().__init__(endpoint, expected_identity=expected_identity, timeout=timeout,
                         record=record, transport=transport, model_id=MODEL_ID,
                         revision=REVISION, protocol=PROTOCOL)
