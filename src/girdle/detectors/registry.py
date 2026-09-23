from girdle.detectors.go_mod import GoModDetector
from girdle.detectors.js_npm import JsNpmDetector
from girdle.detectors.python_pip import PythonPipDetector

# Order matters only for detectors that could both match the same root ambiguously;
# each detect() is expected to return None for markers it doesn't own.
ALL_DETECTORS = [
    JsNpmDetector(),
    PythonPipDetector(),
    GoModDetector(),
]
