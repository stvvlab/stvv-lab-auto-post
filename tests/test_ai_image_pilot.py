import os
import unittest
from unittest.mock import patch
from ai_image_pilot import select_candidate, request_background

class AIPilotTests(unittest.TestCase):
    def test_no_candidate(self):
        self.assertIsNone(select_candidate({"drafts": []}))

    def test_disabled_never_calls_api(self):
        def forbidden(*args, **kwargs):
            raise AssertionError("Must not call paid API")
        with patch.dict(os.environ, {"STVV_IMAGE_PILOT": "0", "OPENAI_API_KEY": "dummy"}):
            with self.assertRaises(RuntimeError):
                request_background({"drafts": []}, http_post=forbidden)

    def test_no_candidate_never_calls_api(self):
        def forbidden(*args, **kwargs):
            raise AssertionError("Must not call paid API")
        with patch.dict(os.environ, {"STVV_IMAGE_PILOT": "1", "OPENAI_API_KEY": "dummy"}):
            result = request_background({"drafts": []}, http_post=forbidden)
        self.assertEqual(result["generated"], 0)

if __name__ == "__main__":
    unittest.main()
