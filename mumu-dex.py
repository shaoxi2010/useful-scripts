from argparse import ArgumentParser
from os import path, mkdir
from shutil import rmtree
from subprocess import check_call
from time import sleep
from retry import retry
from frida import ServerNotRunningError, get_device_manager
from frida.core import Device, ScriptMessage
import sys

parser = ArgumentParser(description="Dump dex files from a process")
parser.add_argument("identifier", help="Process identifier")
parser.add_argument("-o", "--output", help="Output directory", default="classes")

pwd = path.abspath(path.dirname(__file__))
server = path.join(pwd, "frida-server")


def run_frida_server_by_adb():
    check_call(f"adb push {server} /data/local/tmp/", shell=True)
    check_call("adb shell chmod 755 /data/local/tmp/frida-server", shell=True)
    check_call("adb shell /data/local/tmp/frida-server &", shell=True)


def frida_server_is_run(device: Device):
    processes = [p.name for p in device.enumerate_processes()]
    return "frida-server" in processes


def wait_frida_server(device: Device):
    if frida_server_is_run(device):
        return
    else:
        run_frida_server_by_adb()
        while not frida_server_is_run(device):
            sleep(1)


@retry(ServerNotRunningError, tries=3, delay=1)
def kill_by_identifier(device: Device, identifier):
    for process in device.enumerate_applications():
        if process.identifier == identifier:
            device.kill(process.pid)


@retry(ServerNotRunningError, tries=3, delay=1)
def spwan_frida_script(device: Device, identifier, script, output):
    def on_message(message: ScriptMessage, data):
        if message["type"] == "send":
            dexpath = message["payload"]
            print(f"save: {path.basename(dexpath)}")
            with open(path.join(output, path.basename(dexpath)), "wb") as f:
                f.write(data)
        elif message["type"] == "error":
            print(f"[!] {message['stack']}")

    kill_by_identifier(device, identifier)
    pid = device.spawn([identifier])
    process = device.attach(pid)
    script = process.create_script(script)
    script.on("message", on_message)
    script.load()
    device.resume(pid)


#  安卓12的dex打开函数 http://aospxref.com/android-12.0.0_r3/xref/art/libdexfile/dex/dex_file_loader.h#182
#  static std:: unique_ptr < DexFile > DexFileLoader:: OpenCommon(const uint8_t* base,
#                                                     size_t size,
#                                                     const uint8_t* data_base,
#                                                     size_t data_size,
#                                                     const std:: string& location,
#                                                     uint32_t location_checksum,
#                                                     const OatDexFile* oat_dex_file,
#                                                     bool verify,
#                                                     bool verify_checksum,
#                                                     std:: string * error_msg,
#                                                     std:: unique_ptr < DexFileContainer > container,
#                                                     VerifyResult * verify_result)
dump_script = """
var opencommon = "_ZN3art13DexFileLoader10OpenCommonEPKhmS2_mRKNSt3__112basic_stringIcNS3_11char_traitsIcEENS3_9allocatorIcEEEEjPKNS_10OatDexFileEbbPS9_NS3_10unique_ptrINS_16DexFileContainerENS3_14default_deleteISH_EEEEPNS0_12VerifyResultE"
Java.performNow(function () {
    var target = Module.findExportByName("libdexfile.so", opencommon)
    Interceptor.attach(target, {
        onEnter: function (args) {
            this.base = args[0]
            this.size = args[1]
            this.location = readStdString(args[4])
        },
        onLeave: function (retval) {
            var data = Memory.readByteArray(this.base, this.size.toInt32())
            send(this.location, data)
        }
    })
})

function readStdString(str) {
    const isTiny = (str.readU8() & 1) === 0
    if (isTiny) {
        return str.add(1).readUtf8String()
    }

    return str.add(2 * Process.pointerSize).readPointer().readUtf8String()
}
"""

if __name__ == "__main__":
    args = parser.parse_args()
    device = get_device_manager().get_usb_device(3)
    wait_frida_server(device)
    if path.exists(args.output):
        rmtree(args.output)
    mkdir(args.output)
    spwan_frida_script(device, args.identifier, dump_script, args.output)
    try:
        sys.stdin.read()
    except KeyboardInterrupt:
        sys.exit(0)
