import os
import subprocess
import time

'''
    Syncs the working script with origin
    
    DON'T USE THIS FOR DEVELOPMENT, SINCE IT DELETES (or at least should) ALL CHANGES NOT SAVED IN ORIGIN
'''

while True:
    os.system("git pull origin")
    print("Pulled newest version from origin")
    process = subprocess.Popen("python3 logic.py", shell=True)
    time.sleep(5 * 60)
    process.kill()
