# 128M 128KB 2KB, first partition is 10 erase blocks, second partition is 20 erase blocks
# modprobe nandsim id_bytes = "0xec,0xa1,0x00,0x15" parts = 10, 20
# modprobe nandsim id_bytes="0x20,0xa5,0x00,0x15" # 2G 128KB PEB, 2KB page
# modprobe nandsim id_bytes="0x20,0xa5,0x00,0x26" # 4G 256KB 4KB 1KB-sub-page
# modprobe nandsim id_bytes="0x20,0xa7,0x00,0x15" # 4G 256KB 4KB 2KB-sub-page
# modprobe nandsim id_bytes="0x20,0x33,0x00,0x00" # 16M 16KB PEB, 512 page
# p：enable the pr_debug() callsite；
# f/l/m/t：include the function name、line number、module name、threadID in the printed message；

from subprocess import check_call
from argparse import ArgumentParser
from os import path
from shutil import copyfileobj

parser = ArgumentParser()
parser.add_argument('-b', '--block', type=int, default=64)
parser.add_argument('-p', '--page', type=int, default=2048)
parser.add_argument('nandfile', type=str, help='nand image file')

if __name__ == '__main__':
    args = parser.parse_args()

    if path.exists('/dev/mtd0'):
        check_call('sudo rmmod nandsim', shell=True)
    blocks = path.getsize(args.nandfile) // (args.block * args.page) 
    check_call(f'sudo modprobe nandsim id_bytes="0xec,0xa1,0x00,0x15" parts={blocks} dyndbg="+pmf"'
               ,shell=True)
    with open('/dev/mtd0', 'bw') as mtd, open(args.nandfile, 'rb') as raw:
        copyfileobj(raw, mtd)
        
    print('Use: sudo modprobe ubi dyndbg=+pmf #load ubi')
    print('Use: sudo ubiattach  -O 2048 -p /dev/mtd0 #attach ubi')
