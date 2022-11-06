import os
import subprocess
import time
import atexit
import init_db

'''
    Syncs the working script with origin. 
    
    DON'T USE THIS FOR DEVELOPMENT, SINCE IT DELETES (or at least should) ALL CHANGES NOT SAVED IN ORIGIN
'''


process = None


def on_exit():
    if process is not None:
        process.terminate()
    print("Exiting")


atexit.register(on_exit)
while True:
    os.system("git pull origin")
    print("Pulled newest version from origin")
    if not init_db.valid():
        print("Database update required")
        init_db.update()
        print("Database updated")
    process = subprocess.Popen(["python3", "logic.py"], shell=False)
    time.sleep(5 * 60)
    process.terminate()
