function Select-XvfWavFile {
    param(
        [Parameter(Mandatory = $true)][string]$ProjectRoot,
        [string]$Title = "Select an XVF3800 mono WAV input"
    )

    try {
        Add-Type -AssemblyName System.Windows.Forms
    } catch {
        throw "The Windows file picker could not be loaded. Provide -MonoFile explicitly. Details: $($_.Exception.Message)"
    }

    $dialog = New-Object System.Windows.Forms.OpenFileDialog
    try {
        $dialog.Title = $Title
        $dialog.Filter = "WAV audio files (*.wav)|*.wav|All files (*.*)|*.*"
        $dialog.CheckFileExists = $true
        $dialog.Multiselect = $false
        $sampleAudio = Join-Path (Split-Path -Parent $ProjectRoot) "SampleAudio"
        $dialog.InitialDirectory = if (Test-Path -LiteralPath $sampleAudio -PathType Container) { $sampleAudio } else { $ProjectRoot }
        $result = $dialog.ShowDialog()
        if ($result -ne [System.Windows.Forms.DialogResult]::OK -or [string]::IsNullOrWhiteSpace($dialog.FileName)) {
            throw "No WAV file was selected."
        }
        if ([IO.Path]::GetExtension($dialog.FileName).ToLowerInvariant() -ne ".wav") {
            throw "The selected file is not a WAV file: $($dialog.FileName)"
        }
        return $dialog.FileName
    } finally {
        $dialog.Dispose()
    }
}
