"""Build-config regressions use dummy values only and require no credentials."""

import contextlib
import importlib.util
import io
from pathlib import Path
import re
import tempfile
import unittest
from unittest import mock
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "Plain Craft Launcher 2"
SPEC = importlib.util.spec_from_file_location(
    "build_credentials", ROOT / ".github/scripts/build_credentials.py"
)
credentials = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(credentials)
DUMMY_ID = "11111111-2222-3333-4444-555555555555"
DUMMY_KEY = '$2a$10$' + "A" * 53


def environment(api_key=DUMMY_KEY, client_id=DUMMY_ID):
    return {"PCL_MS_CLIENT_ID": client_id, "PCL_CF_API_KEY": api_key}


class BuildCredentialGenerationTests(unittest.TestCase):
    def test_generates_both_constants_and_preserves_dollar_characters(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = io.StringIO()
            with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
                credentials.generate(root, environment())
            text = (root / credentials.GENERATED).read_text(encoding="utf-8")
            self.assertIn(f'Friend Const MicrosoftClientId As String = "{DUMMY_ID}"', text)
            self.assertIn(f'Friend Const CurseForgeApiKey As String = "{DUMMY_KEY}"', text)
            self.assertEqual(output.getvalue(), "")

    def test_opaque_key_is_literal_not_shell_code(self):
        key = 'dummy-$env:SECRET-$(command)-"quotes"-`ticks`'
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            credentials.generate(root, environment(key))
            text = (root / credentials.GENERATED).read_text(encoding="utf-8")
            self.assertIn(key.replace('"', '""'), text)
        self.assertEqual(credentials.vb_string('a"$b'), '"a""$b"')

    def test_invalid_ids_never_appear_in_error_messages(self):
        for value in ("", "not-a-uuid", DUMMY_ID + "\n", " " + DUMMY_ID, DUMMY_ID + '"'):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, r"^PCL_MS_CLIENT_ID must be a UUID\.$"):
                    credentials.read_credentials(environment(client_id=value))

    def test_invalid_keys_are_rejected_without_echo(self):
        for value in ("", "short", DUMMY_KEY + "\n", DUMMY_KEY + "\r", DUMMY_KEY + "\t",
                      DUMMY_KEY + " ", DUMMY_KEY + "\0", "é" * 60, "A" * 513):
            with self.subTest(length=len(value)):
                with self.assertRaisesRegex(ValueError, r"^PCL_CF_API_KEY must be a nonempty printable API key\.$"):
                    credentials.read_credentials(environment(value))

    def test_failed_validation_removes_stale_generated_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            credentials.generate(root, environment())
            with self.assertRaises(ValueError):
                credentials.generate(root, {})
            self.assertFalse((root / credentials.GENERATED).exists())

    def test_partial_write_is_removed_on_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            destination = root / credentials.GENERATED

            def fail_write(path, *_args, **_kwargs):
                with path.open("w", encoding="utf-8") as stream:
                    stream.write("partial generated source")
                raise OSError("simulated write failure")

            with mock.patch.object(Path, "write_text", fail_write):
                with self.assertRaises(OSError):
                    credentials.generate(root, environment())
            self.assertFalse(destination.exists())

    def test_cli_failure_does_not_log_exception_payload(self):
        output = io.StringIO()
        with mock.patch("sys.argv", ["build_credentials.py"]), \
             mock.patch.object(credentials, "generate", side_effect=OSError(DUMMY_KEY)), \
             contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            self.assertEqual(credentials.main(), 1)
        self.assertNotIn(DUMMY_KEY, output.getvalue())
        self.assertIn("Build credential preparation failed", output.getvalue())

    def test_cleanup_is_idempotent_and_requires_no_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            credentials.generate(root, environment())
            with mock.patch.object(credentials, "ROOT", root), \
                 mock.patch("sys.argv", ["build_credentials.py", "--clean"]), \
                 mock.patch.dict("os.environ", {}, clear=True):
                self.assertEqual(credentials.main(), 0)
                self.assertEqual(credentials.main(), 0)
            self.assertFalse((root / credentials.GENERATED).exists())


class BuildCredentialWiringTests(unittest.TestCase):
    def test_public_defaults_are_empty_and_runtime_overrides_remain(self):
        stub = (APP / "Modules/BuildCredentials.vb").read_text(encoding="utf-8")
        self.assertIn('Friend Const MicrosoftClientId As String = ""', stub)
        self.assertIn('Friend Const CurseForgeApiKey As String = ""', stub)
        source = (APP / "Modules/ModSecret.vb").read_text(encoding="utf-8-sig")
        self.assertNotRegex(source, credentials.CLIENT_ID_PATTERN.pattern)
        self.assertIn('If(Environment.GetEnvironmentVariable("PCL_MS_CLIENT_ID"), BuildCredentials.MicrosoftClientId)', source)
        self.assertIn('If(Environment.GetEnvironmentVariable("PCL_CURSEFORGE_API_KEY"), If(Environment.GetEnvironmentVariable("PCL_CF_API_KEY"), BuildCredentials.CurseForgeApiKey))', source)

    def test_project_compiles_exactly_one_credentials_module(self):
        namespace = {"m": "http://schemas.microsoft.com/developer/msbuild/2003"}
        project = ET.parse(APP / "Plain Craft Launcher 2.vbproj")
        entries = {
            element.attrib["Include"]: element.attrib.get("Condition")
            for element in project.findall(".//m:Compile", namespace)
            if "BuildCredentials" in element.attrib["Include"]
        }
        self.assertEqual(entries, {
            r"Modules\BuildCredentials.vb": r"!Exists('obj\PrivateBuildCredentials.g.vb')",
            r"obj\PrivateBuildCredentials.g.vb": r"Exists('obj\PrivateBuildCredentials.g.vb')",
        })
        self.assertIn("[Oo]bj/", (ROOT / ".gitignore").read_text())

    def test_workflow_scopes_secrets_and_always_cleans_before_exe_upload(self):
        workflow = (ROOT / ".github/workflows/build.yml").read_text()
        steps = {
            part.splitlines()[0]: part for part in workflow.split("    - name: ")[1:]
        }
        guard = "github.event_name != 'pull_request' && github.ref == format('refs/heads/{0}', github.event.repository.default_branch)"
        for name in ("Generate Private Build Credentials", "Verify Compiled Credentials"):
            step = steps[name]
            self.assertIn("if: " + guard, step)
            self.assertIn("PCL_MS_CLIENT_ID: ${{ secrets.PCL_MS_CLIENT_ID }}", step)
            self.assertIn("PCL_CF_API_KEY: ${{ secrets.CURSEFORGE_API_KEY }}", step)
            self.assertNotIn("${{ secrets.", step.split("run: ", 1)[1])
        self.assertEqual(workflow.count("${{ secrets."), 4)
        self.assertIn("shell: powershell", steps["Verify Compiled Credentials"])
        self.assertIn("if: always()", steps["Remove Private Build Source"])
        self.assertIn("--clean", steps["Remove Private Build Source"])
        self.assertLess(workflow.index("Remove Private Build Source"), workflow.index("Upload a Build Artifact"))
        self.assertNotIn("secrets.", steps["Build"])
        self.assertIn("-verbosity:minimal", steps["Build"])
        artifact = steps["Upload a Build Artifact"]
        self.assertIn(r"path: Plain Craft Launcher 2\obj\${{ matrix.configuration }}\Plain Craft Launcher 2.exe", artifact)
        self.assertNotRegex(artifact, r"path:.*[*]")
        self.assertIn("if-no-files-found: error", artifact)

    def test_verifier_checks_raw_constants_without_running_application(self):
        script = (ROOT / ".github/scripts/verify_build_credentials.ps1").read_text()
        self.assertIn("::ReflectionOnlyLoad(", script)
        self.assertIn("GetType('PCL.BuildCredentials'", script)
        self.assertIn("GetRawConstantValue()", script)
        self.assertIn("[StringComparer]::Ordinal.Equals", script)
        self.assertNotIn(".GetValue(", script)
        for line in script.splitlines():
            if re.search(r"Write-(Host|Output|Error)", line):
                self.assertNotIn("$expected", line)
                self.assertNotIn("$env:", line)
                self.assertNotIn("$_", line)

    def test_api_key_initial_destination_checks_https_host(self):
        source = (APP / "Modules/ModSecret.vb").read_text(encoding="utf-8-sig")
        self.assertNotIn('Url.Contains("api.curseforge.com")', source)
        self.assertNotIn('Url.Contains("forgecdn.net")', source)
        self.assertIn("Uri.TryCreate(Url, UriKind.Absolute, RequestUri)", source)
        self.assertIn("RequestUri.Scheme = Uri.UriSchemeHttps", source)
        self.assertIn('String.Equals(RequestUri.Host, "api.curseforge.com", StringComparison.OrdinalIgnoreCase)', source)
        self.assertIn('RequestUri.Host.EndsWith(".forgecdn.net", StringComparison.OrdinalIgnoreCase)', source)


if __name__ == "__main__":
    unittest.main()
