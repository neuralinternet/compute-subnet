import atexit
import subprocess
import datetime
import os

def start(delay_days):
    # Get the absolute path of the current working directory
    current_directory = os.getcwd()

    # The name of the file
    file_name = "kill_container"

    # Get the absolute path of the file in the current directory
    file_path = os.path.join(current_directory, file_name)

    # Calculate the future time
    current_datetime = datetime.datetime.now()
    future_datetime = current_datetime + datetime.timedelta(days=delay_days)
    formatted_date = future_datetime.strftime("%m/%d/%Y")
    formatted_time = future_datetime.strftime("%H:%M")

    # A function to schedule the command
    def schedule_command():
        scheduled_task_name = "MyScheduledTask"
        print(formatted_date + ":" + formatted_time + ":" + file_path)
        subprocess.run(['schtasks', '/delete', '/tn', scheduled_task_name, '/f'], check=True)
        subprocess.call(["schtasks.exe", "/create", "/tn", scheduled_task_name, "/tr", file_path, "/sc", "once", "/st", formatted_time, "/sd", formatted_date])

    # Register the function to be executed when the script exits
    atexit.register(schedule_command)