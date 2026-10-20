"""Static checks for third-party release identification and retained attribution."""

from pathlib import Path
import unittest
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "Plain Craft Launcher 2"
XAML_NAME = "{http://schemas.microsoft.com/winfx/2006/xaml}Name"
REPOSITORY = "https://github.com/zhaibingye/PCL-Download"
PRODUCT = "Plain Craft Launcher (PCL) Download 修改版"


class ReleaseIdentityTests(unittest.TestCase):
    def test_window_and_visible_title_identify_modified_edition(self):
        window = ET.parse(APP / "FormMain.xaml").getroot()
        self.assertEqual(window.attrib["Title"], PRODUCT)
        self.assertTrue(any(
            element.attrib.get("Text") == "Download 修改版"
            for element in window.iter()
        ))

    def test_assembly_metadata_identifies_third_party(self):
        metadata = (APP / "My Project/AssemblyInfo.vb").read_text(encoding="utf-8-sig")
        self.assertIn(f'AssemblyTitle("{PRODUCT}")', metadata)
        self.assertIn(f'AssemblyProduct("{PRODUCT}")', metadata)
        self.assertIn("第三方 Minecraft 启动器，非 PCL 官方版本", metadata)
        self.assertIn("Copyright © 成都瓜皮龙科技有限公司", metadata)

    def test_about_page_discloses_independent_modification(self):
        about = ET.parse(APP / "Pages/PageOther/PageOtherAbout.xaml").getroot()
        item = next(element for element in about.iter()
                    if element.attrib.get(XAML_NAME) == "ItemAboutPcl")
        self.assertEqual(item.attrib["Title"], "PCL Download 修改版")
        self.assertIn("第三方独立修改版", item.attrib["Info"])
        self.assertIn("不是 PCL 官方版本", item.attrib["ToolTip"])
        self.assertIn(REPOSITORY, item.attrib["ToolTip"])
        self.assertTrue(any(
            element.attrib.get("Text") == "修改版源码"
            and REPOSITORY in element.attrib.values()
            for element in about.iter()
        ))

    def test_original_author_and_sponsor_link_remain_first(self):
        about = ET.parse(APP / "Pages/PageOther/PageOtherAbout.xaml").getroot()
        first_card = next(element for element in about.iter()
                          if element.attrib.get("Title") == "关于")
        people = [element for element in first_card.iter()
                  if element.tag.endswith("MyListItem")]
        self.assertEqual(people[0].attrib["Title"], "龙腾猫跃")
        self.assertEqual(people[0].attrib["Grid.Row"], "0")
        self.assertTrue(any(
            element.attrib.get("Grid.Row") == "0"
            and "https://meloong.com/afd/a/LTCat" in element.attrib.values()
            for element in first_card.iter()
        ))

    def test_readme_identifies_third_party_and_links_license(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8-sig")
        self.assertTrue(readme.startswith("# " + PRODUCT))
        self.assertIn("第三方基于", readme)
        self.assertIn("不是 PCL 官方版本", readme)
        self.assertIn("[LICENCE](LICENCE)", readme)

    def test_assembly_identity_preserves_resource_uris(self):
        namespace = {"m": "http://schemas.microsoft.com/developer/msbuild/2003"}
        project = ET.parse(APP / "Plain Craft Launcher 2.vbproj")
        self.assertEqual(
            project.find(".//m:AssemblyName", namespace).text,
            "Plain Craft Launcher 2",
        )


if __name__ == "__main__":
    unittest.main()
