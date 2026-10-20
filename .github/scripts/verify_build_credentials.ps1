param(
    [Parameter(Mandatory = $true)]
    [string]$AssemblyPath
)

$ErrorActionPreference = 'Stop'
try {
    # Run with Windows PowerShell 5.1. Reflection-only loading never executes
    # application startup, network requests or module initializers.
    $bytes = [System.IO.File]::ReadAllBytes((Resolve-Path -LiteralPath $AssemblyPath).Path)
    $assembly = [System.Reflection.Assembly]::ReflectionOnlyLoad($bytes)
    $type = $assembly.GetType('PCL.BuildCredentials', $true)
    $flags = [System.Reflection.BindingFlags]'Static, Public, NonPublic'
    $expected = @{
        MicrosoftClientId = $env:PCL_MS_CLIENT_ID
        CurseForgeApiKey = $env:PCL_CF_API_KEY
    }
    foreach ($name in $expected.Keys) {
        $field = $type.GetField($name, $flags)
        if ([string]::IsNullOrEmpty($expected[$name]) -or
            $null -eq $field -or -not $field.IsLiteral -or
            -not [StringComparer]::Ordinal.Equals($field.GetRawConstantValue(), $expected[$name])) {
            throw 'Compiled credential mismatch.'
        }
    }
    Write-Host 'Both compiled credential defaults match the configured secrets.'
} catch {
    # Never print the exception, compiled values, expected values or source.
    Write-Error 'Compiled credential verification failed; values are not logged.'
    exit 1
}
