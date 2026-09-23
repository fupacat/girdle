from girdle.detectors.dotnet import DotNetDetector
from girdle.detectors.go_mod import GoModDetector
from girdle.detectors.java_gradle import JavaGradleDetector
from girdle.detectors.java_maven import JavaMavenDetector
from girdle.detectors.js_bun import JsBunDetector
from girdle.detectors.js_npm import JsNpmDetector
from girdle.detectors.js_pnpm import JsPnpmDetector
from girdle.detectors.js_yarn import JsYarnDetector
from girdle.detectors.python_conda import PythonCondaDetector
from girdle.detectors.python_pip import PythonPipDetector
from girdle.detectors.python_pipenv import PythonPipenvDetector
from girdle.detectors.python_uv import PythonUvDetector
from girdle.detectors.rust import RustDetector

# JS/Python toolchain-specific detectors (yarn/pnpm/bun, uv/conda/pipenv/poetry)
# run before their generic fallback (npm, pip) so the fallback can yield via
# its own marker-exclusion checks. See each fallback's detect() for the
# exclusion list it applies.
ALL_DETECTORS = [
    JsYarnDetector(),
    JsPnpmDetector(),
    JsBunDetector(),
    JsNpmDetector(),
    PythonUvDetector(),
    PythonCondaDetector(),
    PythonPipenvDetector(),
    PythonPipDetector(),
    GoModDetector(),
    RustDetector(),
    JavaMavenDetector(),
    JavaGradleDetector(),
    DotNetDetector(),
]
