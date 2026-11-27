# 오늘의 두더지 캐러셀 렌더러
# 사용법: powershell -ExecutionPolicy Bypass -File render.ps1 -Content posts\sample.json
# 결과: out\<json 파일 이름>\01.png, 02.png ... (1080x1350, 4:5)
#
# 텍스트 서식: [[강조]] -> 노란/빨간 강조,  **굵게** -> 빨간 굵은 글씨,  줄바꿈은 배열로 나눠서 입력

param(
  [Parameter(Mandatory = $true)][string]$Content,
  [string]$Browser = ""
)

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot

if (-not $Browser) {
  $candidates = @(
    "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
    "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe",
    "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe"
  )
  $Browser = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
  if (-not $Browser) { throw 'Chrome 또는 Edge를 찾을 수 없습니다.' }
}

function Format-Text([string]$s) {
  if ($null -eq $s) { return '' }
  $s = [System.Net.WebUtility]::HtmlEncode($s)
  $s = [regex]::Replace($s, '\[\[(.+?)\]\]', '<em>$1</em>')
  $s = [regex]::Replace($s, '\*\*(.+?)\*\*', '<b>$1</b>')
  return $s
}

function Join-Lines($lines) {
  if ($lines -is [array]) { return (($lines | ForEach-Object { Format-Text $_ }) -join '<br>') }
  return (Format-Text $lines)
}

function Get-Head([int]$i, [int]$total) {
  return @"
<div class="head">
  <div class="logo"></div>
  <div class="brand">오늘의 <span>두더지</span></div>
  <div class="page">$i / $total</div>
</div>
"@
}

$contentPath = (Resolve-Path $Content).Path
$data = Get-Content -Raw -Encoding UTF8 $contentPath | ConvertFrom-Json
$name = [IO.Path]::GetFileNameWithoutExtension($contentPath)
$outDir = Join-Path $root "out\$name"
$buildDir = Join-Path $root "build\$name"
New-Item -ItemType Directory -Force $outDir, $buildDir | Out-Null

$handle = if ($data.handle) { $data.handle } else { '@today_dudeoji' }
$cards = @($data.cards)
$total = $cards.Count

for ($n = 0; $n -lt $total; $n++) {
  $c = $cards[$n]
  $i = $n + 1
  switch ($c.type) {
    'cover' {
      $inner = @"
<div class="card cover">
  <div class="art"></div>
  <div class="panel">
    <div class="tag">$(Format-Text $c.tag)</div>
    <h1>$(Join-Lines $c.title)</h1>
    <div class="sub">$(Join-Lines $c.sub)</div>
  </div>
  <div class="foot"><span>$(Format-Text $handle)</span><span class="swipe">넘겨보기 →</span></div>
</div>
"@
    }
    'body' {
      $list = ''
      if ($c.items) {
        $list = '<div class="items">' + (($c.items | ForEach-Object {
          "<div class=`"item`"><div class=`"num`">$(Format-Text $_.num)</div><div><div class=`"t`">$(Join-Lines $_.title)</div><div class=`"d`">$(Join-Lines $_.desc)</div></div></div>"
        }) -join '') + '</div>'
      }
      if ($c.bullets) {
        $list += '<ul class="bullets">' + (($c.bullets | ForEach-Object { "<li>$(Format-Text $_)</li>" }) -join '') + '</ul>'
      }
      $inner = @"
<div class="card body">
  $(Get-Head $i $total)
  <div class="inner">
    <div class="label">$(Format-Text $c.label)</div>
    <h2>$(Join-Lines $c.heading)</h2>
    $list
  </div>
  <div class="foot-handle">$(Format-Text $handle)</div>
</div>
"@
    }
    'checklist' {
      $checks = ($c.items | ForEach-Object { "<li><span class=`"box`"></span><span>$(Format-Text $_)</span></li>" }) -join ''
      $inner = @"
<div class="card checklist">
  $(Get-Head $i $total)
  <div class="inner">
    <div class="label">$(Format-Text $c.label)</div>
    <h2>$(Join-Lines $c.heading)</h2>
    <ul class="checks">$checks</ul>
    <div class="save-note"><span>$(Format-Text $c.note)</span></div>
  </div>
  <div class="foot-handle">$(Format-Text $handle)</div>
</div>
"@
    }
    'follow' {
      $inner = @"
<div class="card follow">
  <div class="top">$(if ($c.top) { Format-Text $c.top } else { Format-Text '[[내 돈·생활 이슈]], 두더지가 캐드려요' })</div>
  <div class="art"></div>
  <div class="bottom">$(Format-Text $handle)</div>
</div>
"@
    }
    default { throw "알 수 없는 카드 type: $($c.type)" }
  }

  $html = @"
<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<link rel="stylesheet" href="../../template/style.css">
</head><body>
$inner
</body></html>
"@
  $file = Join-Path $buildDir ('{0:D2}.html' -f $i)
  [IO.File]::WriteAllText($file, $html, (New-Object System.Text.UTF8Encoding($false)))

  $png = Join-Path $outDir ('{0:D2}.png' -f $i)
  $url = 'file:///' + ($file -replace '\\', '/')
  $chromeArgs = @('--headless=new', '--disable-gpu', '--hide-scrollbars', '--force-device-scale-factor=1',
            '--window-size=1080,1350', '--virtual-time-budget=8000', '--allow-file-access-from-files',
            "--screenshot=`"$png`"", "`"$url`"")
  Start-Process -FilePath $Browser -ArgumentList $chromeArgs -Wait -WindowStyle Hidden | Out-Null
  if (-not (Test-Path $png)) { throw "렌더링 실패: 카드 $i" }
  Write-Output "카드 $i/$total -> $png"
}
