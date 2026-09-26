import os
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

import app


class FakePaddleOCR:
    kwargs = None

    def __init__(self, **kwargs):
        type(self).kwargs = kwargs


class PipelineConfigTest(unittest.TestCase):
    def setUp(self):
        app._pipeline = None
        app._pipeline_error = None
        app._pipeline_kind = None
        FakePaddleOCR.kwargs = None

    def tearDown(self):
        app._pipeline = None
        app._pipeline_error = None
        app._pipeline_kind = None

    def _initialize_with_fake_paddleocr(self):
        paddleocr_module = types.ModuleType("paddleocr")
        paddleocr_module.PaddleOCR = FakePaddleOCR
        with patch.dict(sys.modules, {"paddleocr": paddleocr_module}):
            app._initialize_pipeline()

    def test_uses_model_directories_from_environment(self):
        environment = {
            "PADDLEOCR_PIPELINE": "ocr",
            "PADDLEOCR_TEXT_DETECTION_MODEL_DIR": "/models/det",
            "PADDLEOCR_TEXT_RECOGNITION_MODEL_DIR": "/models/rec",
        }
        with patch.dict(os.environ, environment, clear=False):
            self._initialize_with_fake_paddleocr()

        self.assertEqual(
            "/models/det", FakePaddleOCR.kwargs["text_detection_model_dir"]
        )
        self.assertEqual(
            "/models/rec", FakePaddleOCR.kwargs["text_recognition_model_dir"]
        )

    def test_uses_existing_standard_cache_directories(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            detection_dir = os.path.join(temp_dir, "det")
            recognition_dir = os.path.join(temp_dir, "rec")
            os.makedirs(detection_dir)
            os.makedirs(recognition_dir)

            real_isdir = os.path.isdir

            def fake_isdir(path):
                if path.endswith("PP-OCRv5_server_det"):
                    return True
                if path.endswith("PP-OCRv5_server_rec"):
                    return True
                return real_isdir(path)

            environment = {
                "PADDLEOCR_PIPELINE": "ocr",
                "PADDLEOCR_TEXT_DETECTION_MODEL_DIR": "",
                "PADDLEOCR_TEXT_RECOGNITION_MODEL_DIR": "",
            }
            with patch.dict(os.environ, environment, clear=False), patch(
                "app.os.path.isdir", side_effect=fake_isdir
            ):
                self._initialize_with_fake_paddleocr()

        self.assertEqual(
            "/home/ocr/.paddlex/official_models/PP-OCRv5_server_det",
            FakePaddleOCR.kwargs["text_detection_model_dir"],
        )
        self.assertEqual(
            "/home/ocr/.paddlex/official_models/PP-OCRv5_server_rec",
            FakePaddleOCR.kwargs["text_recognition_model_dir"],
        )


if __name__ == "__main__":
    unittest.main()
