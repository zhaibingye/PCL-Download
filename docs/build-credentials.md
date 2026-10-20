# 构建时注入配置

公开源码中的微软 Client ID 和 CurseForge API Key 默认值均为空。当前源码不保留旧 Client ID，但不会改写已经发布的 Git 历史。

## GitHub Actions

在仓库的 Actions Secrets 中配置：

- `PCL_MS_CLIENT_ID`：微软应用的 Client ID（UUID）。
- `CURSEFORGE_API_KEY`：合法获取的 CurseForge API Key。

默认分支的 push / 手动构建会要求两个值均有效，缺失或格式不合法就停止，不上传缺少配置的产物。PR 及其他分支不注入这些值，仍可构建不含默认凭据的版本。

工作流仅在生成与校验步骤中通过环境变量传值。Python 生成脚本逐字处理 `$` 等字符，并正确转义 VB 字符串，不把值拼入 shell 命令。生成文件为已被 Git 忽略的 `Plain Craft Launcher 2/obj/PrivateBuildCredentials.g.vb`。构建后在 Windows PowerShell 中以只读反射校验 EXE 内的两个常量，不运行启动器、不发起登录/API 请求，也不输出常量值。后续清理步骤使用 `always()`，即使构建或校验失败也删除生成源文件；仅在成功时上传 EXE，不上传生成源码、PDB、日志或整个工作目录。

嵌入 EXE 的值能够被提取，公开二进制不能保证 API Key 保密。Actions Secrets 和此流程只避免它们出现在公开源码和正常构建日志中。不要上传包含凭据的源码、诊断日志或缓存；不要在本流程上开启详细 MSBuild 日志或二进制日志。

## 运行时覆盖与本机构建

运行时仍支持 `PCL_MS_CLIENT_ID` 和原有的 `PCL_CURSEFORGE_API_KEY`；也可使用 `PCL_CF_API_KEY`，但原有的长名称优先。运行时变量未设置时使用编译进去的默认值。

本机构建可在私有进程环境中设置 `PCL_MS_CLIENT_ID` 和 `PCL_CF_API_KEY`，执行：

```text
python .github/scripts/build_credentials.py
```

然后按原流程编译。无论编译是否成功，都执行：

```text
python .github/scripts/build_credentials.py --clean
```

不要把值放在命令行或提交到文件。未运行生成脚本的普通源码构建使用空默认值，需要自行配置运行时变量。

## 本次附带保护

CurseForge 鉴权头只添加到 HTTPS 的 `api.curseforge.com` 和 `forgecdn.net` 域名及其子域名，避免原有 URL 子串匹配误把凭据发送到相似域名或 URL 路径。保留 CDN 鉴权，因为 CurseForge 下载接口也需要 API Key。

该检查针对初始请求；现有 HTTP 客户端仍自动跟随重定向，跨域重定向可能保留自定义鉴权头。本次不改写下载重定向逻辑，因此这不是完整的凭据隔离方案。
