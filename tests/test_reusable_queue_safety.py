"""Offline safety tests for reusable Buffer queue; never connects to Buffer."""
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from editorial.manual_reservation import enqueue_approved as module

PNG = bytes.fromhex("89504e470d0a1a0a") + b"test-image"

class Response:
    content = PNG
    def raise_for_status(self): pass

class FakeClient:
    mutation_calls = 0
    def preflight(self):
        return {"channel_id":"test-channel","remaining_capacity":3,"posts":[]}
    def query(self, query, variables=None):
        if "organizations" in query:
            return {"account":{"organizations":[{"id":"test-org"}]}}
        if "createPost" in query:
            FakeClient.mutation_calls += 1
            raise AssertionError("No real Buffer mutation allowed in offline tests")
        raise AssertionError("Unexpected query")
    def posts(self, org, statuses, *, channel=None):
        return [{"text":"approved caption"}] if statuses == ["draft"] else []

class SafetyTests(unittest.TestCase):
    def setUp(self):
        FakeClient.mutation_calls = 0
        self.root = Path("editorial/reservation_requests")
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "_offline_safety_test.json"
        self.request = {"approval_status":"approved","text":"approved caption","image_public_url":"https://example.com/approved.png","image_sha256":hashlib.sha256(PNG).hexdigest()}
        self.path.write_text(json.dumps(self.request),encoding="utf-8")
        self.addCleanup(lambda: self.path.unlink(missing_ok=True))
    def run_case(self, request=None, image=PNG, client=FakeClient):
        if request is not None:
            self.path.write_text(json.dumps(request),encoding="utf-8")
        with patch.dict(os.environ,{"REQUEST_PATH":str(self.path)}),patch.object(module.requests,"get",return_value=type("R",(),{"content":image,"raise_for_status":lambda self:None})()),patch.object(module,"BufferReservations",client):
            module.main()
    def test_unapproved_rejected(self):
        with self.assertRaisesRegex(ValueError,"approval_status"):
            self.run_case({**self.request,"approval_status":"pending"})
        self.assertEqual(FakeClient.mutation_calls,0)
    def test_invalid_png_rejected(self):
        with self.assertRaisesRegex(ValueError,"PNG"):
            self.run_case(image=b"not png")
        self.assertEqual(FakeClient.mutation_calls,0)
    def test_wrong_hash_rejected(self):
        with self.assertRaisesRegex(ValueError,"SHA256"):
            self.run_case(image=PNG+b"changed")
        self.assertEqual(FakeClient.mutation_calls,0)
    def test_matching_draft_rejected(self):
        with self.assertRaisesRegex(ValueError,"draft"):
            self.run_case()
        self.assertEqual(FakeClient.mutation_calls,0)
    def test_outside_path_rejected(self):
        with tempfile.NamedTemporaryFile(suffix=".json") as f:
            with patch.dict(os.environ,{"REQUEST_PATH":f.name}):
                with self.assertRaisesRegex(ValueError,"editorial JSON"):
                    module.main()
        self.assertEqual(FakeClient.mutation_calls,0)

if __name__=="__main__":
    unittest.main()
