# Installs alchem from a GitHub release on Windows:
#
#   irm https://raw.githubusercontent.com/SmithOperatingSolutions/alchem/main/install.ps1 | iex
#
# $env:ALCHEM_VERSION picks a release (the latest by default) and
# $env:ALCHEM_INSTALL_DIR the directory for alchem.exe
# (%LOCALAPPDATA%\Programs\alchem by default), which is added to the user's
# PATH. The download is checked against the release's checksums.txt before
# anything is installed. Go is not needed: alchem downloads the Go release it
# builds with on first use.
$ErrorActionPreference = 'Stop'

$repository = 'SmithOperatingSolutions/alchem'
$base = if ($env:ALCHEM_RELEASES_URL) { $env:ALCHEM_RELEASES_URL } else { "https://github.com/$repository/releases" }
$installDir = if ($env:ALCHEM_INSTALL_DIR) { $env:ALCHEM_INSTALL_DIR } else { Join-Path $env:LOCALAPPDATA 'Programs\alchem' }

$arch = switch ($env:PROCESSOR_ARCHITECTURE) {
    'AMD64' { 'amd64' }
    'ARM64' { 'arm64' }
    default { throw "alchem install: no release for the $($env:PROCESSOR_ARCHITECTURE) processor" }
}

$version = $env:ALCHEM_VERSION
if (-not $version) {
    # releases/latest redirects to the latest release's tag, which avoids the
    # API and its limit on requests from shared addresses.
    $response = Invoke-WebRequest -UseBasicParsing -Uri "$base/latest"
    $final = if ($response.BaseResponse.ResponseUri) { $response.BaseResponse.ResponseUri.AbsoluteUri } else { $response.BaseResponse.RequestMessage.RequestUri.AbsoluteUri }
    $version = ($final -split '/')[-1]
    if ($version -notmatch '^v[0-9]') { throw 'alchem install: could not find the latest release' }
}
if (-not $version.StartsWith('v')) { $version = "v$version" }

$name = "alchem_${version}_windows_$arch"
$archive = "$name.zip"
$work = Join-Path ([System.IO.Path]::GetTempPath()) ("alchem-install-" + [System.Guid]::NewGuid())
New-Item -ItemType Directory -Path $work | Out-Null
try {
    Write-Host "Downloading alchem $version for windows/$arch"
    Invoke-WebRequest -UseBasicParsing -Uri "$base/download/$version/$archive" -OutFile (Join-Path $work $archive)
    Invoke-WebRequest -UseBasicParsing -Uri "$base/download/$version/checksums.txt" -OutFile (Join-Path $work 'checksums.txt')

    $line = Get-Content (Join-Path $work 'checksums.txt') | Where-Object { $_ -match " $([regex]::Escape($archive))$" } | Select-Object -First 1
    if (-not $line) { throw "alchem install: checksums.txt has no entry for $archive" }
    $expected = ($line -split '\s+')[0].ToLowerInvariant()
    $actual = (Get-FileHash -Algorithm SHA256 (Join-Path $work $archive)).Hash.ToLowerInvariant()
    if ($actual -ne $expected) { throw "alchem install: checksum mismatch for ${archive}: expected $expected, got $actual" }

    Expand-Archive -Path (Join-Path $work $archive) -DestinationPath $work
    New-Item -ItemType Directory -Force -Path $installDir | Out-Null
    Copy-Item -Force (Join-Path $work "$name\alchem.exe") (Join-Path $installDir 'alchem.exe')
}
finally {
    Remove-Item -Recurse -Force $work -ErrorAction SilentlyContinue
}

$userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
if (-not (($userPath -split ';') -contains $installDir)) {
    [Environment]::SetEnvironmentVariable('Path', (@($userPath, $installDir) -ne '' -join ';'), 'User')
    Write-Host "Added $installDir to your PATH; open a new terminal to use it."
}
$installed = & (Join-Path $installDir 'alchem.exe') version | Select-Object -First 1
Write-Host "Installed $installed to $installDir\alchem.exe"
