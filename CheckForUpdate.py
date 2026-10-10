import os
import glob
import time
import getpass

APP_DIRECTORY = os.path.dirname(os.path.abspath(__file__))

def GetUSBDrives():
    """Mount points of attached USB drives, as in MainViewModel.GetUSBDrives."""
    drives = []
    for root in dict.fromkeys(os.path.realpath(r) for r in ("/media/pi", "/media/"+getpass.getuser())):
        try:
            drives += [f.path for f in os.scandir(root) if f.is_dir()]
        except OSError:
            pass
    return sorted(drives)

def GetUSBDrive(folder):
    """First attached USB drive that has the given top-level folder, as in MainViewModel.GetUSBDrive."""
    for drive in GetUSBDrives():
        if os.path.isdir(os.path.join(drive, folder)):
            return drive
    return None

def DetectUSB():
    try:
        return GetUSBDrive("FLICUpdates") is not None
    except:
        return False

def DetectUpdateFile():  
    try:    
        sourceDirectory = GetUSBDrive("FLICUpdates")+"/FLICUpdates/"
        files=(glob.glob(sourceDirectory+"*.tgz"))                
        if(len(files)==1):    
            print("Updating...")
            time.sleep(1)
            command = "/bin/tar -C \"" + APP_DIRECTORY + "\" -xvf " + "\""+files[0]+"\""                        
            os.system(command)            
            print("Done!")
            print("Shutting down...Remove USB and power cycle")    
            time.sleep(3)
            os.system("sudo shutdown -h now")
        else:            
            return False
    except:
        return False
    return True
                
      
def main():
    if(DetectUSB()):
        DetectUpdateFile()

if __name__ == "__main__":    
    main()    
