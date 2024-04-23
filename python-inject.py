# 使用CPython的方法进行远程的python代码注入

from os import getenv, path
from argparse import ArgumentParser
from time import sleep
from threading import Condition

# maybe need sudo
if getenv("SUDO_USER"):
    import sys
    homedir = path.join("/home", getenv("SUDO_USER"))
    sys.path.append(path.join(homedir, ".local/lib/python3.10/site-packages"))

from frida import get_local_device
from frida_tools.reactor import Reactor

hook = """
var py_run = Module.findExportByName(null, "PyRun_SimpleStringFlags");
var py_gli_ensure = Module.findExportByName(null, "PyGILState_Ensure");
var py_gli_release = Module.findExportByName(null, "PyGILState_Release");

var py_run = new NativeFunction(py_run, 'int', ['pointer', 'pointer'])
var py_gli_ensure = new NativeFunction(py_gli_ensure, 'pointer', [])
var py_gli_release = new NativeFunction(py_gli_release, 'void', ['pointer'])

rpc.exports = {
    run: function(code, size) {
        var gstate = py_gli_ensure();
		var data = Memory.alloc(size);
		data.writeUtf8String(code);
		var result = py_run(data, NULL);
        py_gli_release(gstate);
        return result;
    }
}
"""

class HookCPython:
    def __init__(self, pid, code, time):
        self._pid = pid
        self.code = code
        self.time = time
        self._reactor = Reactor(run_until_return=self._loop)
        self.wait_start = Condition()

    def _start(self):
        def on_message(message, data):
            if message["type"] == "send":
                print(f"[*] {message['payload']}")
            else:
                print(f"[!] {message['stack']}")

        def on_destroyed():
            self.running = False

        try:
            device = get_local_device()
            session = device.attach(self._pid)
            self.script = session.create_script(hook)
            self.script.on("message", on_message)
            self.script.on("destroyed", on_destroyed)
            self.script.load()
            self.running = True
        except Exception as e:
            print(f"[!] {e}")
            self.running = False

        self.wait_start.acquire()
        self.wait_start.notify()
        self.wait_start.release()

    def _remote_run_code(self, code: str):
        if not isinstance(code, str):
            return
        size = len(code.encode("utf-8")) + 1
        return self.script.exports_sync.run(code, size)

    def _loop(self, reactor):
        self.wait_start.acquire()
        self.wait_start.wait()
        self.wait_start.release()
        self._remote_run_code(self.code)
        while self.running and self.time:
            sleep(self.time)
            self._remote_run_code(self.code)

    def run(self):
        self._reactor.schedule(lambda: self._start())
        self._reactor.run()


parser = ArgumentParser()
parser.add_argument("pid", type=int, help="Process ID to attach to")
parser.add_argument("-c", "--code", type=str, help="Code to run in the target process", required=False)
parser.add_argument("-f", "--file", type=str, help="File to run in the target process", required=False)
parser.add_argument("-t", "--time", type=int, help="Time to run the script", default=0)

if __name__ == "__main__":
    args = parser.parse_args()
    if args.code:
        code  =  args.code
    elif args.file:
        with open(args.file, "r") as f:
            code = f.read()
    else:
        code = "print('nothing to inject!')"
    app = HookCPython(args.pid, code, args.time)
    app.run()
    