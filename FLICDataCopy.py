import sys
import os
import threading
import time
import shutil

class FLICDataCopy(object):
    def __init__(self, message, width=15, progressSymbol=u'▣ ', emptySymbol=u'□ '):
        self.width = width
 
        if self.width < 0:
            self.width = 0
 
        self.message = message
        self.progressSymbol = progressSymbol
        self.emptySymbol = emptySymbol
        self.isDataTransferring=False
        self.numFiles=0
        self.numCopied=0
        self.copySuccess=False
       
    def GetProgressString(self):   
        if(self.numFiles<=0):
            progress=0   
        else:
            progress = int(round( (self.numCopied / float(self.numFiles)) * 100) )
        totalBlocks = self.width
        filledBlocks = int(round(progress / (100 / float(totalBlocks)) ))
        emptyBlocks = totalBlocks - filledBlocks
      
        progressBar = self.progressSymbol * filledBlocks + \
                      self.emptySymbol * emptyBlocks
 
        if not self.message:
            self.message = u''
 
        progressMessage = u'\r{0} {1}  {2}%'.format(self.message,
                                                    progressBar,
                                                    progress)
 
        return progressMessage  

    def countFiles(self,path):
        files = []         
        if os.path.isdir(path):          
            for path, dirs, filenames in os.walk(path):               
                files.extend(filenames)
 
        return len(files)
  
    def StartDataTransfer(self,src,target):
        self.targetPath=target
        self.sourcePath=src
        copyThread = threading.Thread(target=self.copyFilesWithProgress)        
        copyThread.start()    

    def makedirs(self,dest):
        if not os.path.exists(dest):
            os.makedirs(dest)   
    
    def copyFilesWithProgress(self):
        self.copySuccess=False
        self.isDataTransferring=True
        try:           
            self.numFiles = self.countFiles(self.sourcePath)

            if self.numFiles > 0:
                self.makedirs(self.targetPath)

                self.numCopied = 0

                for path, dirs, filenames in os.walk(self.sourcePath):                                  
                    for directory in dirs:
                        destDir = path.replace(self.sourcePath,self.targetPath)
                        self.makedirs(os.path.join(destDir, directory))                    
                    for sfile in filenames:
                        srcFile = os.path.join(path, sfile)

                        destFile = os.path.join(path.replace(self.sourcePath, self.targetPath), sfile)                        
                        shutil.copy(srcFile, destFile)
                        self.numCopied += 1
                                    
            self.isDataTransferring=False
            self.copySuccess=True
        except:
            print("File Transfer Exception ")
            self.isDataTransferring=False
            self.copySuccess=False
        return
    

if __name__ == "__main__":
    tmp = FLICDataCopy("Copying files: ")
    subfolders = [f.path for f in os.scandir("/media/pi") if f.is_dir()]
    destPath = subfolders[0]+'/FLICData'  
    print(destPath)  
    #destPath="/home/pi/FLICData"
    sourcePath="/home/pi/PyMCU/PyMCU/FLICData"
    tmp.StartDataTransfer(sourcePath,destPath)     
    while(tmp.isDataTransferring):
        #print(tmp.GetProgressString())
        time.sleep(0.2)
