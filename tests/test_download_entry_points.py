"""Source-wiring regression checks for the restored download entry points.

These checks deliberately require no .NET/WPF runtime or network access. They
guard the entry points disabled in e4b0489; they do not execute VB, download a
game, or replace the Windows build and interactive smoke tests.
"""

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1] / "Plain Craft Launcher 2"


def source(relative_path):
    return (ROOT / relative_path).read_text(encoding="utf-8-sig")


def method(relative_path, name, kind="Sub"):
    """Read a top-level VB method, including its indented anonymous delegates."""
    text = source(relative_path)
    pattern = (
        rf"^    (?:Public|Private|Friend|Protected) [^\n]*\b{kind} "
        rf"{re.escape(name)}\([^\n]*\n.*?^    End {kind}\b"
    )
    match = re.search(pattern, text, re.MULTILINE | re.DOTALL)
    if match is None:
        raise AssertionError(f"Cannot find {kind} {name} in {relative_path}")
    return match.group()


INSTALL = "Pages/PageDownload/PageDownloadInstall.xaml.vb"
MODIFY = "Pages/PageDownload/PageDownloadModify.vb"
DETAIL = "Pages/PageDownload/Resource/PageDownloadCompDetail.xaml.vb"
LIBRARY = "Pages/PageDownload/ModDownloadLib.vb"
MODPACK = "Modules/Minecraft/ModModpack.vb"


class DownloadEntryPointTests(unittest.TestCase):
    def test_no_download_shutdown_flag_or_message_remains(self):
        for path in ROOT.rglob("*.vb"):
            with self.subTest(path=path.relative_to(ROOT)):
                text = path.read_text(encoding="utf-8-sig")
                self.assertNotIn("RestrictMcDownload", text)
                self.assertNotIn("PCL 暂时不再提供 MC 下载功能", text)

    def test_install_page_uses_real_version_list_loader(self):
        init = method(INSTALL, "LoaderInit")
        statements = [
            line.strip()
            for line in init.splitlines()[1:-1]
            if line.strip() and not line.lstrip().startswith("'")
        ]
        self.assertEqual(statements, [
            "ControlInit()",
            "PageLoaderInit(LoadMinecraft, PanLoad, PanAllBack, Nothing, "
            "DlClientListLoader, AddressOf LoadMinecraft_OnFinish)",
        ])

    def test_selected_game_and_components_reach_installer(self):
        selection = method(INSTALL, "GetSelectedComponents", "Function")
        for component in (
            "minecraftVersion", "optiFineEntry", "forgeVersion",
            "neoForgeVersion", "fabricVersion", "fabricApiVersion",
            "optiFabricVersion", "liteLoaderVersion",
        ):
            with self.subTest(component=component):
                self.assertIn(component + ":=", selection)
        self.assertIn("StartInstall(Request)", method(INSTALL, "BtnStart_Click"))
        self.assertIn(
            "If Not McInstallStart(Request) Then Return",
            method(INSTALL, "StartInstall"),
        )

    def test_client_save_and_server_download_actions_remain(self):
        menu = method(LIBRARY, "McDownloadMenuBuild")
        self.assertIn("AddressOf McDownloadMenuSave\n", menu)
        self.assertIn("AddressOf McDownloadMenuSaveServer\n", menu)

    def test_local_modpack_picker_preserves_cancel_and_worker_dispatch(self):
        picker = method(MODPACK, "ModpackInstall")
        first_statement = picker.splitlines()[1].strip()
        self.assertTrue(first_statement.startswith("Dim File As String = Dialogs.SelectFile("))
        self.assertIn('{"rar", "zip", "mrpack"}', picker)
        self.assertIn("If String.IsNullOrEmpty(File) Then Return", picker)
        self.assertIn("RunInThread(", picker)
        self.assertIn("ModpackInstall(File)", picker)
        self.assertIn("ex.ThrowIfCanceled()", picker)

    def test_all_local_modpack_formats_dispatch_and_archive_is_disposed(self):
        dispatch = method(MODPACK, "ModpackInstall", "Function")
        self.assertRegex(dispatch, r"'执行对应的安装方法\s+Select Case PackType")
        installers = {
            "0": "InstallPackCurseForge", "1": "InstallPackHMCL",
            "2": "InstallPackMMC", "3": "InstallPackMCBBS",
            "4": "InstallPackModrinth", "9": "InstallPackLauncherPack",
            "Else": "InstallPackCompress",
        }
        for case, installer in installers.items():
            with self.subTest(installer=installer):
                self.assertRegex(
                    dispatch,
                    rf"Case {case}\s+[^\n]*\n\s+Return {installer}\(",
                )
        self.assertIn("Finally\n            If Archive IsNot Nothing Then Archive.Dispose()", dispatch)

    def test_online_modpacks_offer_install_and_save_other_resources_save_only(self):
        self.assertRegex(
            source(DETAIL),
            r"If TargetResourceType = ResourceTypes\.ModPack Then\s+"
            r"Stack\.Children\.Add\(Version\.ToListItem\(AddressOf Install_Click, "
            r"AddressOf Save_Click, IsBadDisplay:=HasDuplicates\)\)\s+Else\s+"
            r"Stack\.Children\.Add\(Version\.ToListItem\(AddressOf Save_Click, "
            r"IsBadDisplay:=HasDuplicates\)\)\s+End If",
        )
        install = method(DETAIL, "Install_Click")
        self.assertIn("If String.IsNullOrEmpty(InstanceName) Then Return", install)
        self.assertIn('New LoaderDownload("下载整合包文件"', install)
        self.assertIn("Sub() ModpackInstall(Target, InstanceName,", install)
        self.assertIn("McInstallFailedClearFolder(MyLoader)", install)

    def test_drag_drop_preserves_cancel_and_non_modpack_fallback(self):
        self.assertRegex(
            source("FormMain.xaml.vb"),
            r"ModpackInstall\(FilePath\)\s+"
            r"RunInUi\(Sub\(\) FrmMain\.PageChange\(FormMain\.PageType\.TaskManager\)\)\s+"
            r"Return\s+Catch ex As Exception\s+If ex\.IsCanceled Then Return\s+"
            r"'安装失败，继续往后尝试",
        )

    def test_modify_page_exposes_minecraft_and_preserves_modification_flow(self):
        init = method(MODIFY, "LoadInstanceFinished")
        self.assertIn("CardMinecraft.Visibility = Visibility.Visible\n", init)
        self.assertIn("PrepareSelectPage()", init)
        self.assertIn("InitialTarget = GetSelectedComponents()", init)
        self.assertIn("McModificationStart(Request, TargetInstance)", method(MODIFY, "StartInstall"))

    def test_indirect_modpack_entry_points_remain(self):
        callers = {
            "Pages/PageDownload/Resource/PageResource.xaml.vb": "ModpackInstall()",
            "Modules/ModEvent.vb": "RunInUi(Sub() ModpackInstall())",
            "Pages/PageLaunch/PageLaunchLeft.xaml.vb": "ModpackInstall(PackInstallPath)",
            MODPACK: "ModpackInstall(ModpackFile)",
        }
        for path, call in callers.items():
            with self.subTest(path=path):
                self.assertIn(call, source(path))

    def test_release_and_snapshot_changelogs_describe_restoration(self):
        self.assertEqual(
            source("FormMain.xaml.vb").count(
                "恢复：Minecraft 下载、整合包安装，以及已安装实例的 MC 版本修改"
            ),
            2,
        )


if __name__ == "__main__":
    unittest.main()
