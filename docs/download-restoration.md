# 下载功能恢复说明

本补丁是基于 PCL 的第三方修改，供 PCL-Download 仓库审阅和测试；不是上游官方更新。

## 对照与范围

- 用户指定的上游版本：[2.13.1.1](https://github.com/Meloong-Git/PCL/releases/tag/2.13.1.1)，标签提交为 `0ce35fe7e5cb939500ef754ff177b082927374ad`。
- 修改基于 PCL-Download 的 `6b9a50df911c9d68b69b24c979efba477fb14b67`（2.99.0.0 正式版）。
- 最近关闭下载功能的源码提交为 `e4b0489a22cfd4bc57a18fc1e2ac66d5c18e7fc1`，它新增了 `RestrictMcDownload` 及各入口的限制。
- 恢复该提交关闭的入口，保留 2.14.0.0 引入的组件安装和实例修改实现，不整库退回旧版本。
- 2.13.1.1 已有的下载实现仍在当前源码中；实例 MC 版本修改是 2.14 新增的功能，本次也恢复其被关闭的入口。

## 恢复内容

1. 安装页面加载真实 Minecraft 版本列表，可进入原版及兼容组件组合安装，并访问原有的客户端另存为和服务端下载菜单。
2. 本地整合包选择、拖入安装，以及共用安装方法的自定义事件、启动时自动安装和带启动器整合包递归安装。
3. CurseForge、HMCL、MMC、MCBBS、Modrinth、带启动器整合包及普通压缩包原有分流。
4. 在线整合包版本的默认安装操作，同时保留另存为；Mod、资源包、光影包等非整合包资源保持保存操作。
5. 已安装实例修改页面的 Minecraft 版本选择。
6. 正式版和快照版的更新说明，不再显示“暂时不再提供 MC 下载功能”。

未修改网络下载源、微软登录、CurseForge API Key 配置、文件校验、正版购买劝导、赞助劝导或主题。第三方 API 仍需项目原有的合法配置。

## 自动检查

在仓库根目录运行（Python 3，无第三方 Python 依赖）：

```shell
python -m unittest discover -s tests -v
git diff --check
```

测试检查的是 VB 源码入口和回调连接，不能替代编译、WPF 交互和真实联网安装。已有 Windows Build 工作流现在会在构建前执行这些检查。

Windows 完整构建沿用 `.github/workflows/build.yml`：

```shell
git submodule update --init --recursive
dotnet restore PCLCS/PCLCS.csproj
msbuild "Plain Craft Launcher 2/Plain Craft Launcher 2.vbproj" -p:Configuration=Debug
msbuild "Plain Craft Launcher 2/Plain Craft Launcher 2.vbproj" -p:Configuration=Release
```

需要 Windows、.NET Framework 4.8 开发工具和 MSBuild；构建时仍按原工作流准备帮助资源及所需配置。

## Windows 手动验收

使用单独的测试游戏目录和测试实例；修改已有实例前备份存档。

- 打开下载页，确认版本列表成功、网络失败和重试均能正常处理；反复进入、返回、刷新。
- 安装一个原版版本，再分别测试兼容的 Forge、NeoForge、Fabric、OptiFine、LiteLoader 组合；确认取消任务后可以重试。
- 测试 Minecraft 客户端另存为及存在服务端文件的版本下载；检查不支持服务端的版本提示。
- 在线整合包分别测试安装、另存为和取消名称输入；确认普通 Mod、资源包、光影包等仍为保存操作。
- 本地分别测试已知格式整合包、取消文件选择、损坏压缩包和不支持的 RAR；测试文件拖入及非整合包的错误报告识别。
- 测试自定义导入事件、启动目录的 `modpack.zip` / `modpack.mrpack` 和含内部整合包的启动器压缩包。
- 修改测试实例的 Minecraft 版本和兼容组件；检查警告、取消、任务失败、成功后重新进入页面及启动。

## 发布提示

保留仓库的 `LICENCE`。发布二次创作产物前，应按其要求核对第三方标识、名称后缀、关于页原作者首位署名及赞助链接、源码公开、正版购买和赞助劝导，以及默认蓝色主题等要求。

本补丁不更新仓库中的历史二进制补丁或 `最新正式版.zip`；这些文件仍是原版本，不能作为本次恢复后的可执行文件交付。新构建须在 Windows 验证后另行生成。
