# Simple static file server for preview.html (no Python/Node needed)
# Usage: powershell -ExecutionPolicy Bypass -File serve.ps1 [-Port 8123]
param([int]$Port = 8123)

$root = $PSScriptRoot
$listener = New-Object System.Net.HttpListener
$listener.Prefixes.Add("http://localhost:$Port/")
$listener.Start()
Write-Host "Serving $root at http://localhost:$Port/preview.html"

$types = @{
  '.html' = 'text/html; charset=utf-8'; '.css' = 'text/css; charset=utf-8'
  '.js' = 'application/javascript; charset=utf-8'; '.json' = 'application/json; charset=utf-8'
  '.png' = 'image/png'; '.webp' = 'image/webp'; '.jpg' = 'image/jpeg'; '.svg' = 'image/svg+xml'
}

while ($listener.IsListening) {
  $ctx = $listener.GetContext()
  $res = $ctx.Response
  try {
    $rel = [Uri]::UnescapeDataString($ctx.Request.Url.AbsolutePath.TrimStart('/'))
    if ($rel -eq '') { $rel = 'preview.html' }
    if ($rel -eq 'posts/index.json') {
      $names = @(Get-ChildItem (Join-Path $root 'posts') -Filter *.json |
        Where-Object { $_.Name -ne 'index.json' } | Sort-Object LastWriteTime -Descending |
        ForEach-Object { $_.BaseName })
      $bytes = [Text.Encoding]::UTF8.GetBytes((ConvertTo-Json -InputObject $names -Compress))
      $res.ContentType = $types['.json']
    } else {
      $path = [IO.Path]::GetFullPath((Join-Path $root $rel))
      if (-not $path.StartsWith($root) -or -not (Test-Path $path -PathType Leaf)) {
        $res.StatusCode = 404; $bytes = [Text.Encoding]::UTF8.GetBytes('Not found')
      } else {
        $bytes = [IO.File]::ReadAllBytes($path)
        $ext = [IO.Path]::GetExtension($path).ToLower()
        $res.ContentType = if ($types[$ext]) { $types[$ext] } else { 'application/octet-stream' }
      }
    }
    $res.Headers.Add('Cache-Control', 'no-store')
    $res.OutputStream.Write($bytes, 0, $bytes.Length)
  } catch {
    $res.StatusCode = 500
  } finally {
    $res.Close()
  }
}
