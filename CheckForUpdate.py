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
            print("Updating...")
            time.sleep(1)
            command = "/bin/tar -C /home/pi/PyMCU -xvf " + "\""+files[0]+"\""                        
            os.system(command)            
            print("Done!")
            print("Shutting down...Remove USB")    
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
