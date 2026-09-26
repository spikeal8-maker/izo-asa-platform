param(
    [string]$HostName = $(if ($env:IZO_DEV_CA_PROBE_HOST) { $env:IZO_DEV_CA_PROBE_HOST } else { "openrouter.ai" })
)

$ErrorActionPreference = "Stop"
$runtime = Join-Path (Split-Path -Parent $PSScriptRoot) ".runtime\dev-ca"
$target = Join-Path $runtime "local-root.crt"
New-Item -ItemType Directory -Force $runtime | Out-Null
Remove-Item $target -Force -ErrorAction SilentlyContinue

try {
    $tcp = [Net.Sockets.TcpClient]::new()
    $tcp.Connect($HostName, 443)
    try {
        $ssl = [Net.Security.SslStream]::new($tcp.GetStream(), $false)
        try {
            # Uses the Windows trusted root store. No certificate bypass callback.
            $ssl.AuthenticateAsClient($HostName)
            $leaf = [Security.Cryptography.X509Certificates.X509Certificate2]::new($ssl.RemoteCertificate)
            $chain = [Security.Cryptography.X509Certificates.X509Chain]::new()
            $chain.ChainPolicy.RevocationMode = [Security.Cryptography.X509Certificates.X509RevocationMode]::NoCheck
            if (-not $chain.Build($leaf) -or $chain.ChainElements.Count -lt 1) {
                Write-Host "DEV_CA_BRIDGE: no trusted root exported."
                exit 0
            }
            $root = $chain.ChainElements[$chain.ChainElements.Count - 1].Certificate
            $bytes = $root.Export([Security.Cryptography.X509Certificates.X509ContentType]::Cert)
            $base64 = [Convert]::ToBase64String($bytes, [Base64FormattingOptions]::InsertLineBreaks)
            $pem = "-----BEGIN CERTIFICATE-----" + [Environment]::NewLine + $base64 + [Environment]::NewLine + "-----END CERTIFICATE-----" + [Environment]::NewLine
            [IO.File]::WriteAllText($target, $pem, [Text.Encoding]::ASCII)
            Write-Host ("DEV_CA_BRIDGE: exported trusted root for {0}." -f $HostName)
        } finally {
            if ($ssl) { $ssl.Dispose() }
        }
    } finally {
        $tcp.Dispose()
    }
} catch {
    Write-Host ("DEV_CA_BRIDGE: Windows TLS probe unavailable; using container system CA only. {0}" -f $_.Exception.GetType().Name)
    exit 0
}
