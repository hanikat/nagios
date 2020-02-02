#Author: Marcus Hanikat (hanikat@kth.se)
#Tested on Windows server 2016 with scheduled Active Directory Syncrhonization client
#Inspiration: https://siliconwolf.net/aad-connect-admin-check-sync-time-and-errors/

#Lines to be added in NSClient++-configuration:

#[/settings/external scripts/scripts]
#<SERVICE_NAME> = cmd /c echo scripts\CheckSync.ps1; exit($LastExitCode) | powershell.exe -command -

#Script is placed in: ..\NSClient++\Scripts for NSClient++

#Parameters:
#allowedMinutesSinceSync: Determines the maximum number of minutes since last successful sync before error is reported
#disableOutput: Determines if the script should output debug information or not
param (
    [int] $allowedMinutesSinceSync = 90,
    [bool] $disableOutput = $false,
    [bool] $checkPasswordSync = $true
)

#Get the latest sync status and timestamp for passwords to AAD
$aadStatus = Get-ADSyncPartitionPasswordSyncState | Select-Object -Index 1 | Select-Object -Property PasswordSyncLastCycleStatus, PasswordSyncLastSuccessfulCycleEndTimestamp

#Get the interval for synchronization between local AD and AAD
$SyncSchedule = (Get-ADSyncScheduler).CurrentlyEffectiveSyncCycleInterval.Minutes

#Get the latest synchronization time between local and AAD
$LastScheduledSyncParams = @{
    LogName      = "Application"
    ProviderName = "Directory Synchronization"
    ID           = "904"
    Data         = "Finished"

}
$LastScheduledSync = Get-WinEvent -MaxEvents 1 -FilterHashtable $LastScheduledSyncParams


# GET: CHECK SYNC ERRORS: ---------------------------------------------
# Check and capture the last connector sync error eventlog. Event ID 6100.
$RunProfileErrorParams = @{
    LogName      = "Application"
    ProviderName = "ADSync"
    ID           = "6100"
    StartTime    = (Get-Date).AddMinutes(0 - $SyncSchedule)

}
$RunProfileError = Get-WinEvent -MaxEvents 1 -FilterHashtable $RunProfileErrorParams -ErrorAction SilentlyContinue


# GET: CHECK MANAGEMENT PROFILE WARNING: ------------------------------
# Check and capture the last connector sync error eventlog. Event ID 6127.
# Usually, due to the configuration change that requires Initial Sync to update the profile.
$RunProfileWarningParams = @{
    LogName      = "Application"
    ProviderName = "ADSync"
    ID           = "6127"
    StartTime    = (Get-Date).AddMinutes(0 - $SyncSchedule)

}
$RunProfileWarning = Get-WinEvent -MaxEvents 1 -FilterHashtable $RunProfileWarningParams -ErrorAction SilentlyContinue


# GET: CHECK OBJECT EXPORT ERRORS: ------------------------------------
# Check and capture the last connector sync error eventlog. Event ID 6803.
# Usually, due to DataValidationFailed, InvalidSoftMatch, AttributeValueMustBeUnique. Event ID 6941 has more
# details but more entries if many errors. Using the generic 6803 as a flag to investigate further.
$ExportStepErrorsParams = @{
    LogName      = "Application"
    ProviderName = "ADSync"
    ID           = "6803"
    StartTime    = (Get-Date).AddMinutes(0 - $SyncSchedule)

}
$ExportStepError = Get-WinEvent -MaxEvents 1 -FilterHashtable $ExportStepErrorsParams -ErrorAction SilentlyContinue

$status = 0


#Check if the last password sync was successful
if($aadStatus.PasswordSyncLastCycleStatus -eq "Successful" -and $checkPasswordSync) {
    #Parse time of last password sync date and current date
    $syncDate = Get-Date -Date $aadStatus.PasswordSyncLastSuccessfulCycleEndTimestamp
    $now = Get-Date
    $now = $now.ToUniversalTime()
	
    #Increment syncDate with $allowedMinutesSinceSync to see if the syncDate is within allowed time frame
    $syncDate = $syncDate.ToUniversalTime().AddMinutes($allowedMinutesSinceSync)
    
    #Check if the syncDate for passwords is within accepted range
    if($now -le $syncDate) {
		if(!$disableOutput) {
			Write-Output "OK: Passwords synced within the last $($allowedMinutesSinceSync) minutes"
		}

    } else {
		#No synchronization of passwords within the last $allowedMinutesSinceSync
        if(!$disableOutput) {
			Write-Output "Error: No password sync within the last $($allowedMinutesSinceSync) minutes!"
        }
		$status = 1
    }
}


#Check if last AAD sync date is within accepted range
if($now -le (Get-Date $LastScheduledSync.TimeCreated).AddMinutes($allowedMinutesSinceSync)) {
	if(!$disableOutput) {
		Write-Output "OK: AAD synced within the last $($allowedMinutesSinceSync) minutes"
	}

	#Get ADSyncScheduler properties and status
	$adSyncScheduler = Get-ADSyncScheduler | Select-Object -Property SyncCycleEnabled, SchedulerSuspended

	#Check if Sync Cycle is enabled
	if(!$adSyncScheduler.SyncCycleEnabled) {
		if(!$disableOutput) {
			Write-Output "Error: SyncCycle is disabled!"
		}
		$status = 1
	} else {
		if(!$disableOutput) {
			Write-Output "OK: SyncCycle is enabled!"
		}
	}

	#Check if syncScheduler is suspended
	if($adSyncScheduler.SchedulerSuspended) {
		if(!$disableOutput) {
			Write-Output "Error: Scheduler has been suspended!"
		}
		$status = 1
	} else {
		if(!$disableOutput) {
			Write-Output "OK: Scheduler is running!"
		}
	}

	#Check if last sync had errors
	if($RunProfileError -ne $null) {
		if(!$disableOutput) {
			Write-Output "Error: AAD Sync returned errors: $($RunProfileError.Message)"
		}
		$status = 1
	}

	#Check if last sync had warnings
	if($RunProfileWarning -ne $null) {
		#Filter away the "Configuration changed" warning since this will be resolved during next full synchronization
		if($RunProfileWarning.Message -notlike '*The rules configuration has changed since the last full synchronization.*') {
			if(!$disableOutput) {
				Write-Output "Error: AAD sync returned warnings: $($RunProfileWarning.Message)"
			}
			$status = 1
		}
	}

	#Check if there were export step errors
	if($ExportStepError -ne $null) {
		if(!$disableOutput) {
			Write-Output "Error: AAD Sync returned errors during export: $($ExportStepError.Message)"
		}
		$status = 1
	}

	#Check if an error was returned and send critical status to Nagios
	if($status -ne 0) {
		if(!$disableOutput) {
			Write-Output "There was one or more problems with the AAD Syncrhonization client!"
		}
		exit 2
	}

} else {
	#No synchronization of local AD to AAD within the last $allowedMinutesSinceSync
	if(!$disableOutput) {
		Write-Output "Error: No AAD sync within the last $($allowedMinutesSinceSync) minutes!"
	}
	exit 2
}
