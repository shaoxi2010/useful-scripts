from argparse import ArgumentParser
from os import path
import xml.dom.minidom as minidom

parser = ArgumentParser()
parser.add_argument('project', help='project file')
parser.add_argument('--armcc', help='armcc install path', default='C:\Keil_v5\ARM\ARMCC')

def paser_keil_project(project):
    prop = {}
    dom = minidom.parse(project)
    elem = dom.documentElement
    for target in elem.getElementsByTagName('Target'):
        name = target.getElementsByTagName('TargetName')
        if name and name[0].firstChild:
            target_name = name[0].firstChild.data
        else:
            continue
        includedirs = []
        defines = []
        for include in target.getElementsByTagName('IncludePath'):
            if include and include.firstChild:
                data = include.firstChild.data
                includedirs.extend(data.split(';'))
        for define in target.getElementsByTagName('Define'):
            if define and define.firstChild:
                data = define.firstChild.data
                defines.extend(data.split())
        prop[target_name] = {'includedirs': includedirs, 'defines': defines}
    return prop

compile_flags_nolibc = """
-target
arm-none-eabi
-xc
-ffreestanding
-nostdinc
-nostdlib
-fdeclspec
-D__const=
-D__forceinline=
-D__global_reg=
-D__inline=
-D__irq=
-D__packed=
-D__pure=
-D__smc=
-D__softfp=
-D__svc=
-D__svc_indirect=
-D__thread=
-D__value_in_regs=
-D__weak=
-D__writeonly=
"""

def gen_compile_flags(target, includedirs, defines, root, armcc):
    print(f'build compile_flags.txt for target: {target}')
    with open('compile_flags.txt', 'w') as f:
        f.write(compile_flags_nolibc)
        for dir in includedirs:
            f.write(f'-I{path.join(root, dir)}\n')
        for define in defines:
            f.write(f'-D{define}\n')
        f.write(f'-isystem{path.join(armcc, "include")}\n')

if __name__ == '__main__':
    args = parser.parse_args()
    props = paser_keil_project(args.project)
    root = path.dirname(args.project)
    for target_name, target_props in props.items():
        print(f'Use target: {target_name} [Y]/N')
        if input().upper() == 'N':
            continue
        gen_compile_flags(target_name, target_props['includedirs'], target_props['defines'], root , args.armcc)