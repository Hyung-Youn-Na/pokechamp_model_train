"""실제 API 호출 없이 인증 경계와 HTTP 동작을 검증한다."""

import json
import tempfile
import unittest
from pathlib import Path

import httpx

from .client import DecisionsError, ENDPOINT, MODEL, create_decision, read_api_key

PAYLOAD = {"model": MODEL, "input": "test", "questions": [
    {"type": "predicate", "name": "ok", "instructions": "Is this a test?"}
]}


class ClientTests(unittest.TestCase):
    def test_dotenv_and_explicit_process_override(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text('OPENAI_API_KEY="file-key-${LITERAL}"\n')
            path.chmod(0o600)
            self.assertEqual(read_api_key(path, {}), "file-key-${LITERAL}")
            self.assertEqual(read_api_key(path, {"OPENAI_API_KEY": "process-key"}), "process-key")
            with self.assertRaises(DecisionsError):
                read_api_key(path, {"OPENAI_API_KEY": ""})
            path.chmod(0o644)
            with self.assertRaisesRegex(DecisionsError, "600"):
                read_api_key(path, {})

    def test_missing_key(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(DecisionsError, "OPENAI_API_KEY"):
                read_api_key(Path(directory) / ".env", {})

    def test_success_request_and_refusal_preserved(self):
        result = {"model": MODEL, "answers": [{"type": "refusal", "name": "ok"}]}
        def handler(request):
            self.assertEqual(str(request.url), ENDPOINT)
            self.assertEqual(request.method, "POST")
            self.assertEqual(request.headers["authorization"], "Bearer fake-key")
            self.assertEqual(json.loads(request.content), PAYLOAD)
            return httpx.Response(200, json=result)
        self.assertEqual(create_decision(PAYLOAD, "fake-key", transport=httpx.MockTransport(handler)), result)

    def test_http_failures_not_retried_or_leaked(self):
        for status in (302, 400, 401, 403, 404, 429, 500):
            calls = []
            def handler(request):
                calls.append(request)
                return httpx.Response(status, text="fake-key private response", headers={"location": "https://example.com"})
            with self.assertRaises(DecisionsError) as caught:
                create_decision(PAYLOAD, "fake-key", transport=httpx.MockTransport(handler))
            self.assertIn(str(status), str(caught.exception))
            self.assertNotIn("fake-key", str(caught.exception))
            self.assertEqual(len(calls), 1)

    def test_timeout(self):
        def handler(request):
            raise httpx.ReadTimeout("fake-key", request=request)
        with self.assertRaisesRegex(DecisionsError, "시간 초과"):
            create_decision(PAYLOAD, "fake-key", transport=httpx.MockTransport(handler))

    def test_invalid_response(self):
        for body in ("not json", "{}"):
            with self.assertRaises(DecisionsError):
                create_decision(PAYLOAD, "fake-key", transport=httpx.MockTransport(
                    lambda request: httpx.Response(200, text=body)))

    def test_invalid_request_never_sent(self):
        def handler(request):
            self.fail("invalid request sent")
        with self.assertRaises(DecisionsError):
            create_decision({**PAYLOAD, "model": "wrong-model"}, "fake-key", transport=httpx.MockTransport(handler))


if __name__ == "__main__":
    unittest.main()
