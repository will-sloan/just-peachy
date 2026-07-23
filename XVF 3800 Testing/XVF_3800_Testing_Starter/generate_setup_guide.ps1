$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot
$OutputPath = Join-Path $ProjectRoot "XVF3800_Install_and_Test_Guide.docx"

$html = @'
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>XVF3800 Windows Installation and Testing Guide</title>
<style>
body { font-family: Calibri, Arial, sans-serif; font-size: 10.5pt; color: #202020; line-height: 1.18; }
h1 { color: #17365d; font-size: 18pt; border-bottom: 1px solid #9fbad0; padding-top: 10pt; }
h2 { color: #1f4e79; font-size: 14pt; padding-top: 6pt; }
h3 { color: #1f4e79; font-size: 11.5pt; }
pre { font-family: Consolas, "Courier New", monospace; font-size: 8.5pt; background: #eef3f7; border: 1px solid #c5d5e2; padding: 7pt; white-space: pre-wrap; }
li { margin-bottom: 3pt; }
table { border-collapse: collapse; width: 100%; }
th, td { border: 1px solid #8ea9bd; padding: 5pt; vertical-align: top; }
th { background: #d9eaf7; }
.note { background: #fff2cc; border-left: 4px solid #e6b800; padding: 7pt; }
.success { background: #e2f0d9; border-left: 4px solid #70ad47; padding: 7pt; }
.small { font-size: 9pt; color: #555555; }
</style>
</head>
<body>
<h1>XVF3800 Windows Installation and Testing Guide</h1>
<p><b>Purpose:</b> Install, configure, verify, and test the XVF3800 Windows project on another computer after copying or cloning the complete <code>just-peachy</code> folder.</p>
<p class="small">Generated: __GENERATED_DATE__</p>

<div class="note"><b>Important:</b> The XMOS binary and source-release folders may not be included in GitHub because of licensing or repository-size rules. If they are absent after cloning, copy them separately into the <code>XVF 3800 Testing</code> folder before running setup. Setup cannot download or invent vendor files.</div>

<h2>1. Copy the complete project</h2>
<p>Preserve this folder structure. The exact outer location can be different on the new computer.</p>
<pre>just-peachy\\
  XVF 3800 Testing\\
    SampleAudio\\test.wav
    XVF3800-Binary_v3_2_1\\...
    xvf3800_source_external_...\\sources\\...
    XVF_3800_Testing_Starter\\
      setup_environment.ps1
      config.example.json
      xvf_test_runner.py
      test_profiles\\</pre>
<ul>
<li>Do not depend on copying the old <code>.venv</code>. The setup script creates a local environment for the new computer.</li>
<li>Use <code>SampleAudio\\test.wav</code> or another approved mono WAV. Do not overwrite personal recordings.</li>
<li>Connect the XVF3800 over USB and install its Windows audio/control drivers.</li>
<li>This project does not flash firmware.</li>
</ul>

<h2>2. Open PowerShell in the starter project</h2>
<p>Open a VS Code PowerShell terminal. Replace the example location with the actual location on the new computer. Keep the quotes because the path contains spaces.</p>
<pre>Set-Location "C:\\Users\\&lt;your-user&gt;\\Documents\\GitHub\\just-peachy\\XVF 3800 Testing\\XVF_3800_Testing_Starter"
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
Get-Location
Get-ChildItem</pre>
<p><b>Expected:</b> <code>Get-Location</code> prints the starter directory, and the listing includes <code>setup_environment.ps1</code>, <code>requirements.txt</code>, <code>config.example.json</code>, <code>xvf_test_runner.py</code>, and the <code>run_*.ps1</code> scripts.</p>

<h2>3. Verify Python 3.10</h2>
<p>The project requires Python 3.10 because the XMOS release Python tools are built and tested for that version. Do not use the Microsoft Store alias or a random global <code>python</code> command.</p>
<pre>py -0p
py -3.10 --version</pre>
<p><b>Expected:</b> the second command reports <code>Python 3.10.x</code>. If it fails, install Python 3.10 for Windows with the Python Launcher enabled, then reopen PowerShell. Stop until this command works.</p>

<h2>4. Create the local environment and discover paths</h2>
<pre>.\setup_environment.ps1</pre>
<p>The setup script verifies Python, creates or repairs <code>.venv</code>, installs <code>requirements.txt</code>, searches for <code>xvf_host.exe</code> and <code>xvf_tools.py</code>, discovers the XMOS tuning module, and normalizes <code>config.json</code> to portable project-relative paths. It backs up an existing config and moves stale virtual environments to timestamped backups.</p>
<pre>Python 3.10.x
Discovered xvf_host.exe: ...\\XVF3800-Binary_v3_2_1\\...\\xvf_host.exe
Discovered xvf_tools.py: ...\\xvf3800_source_external_...\\sources\\xvf_tools.py
Normalized config.json to portable project-relative paths.
Environment ready: ...\\XVF_3800_Testing_Starter\\.venv\\Scripts\\python.exe</pre>
<p>If setup stops, read the error literally. Common causes are missing Python 3.10, missing XMOS release files, multiple ambiguous release copies, or a missing tuning module.</p>

<h2>5. Verify the Python environment and imports</h2>
<pre>&amp; ".\.venv\Scripts\python.exe" --version
&amp; ".\.venv\Scripts\python.exe" -c "import sys; print(sys.executable); print(sys.version)"
&amp; ".\.venv\Scripts\python.exe" -c "import numpy; print('numpy', numpy.__version__)"
&amp; ".\.venv\Scripts\python.exe" -c "import scipy; print('scipy', scipy.__version__)"
&amp; ".\.venv\Scripts\python.exe" -c "import sounddevice; print('sounddevice', sounddevice.__version__)"
&amp; ".\.venv\Scripts\python.exe" -c "import soundfile; print('soundfile', soundfile.__version__)"
&amp; ".\.venv\Scripts\python.exe" -c "import matplotlib; print('matplotlib', matplotlib.__version__)"
&amp; ".\.venv\Scripts\python.exe" ".\xvf_test_runner.py" --help</pre>
<p><b>Expected:</b> the executable path contains the current project <code>.venv</code>; all imports print versions; and <code>--help</code> prints the runner commands without a traceback. NumPy must remain below version 2 because the XMOS packer is incompatible with NumPy 2.x.</p>

<h2>6. Verify config.json and resolved files</h2>
<pre>Get-Content -Raw ".\config.json"
&amp; ".\.venv\Scripts\python.exe" -c "import json; from pathlib import Path; print(json.dumps(json.loads(Path('config.json').read_text(encoding='utf-8')), indent=2))"
&amp; ".\.venv\Scripts\python.exe" -c "from pathlib import Path; import xvf_test_runner as r; c=r.load_config(Path('config.json')); print('workspace_root=', c.workspace_root); print('xvf_host_path=', c.xvf_host_path); print('xvf_tools_path=', c.xvf_tools_path); print('python_executable=', c.python_executable); r.verify_paths(c, require_tools=True); print('all_configured_paths_ok')"</pre>
<p><b>Expected:</b> the config uses relative values such as <code>..</code>, <code>../XVF3800-Binary_v3_2_1/...</code>, <code>../xvf3800_source_external_.../...</code>, and <code>.venv/Scripts/python.exe</code>. The final command prints <code>all_configured_paths_ok</code>.</p>

<h2>7. Verify Windows audio devices</h2>
<pre>&amp; ".\.venv\Scripts\python.exe" ".\xvf_test_runner.py" devices --config ".\config.json"</pre>
<p>The output lists every PortAudio device and then prints the selected XVF3800 input/output pair.</p>
<div class="success"><b>Expected:</b> both selected names contain <code>XVF3800 Voice Processor</code>. The input supports two channels, the output supports two channels, and the runner does not silently choose the normal PC microphone or speakers. Device indices can differ between computers.</div>

<h2>8. Verify xvf_host.exe, firmware, and USB control</h2>
<pre>$config = Get-Content -Raw ".\config.json" | ConvertFrom-Json
$projectRoot = (Get-Location).Path
$xvfHostPath = (Resolve-Path (Join-Path $projectRoot $config.xvf_host_path)).Path
Test-Path -LiteralPath $xvfHostPath
&amp; $xvfHostPath --help
&amp; $xvfHostPath --list-commands
&amp; $xvfHostPath --use usb VERSION
&amp; $xvfHostPath --use usb AEC_NUM_MICS
&amp; $xvfHostPath --use usb USB_BIT_DEPTH</pre>
<p><b>Expected:</b> <code>Test-Path</code> returns <code>True</code>; help and command-list calls exit successfully; firmware reports <code>3 2 1</code> for this release; <code>AEC_NUM_MICS</code> reports <code>4</code>; and <code>USB_BIT_DEPTH</code> reports <code>16 16</code>. Record these outputs before changing routing or packed settings.</p>

<h2>9. Verify the XMOS Python tools</h2>
<pre>$config = Get-Content -Raw ".\config.json" | ConvertFrom-Json
$projectRoot = (Get-Location).Path
$xvfToolsPath = (Resolve-Path (Join-Path $projectRoot $config.xvf_tools_path)).Path
$xmosPythonPath = (Resolve-Path (Join-Path $projectRoot $config.xmos_pythonpath)).Path
$oldPythonPath = $env:PYTHONPATH
try {
    $env:PYTHONPATH = $xmosPythonPath
    &amp; ".\.venv\Scripts\python.exe" $xvfToolsPath packing --command-help
    if ($LASTEXITCODE -ne 0) { throw "packing help failed with exit code $LASTEXITCODE" }
    &amp; ".\.venv\Scripts\python.exe" $xvfToolsPath packed_recorder --command-help
    if ($LASTEXITCODE -ne 0) { throw "packed_recorder help failed with exit code $LASTEXITCODE" }
    &amp; ".\.venv\Scripts\python.exe" $xvfToolsPath doa_plot --command-help
    if ($LASTEXITCODE -ne 0) { throw "doa_plot help failed with exit code $LASTEXITCODE" }
} finally {
    if ($null -eq $oldPythonPath) { Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue } else { $env:PYTHONPATH = $oldPythonPath }
}</pre>
<p><b>Expected:</b> all three commands print usage information and exit with code 0. The temporary <code>PYTHONPATH</code> must point to the tuning module inside the copied XMOS source release. Do not install an unrelated PyPI package named <code>tuning</code>.</p>

<h1>Testing workflow</h1>
<h2>10. Run the baseline test</h2>
<pre>.\run_baseline.ps1</pre>
<p><b>Expected:</b> the command prints <code>Completed</code> and creates a timestamped folder under the parent <code>XVF 3800 Testing\runs</code> directory.</p>
<pre>$latestRun = Get-ChildItem "..\runs" -Directory | Sort-Object LastWriteTime -Descending | Select-Object -First 1
$latestRun.FullName
Get-ChildItem -LiteralPath $latestRun.FullName -Recurse -File | Select-Object FullName</pre>
<p>The baseline folder should contain <code>metadata.json</code>, firmware and parameter snapshots, <code>config_snapshot.json</code>, command logs, stdout/stderr logs, environment data, and pip-freeze data.</p>

<h2>11. Run the six-output packed capture</h2>
<pre>.\run_packed_capture.ps1 -Duration 10</pre>
<p>The terminal prints <code>Starting packed six-output recording...</code> immediately before the recorder starts.</p>
<p>This records two 48 kHz USB channels and unpacks six internal 16 kHz signals. The confirmed output mapping is:</p>
<table><tr><th>File</th><th>Signal</th></tr>
<tr><td>01_far_end_reference.wav</td><td>Far-end/reference signal</td></tr>
<tr><td>02_processed_auto_selected.wav</td><td>Processed auto-selected beam output</td></tr>
<tr><td>03_amplified_mic0.wav</td><td>Amplified MIC0</td></tr>
<tr><td>04_amplified_mic1.wav</td><td>Amplified MIC1</td></tr>
<tr><td>05_amplified_mic2.wav</td><td>Amplified MIC2</td></tr>
<tr><td>06_amplified_mic3.wav</td><td>Amplified MIC3</td></tr></table>
<pre>$packedRun = Get-ChildItem "..\runs" -Directory | Where-Object Name -like "*packed*" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
Get-ChildItem -LiteralPath (Join-Path $packedRun.FullName "output") -File | Select-Object Name,Length</pre>
<p><b>Expected:</b> the output contains a non-empty raw 48 kHz stereo WAV, a six-channel 16 kHz WAV, six named mono WAV files, telemetry, audio statistics, and logs. Microphone channels should show non-zero audio when sound is present.</p>

<h2>12. Run the automatic speech-recognition capture</h2>
<pre>.\run_asr_capture.ps1 -Duration 10</pre>
<p>This is similar to the six-output capture, but enables <code>AEC_ASROUTONOFF=1</code> and routes category 7/source 3 to the packed auto-selected output. The output file <code>02_asr_processed_auto_selected.wav</code> is the verified automatic speech-recognition output. This is speech processing output, not speaker-identity recognition.</p>
<p><b>Expected:</b> the run metadata records <code>asr_output_enabled: true</code>, <code>AEC_ASROUTONOFF=1</code>, and the ASR packed command. Temporary settings are restored after the run.</p>

<h2>13. Run the default digital mono processed-output test</h2>
<pre>.\run_digital_mono.ps1</pre>
<p>Select a WAV in the file picker, or provide <code>-MonoFile</code> explicitly. By default, this places the same mono signal into MIC0, MIC1, MIC2, and MIC3 and captures the normal non-ASR processed auto-selected output in <code>02_processed_auto_selected.wav</code>. It is valid for data-path, gain, logical routing, normal processed-output, and firmware-regression checks.</p>
<div class="note"><b>Limitation:</b> duplicated mono is not genuine spatial four-microphone data. Do not use it to judge beamforming, Direction of Arrival, dereverberation, microphone geometry, or spatial rejection.</div>

<h2>14. Run the ASR-output version when needed</h2>
<pre>.\run_digital_mono.ps1 `
  -ASROutput</pre>
<p>This uses the same digital mono input but enables <code>AEC_ASROUTONOFF=1</code> and writes the ASR-processed auto-selected waveform to <code>02_asr_processed_auto_selected.wav</code>. This is speech-signal processing output, not speaker-identity recognition.</p>

<h2>15. Run a single substitute-microphone test</h2>
<pre>.\run_digital_mono.ps1 `
  -Mode SingleMic `
  -MicIndex 0</pre>
<p>Repeat with <code>MicIndex</code> 1, 2, or 3 to test the other logical paths. The channel map should show only the selected MIC channel containing the mono input; the other substitute microphones and far-end/reference channel should be silence. Add <code>-ASROutput</code> if the ASR-processed waveform is specifically required.</p>

<h2>16. Repeatability comparison</h2>
<p>Run the duplicate-microphone test twice. Use the two actual run-folder paths printed by the commands:</p>
<pre>&amp; ".\.venv\Scripts\python.exe" ".\xvf_test_runner.py" compare-runs `
  "C:\full\path\to\first_duplicate_run" `
  "C:\full\path\to\second_duplicate_run"</pre>
<p>The comparison reports duration, frame count, peak, RMS, SHA-256, bit-identical status, and maximum absolute sample difference. Hardware output can vary slightly; a non-bit-identical result is reported numerically rather than automatically treated as a failure.</p>

<h2>17. What to collect when something fails</h2>
<ul>
<li>Copy the complete timestamped run folder from <code>..\runs</code>. Do not delete the failed run.</li>
<li>Include <code>logs\commands.txt</code>, <code>logs\stdout.log</code>, <code>logs\stderr.log</code>, <code>logs\xvf_host_commands.log</code>, <code>metadata.json</code>, <code>config_snapshot.json</code>, and parameter snapshots.</li>
<li>Record <code>py -0p</code>, <code>py -3.10 --version</code>, the devices output, firmware <code>VERSION</code>, <code>AEC_NUM_MICS</code>, and <code>USB_BIT_DEPTH</code>.</li>
<li>If a device is missing, reconnect the XVF3800 and check Windows Sound settings. Do not allow the test to silently use a laptop microphone or speakers.</li>
<li>If an XMOS import reports <code>No module named tuning</code>, verify <code>config.json</code> and rerun Section 9.</li>
<li>If an XMOS file is missing, copy the vendor release folders into <code>XVF 3800 Testing</code> and rerun setup.</li>
</ul>

<h2>Safety and limitations</h2>
<ul>
<li>Temporary packed-input/output changes are recorded and restored where practical.</li>
<li>Do not flash firmware as part of this guide.</li>
<li>Do not overwrite the original input WAV.</li>
<li>Do not describe duplicated mono as genuine four-microphone far-field data.</li>
<li>An XTAG <code>P[0]</code> device is not required for the USB control/audio tests.</li>
</ul>

<h2>Project references</h2>
<p>For the file inventory and detailed validation already performed, open <code>README.md</code> and <code>SETUP_REPORT.md</code> in the same starter directory. The installed package versions are recorded in <code>environment_freeze.txt</code> after setup.</p>
</body>
</html>
'@

$html = $html.Replace("__GENERATED_DATE__", (Get-Date -Format "yyyy-MM-dd HH:mm:ss"))

# Convert the guide's HTML content into a small, standard WordprocessingML package.
# This avoids requiring Microsoft Word to be running while generating the DOCX.
function Escape-XmlText {
    param([AllowNull()][string]$Text)
    if ($null -eq $Text) { return "" }
    return [System.Security.SecurityElement]::Escape($Text)
}

$bodyMatch = [regex]::Match($html, '(?is)<body[^>]*>(.*)</body>')
if (-not $bodyMatch.Success) { throw "Could not extract the guide body while generating the DOCX." }
$bodyText = $bodyMatch.Groups[1].Value
$bodyText = [regex]::Replace($bodyText, '(?is)<h1[^>]*>', "`n@@H1@@`n")
$bodyText = [regex]::Replace($bodyText, '(?is)</h1>', "`n")
$bodyText = [regex]::Replace($bodyText, '(?is)<h2[^>]*>', "`n@@H2@@`n")
$bodyText = [regex]::Replace($bodyText, '(?is)</h2>', "`n")
$bodyText = [regex]::Replace($bodyText, '(?is)<h3[^>]*>', "`n@@H3@@`n")
$bodyText = [regex]::Replace($bodyText, '(?is)</h3>', "`n")
$bodyText = [regex]::Replace($bodyText, '(?is)<pre[^>]*>', "`n@@CODE@@`n")
$bodyText = [regex]::Replace($bodyText, '(?is)</pre>', "`n@@ENDCODE@@`n")
$bodyText = [regex]::Replace($bodyText, '(?is)<li[^>]*>', "`n- ")
$bodyText = [regex]::Replace($bodyText, '(?is)</li>', "`n")
$bodyText = [regex]::Replace($bodyText, '(?is)<tr[^>]*>', "`n")
$bodyText = [regex]::Replace($bodyText, '(?is)</tr>', "`n")
$bodyText = [regex]::Replace($bodyText, '(?is)<td[^>]*>', " | ")
$bodyText = [regex]::Replace($bodyText, '(?is)</td>', " ")
$bodyText = [regex]::Replace($bodyText, '(?is)<th[^>]*>', " | ")
$bodyText = [regex]::Replace($bodyText, '(?is)</th>', " ")
$bodyText = [regex]::Replace($bodyText, '(?is)<p[^>]*>', "`n")
$bodyText = [regex]::Replace($bodyText, '(?is)</p>', "`n")
$bodyText = [regex]::Replace($bodyText, '(?is)<br\s*/?>', "`n")
$bodyText = [regex]::Replace($bodyText, '(?is)<[^>]+>', "")
$bodyText = [System.Net.WebUtility]::HtmlDecode($bodyText)

$documentBuilder = New-Object System.Text.StringBuilder
[void]$documentBuilder.AppendLine('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>')
[void]$documentBuilder.AppendLine('<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">')
[void]$documentBuilder.AppendLine('<w:body>')
$inCode = $false
foreach ($rawLine in ($bodyText -split "`r?`n")) {
    $line = $rawLine.TrimEnd()
    if ($line -eq "@@CODE@@") { $inCode = $true; continue }
    if ($line -eq "@@ENDCODE@@") { $inCode = $false; continue }
    if ($line -eq "@@H1@@") { $currentStyle = "Heading1"; continue }
    if ($line -eq "@@H2@@") { $currentStyle = "Heading2"; continue }
    if ($line -eq "@@H3@@") { $currentStyle = "Heading3"; continue }
    if ($line.Trim().Length -eq 0) {
        [void]$documentBuilder.AppendLine('<w:p/>')
        continue
    }
    if ($inCode) {
        $styleXml = '<w:pPr><w:pStyle w:val="Code"/></w:pPr>'
    } elseif ($null -ne $currentStyle) {
        $styleXml = '<w:pPr><w:pStyle w:val="' + $currentStyle + '"/></w:pPr>'
        $currentStyle = $null
    } else {
        $styleXml = ''
    }
    $escaped = Escape-XmlText $line
    [void]$documentBuilder.AppendLine('<w:p>' + $styleXml + '<w:r><w:t xml:space="preserve">' + $escaped + '</w:t></w:r></w:p>')
}
[void]$documentBuilder.AppendLine('<w:sectPr><w:pgSz w:w="12240" w:h="15840"/><w:pgMar w:top="720" w:right="720" w:bottom="720" w:left="720"/></w:sectPr>')
[void]$documentBuilder.AppendLine('</w:body></w:document>')

$packageRoot = Join-Path $env:TEMP ("xvf3800-docx-{0}" -f ([guid]::NewGuid().ToString("N")))
New-Item -ItemType Directory -Path (Join-Path $packageRoot "_rels") -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $packageRoot "word\_rels") -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $packageRoot "word") -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $packageRoot "docProps") -Force | Out-Null
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)

$contentTypes = @'
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>
'@
$rootRelationships = @'
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>
'@
$documentRelationships = @'
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>
'@
$styles = @'
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri"/><w:sz w:val="21"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri"/><w:b/><w:color w:val="17365D"/><w:sz w:val="32"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri"/><w:b/><w:color w:val="1F4E79"/><w:sz w:val="26"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading3"><w:name w:val="heading 3"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri"/><w:b/><w:color w:val="1F4E79"/><w:sz w:val="23"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Code"><w:name w:val="Code"/><w:basedOn w:val="Normal"/><w:rPr><w:rFonts w:ascii="Consolas" w:hAnsi="Consolas"/><w:sz w:val="17"/></w:rPr></w:style>
</w:styles>
'@
$coreProperties = @"
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><dc:title>XVF3800 Windows Installation and Testing Guide</dc:title><dc:creator>OpenAI Codex</dc:creator><dcterms:created xsi:type="dcterms:W3CDTF">$((Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ"))</dcterms:created></cp:coreProperties>
"@
$appProperties = @'
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes"><Application>XVF3800 Guide Generator</Application></Properties>
'@

[System.IO.File]::WriteAllText((Join-Path $packageRoot "[Content_Types].xml"), $contentTypes, $utf8NoBom)
[System.IO.File]::WriteAllText((Join-Path $packageRoot "_rels\.rels"), $rootRelationships, $utf8NoBom)
[System.IO.File]::WriteAllText((Join-Path $packageRoot "word\_rels\document.xml.rels"), $documentRelationships, $utf8NoBom)
[System.IO.File]::WriteAllText((Join-Path $packageRoot "word\document.xml"), $documentBuilder.ToString(), $utf8NoBom)
[System.IO.File]::WriteAllText((Join-Path $packageRoot "word\styles.xml"), $styles, $utf8NoBom)
[System.IO.File]::WriteAllText((Join-Path $packageRoot "docProps\core.xml"), $coreProperties, $utf8NoBom)
[System.IO.File]::WriteAllText((Join-Path $packageRoot "docProps\app.xml"), $appProperties, $utf8NoBom)

Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem
if (Test-Path -LiteralPath $OutputPath) {
    $backupPath = Join-Path $ProjectRoot ("XVF3800_Install_and_Test_Guide_backup_{0}.docx" -f (Get-Date -Format "yyyyMMdd_HHmmss"))
    Move-Item -LiteralPath $OutputPath -Destination $backupPath
    Write-Host "Moved existing guide to $backupPath"
}
[System.IO.Compression.ZipFile]::CreateFromDirectory($packageRoot, $OutputPath)
Remove-Item -LiteralPath $packageRoot -Recurse -Force

Write-Host "Created Word guide: $OutputPath"
