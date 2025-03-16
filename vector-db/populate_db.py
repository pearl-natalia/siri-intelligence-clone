import subprocess
def reminders():
    apple_script = """
                    tell application "Reminders"
                        set reminderList to {}
                        repeat with r in reminders
                            try
                                set reminderName to name of r
                                set reminderDueDate to due date of r
                                set reminderCompleted to completed of r
                                set reminderPriority to priority of r
                                
                                -- Append details of the reminder to the list
                                set end of reminderList to {reminderName, reminderDueDate, reminderCompleted, reminderPriority}
                            on error
                                set end of reminderList to {"Error fetching details for reminder"}
                            end try
                        end repeat
                        return reminderList
                    end tell
                    """
    result = subprocess.run(['osascript', '-e', apple_script], capture_output=True, text=True)
    output = result.stdout
    with open("reminders.txt", "w") as file:
        file.write(output)
    
reminders()
