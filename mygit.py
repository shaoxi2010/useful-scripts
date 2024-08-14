# pyinstaller -F mygit.py
import sys
from os import path
from subprocess import check_output, Popen,PIPE

# Get the application path with pyinstaller
if getattr(sys, 'frozen', False):
    application_path = path.dirname(sys.executable)
else:
    application_path = path.dirname(path.abspath(__file__))

git = path.join(application_path, "usr/bin/git.exe")
cygpath = path.join(application_path, "usr/bin/cygpath.exe")

# Convert Unix paths to Windows paths
def cygpath_convert(path):
    return check_output([cygpath, "-w", path]).strip().decode("utf-8")


# getpwd() return posix path not a windows path so convert it to windows path
if __name__ == "__main__":
    cmd = [git]
    cmd.extend(sys.argv[1:])
    p = Popen(cmd, stdout=PIPE)
    for line in p.stdout:
        if 'rev-parse' in cmd:
            print(cygpath_convert(line.decode("utf-8").strip('\n')))
        else:
            print(line.decode("utf-8").strip('\n'))
    