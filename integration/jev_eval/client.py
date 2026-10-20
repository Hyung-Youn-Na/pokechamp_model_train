"""Model-bound exact wire transport with the existing durable retry protocol."""
from integration.jev27b import client as shared
from .config import PROTOCOL, experiment

TIMEOUT = shared.TIMEOUT
RETRY_DELAYS = shared.RETRY_DELAYS
LocalRequestError = shared.LocalRequestError
base_url = shared.base_url


def request_bytes(payload, *, config):
    return shared.request_bytes(payload, model_id=experiment(config).model_id)


class LocalClient(shared.LocalClient):
    def __init__(self, config, endpoint=None, *, expected_identity=None,
                 timeout=TIMEOUT, record=None, transport=None):
        self.config = experiment(config)
        super().__init__(endpoint or self.config.endpoint, expected_identity=expected_identity,
            timeout=timeout, record=record, transport=transport, model_id=self.config.model_id,
            revision=self.config.revision, protocol=PROTOCOL)

    def request_bytes(self, payload):
        return request_bytes(payload, config=self.config)
