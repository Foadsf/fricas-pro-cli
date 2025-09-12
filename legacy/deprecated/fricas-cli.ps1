param(
    [Parameter(Position = 0)]
    [string]$Command,

    [Parameter(Position = 1, ValueFromRemainingArguments = $true)]
    [string[]]$Arguments,

    [switch]$DebugMode
)

function Write-DebugLog {
    param([string]$Message)
    if ($DebugMode) {
        Write-Host "[DEBUG] $Message" -ForegroundColor Yellow
    }
}

$FricasPath = "C:\Users\FoadS\scoop\apps\fricas\1.3.12\bin\FRICASsys.exe"

function Show-Usage {
    Write-Host "FriCAS CLI Wrapper"
    Write-Host "Usage: fricas-cli <command> [arguments]"
    Write-Host ""
    Write-Host "Commands:"
    Write-Host "  version     - Show FriCAS version"
    Write-Host "  help        - Show available FriCAS commands"
    Write-Host "  eval <expr> - Evaluate a FriCAS expression"
    Write-Host "  file <path> - Execute commands from file"
    Write-Host "  system <cmd>- Run system command in FriCAS"
    Write-Host "  interactive - Start interactive FriCAS session"
}

function Invoke-FriCAS {
    param([string]$FricasCommand)

    $Input = $FricasCommand + "`n)quit"

    $ProcessStartInfo = New-Object System.Diagnostics.ProcessStartInfo
    $ProcessStartInfo.FileName = $FricasPath
    $ProcessStartInfo.Arguments = "--non-interactive"
    $ProcessStartInfo.UseShellExecute = $false
    $ProcessStartInfo.RedirectStandardInput = $true
    $ProcessStartInfo.RedirectStandardOutput = $true
    $ProcessStartInfo.RedirectStandardError = $true

    $Process = [System.Diagnostics.Process]::Start($ProcessStartInfo)

    $Process.StandardInput.WriteLine($Input)
    $Process.StandardInput.Close()

    $Output = $Process.StandardOutput.ReadToEnd()
    $Process.WaitForExit()

    return $Output
}

switch ($Command.ToLower()) {
    "version" {
        $ProcessStartInfo = New-Object System.Diagnostics.ProcessStartInfo
        $ProcessStartInfo.FileName = "cmd.exe"
        $ProcessStartInfo.Arguments = "/c `"echo )quit | `"$FricasPath`" --version 2>nul | findstr /i `"Version.*FriCAS`"`""
        $ProcessStartInfo.UseShellExecute = $false
        $ProcessStartInfo.RedirectStandardOutput = $true
        $ProcessStartInfo.CreateNoWindow = $true

        $Process = [System.Diagnostics.Process]::Start($ProcessStartInfo)
        $Process.WaitForExit()
        $Output = $Process.StandardOutput.ReadToEnd().Trim()

        if ($Output) {
            Write-Host $Output
        }
        else {
            Write-Host "Version information not found"
        }
    }

    "help" {
        $Output = Invoke-FriCAS ")help"
        Write-Host $Output
    }

    "eval" {
        if ($Arguments.Count -eq 0) {
            Write-Host "Error: eval requires an expression"
            exit 1
        }
        $Expression = $Arguments -join " "
        $Output = Invoke-FriCAS $Expression
        Write-Host $Output
    }

    "file" {
        if ($Arguments.Count -eq 0) {
            Write-Host "Error: file requires a path"
            exit 1
        }
        $FilePath = $Arguments[0]
        $Output = Invoke-FriCAS ")read $FilePath"
        Write-Host $Output
    }

    "system" {
        if ($Arguments.Count -eq 0) {
            Write-Host "Error: system requires a command"
            exit 1
        }
        $SystemCmd = $Arguments -join " "
        $Output = Invoke-FriCAS ")system $SystemCmd"
        Write-Host $Output
    }

    "interactive" {
        Start-Process -FilePath $FricasPath -Wait -NoNewWindow
    }

    default {
        Show-Usage
    }
}
