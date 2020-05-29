import os
import glob
import shutil
import time

def DetectUSB():
    try:
        subfolders = [f.path for f in os.scandir("/media/pi") if f.is_dir()]
        if len(subfolders)>0:
            return True
    except:
        return False

def DetectUpdateFile():  
    try:    
        subfolders = [f.path for f in os.scandir("/media/pi") if f.is_dir()]       
        if len(subfolders)==0:
            sourceDirectory = "/media/pi/FLICUpdates/"
        else:
            sourceDirectory = subfolders[0]+"/FLICUpdates/"    
        targetDirectory ="../"             
        files=(glob.glob(sourceDirectory+"*.tgz"))                
        if(len(files)==1):                      
            shutil.copy(files[0],targetDirectory)
            time.sleep(2)
        else:            
            return False
    except:
        return False
    return True
                
      
def main():
    if(DetectUSB()):
        print(DetectUpdateFile())

if __name__ == "__main__":
    print("Updating...")
    main()
    print("Done! Rebooting...")
    time.sleep(2)