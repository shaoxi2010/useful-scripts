from argparse import ArgumentParser
from os import path, environ, walk
import xml.dom.minidom as minidom

parser = ArgumentParser()
parser.add_argument('project', help='project file')
parser.add_argument('--CDK', help='CDK install path', default=f'{environ["USERPROFILE"]}/AppData/Roaming/C-Sky')

def paser_cdk_project(project):
    project_root = path.dirname(project)
    project_relpath = path.relpath(project_root, 'project')
    prop = {}
    dom = minidom.parse(project)
    elem = dom.documentElement
    for config in elem.getElementsByTagName('ToolsConfig'):
        for tool in config.getElementsByTagName('Name'):
            if tool and tool.firstChild:
                tool_name = tool.firstChild.data
    for target in elem.getElementsByTagName('BuildConfig'):
        target_name = target.getAttribute('Name')
        includedirs = []
        defines = []
        compiler = target.getElementsByTagName('Compiler')[0]
        for include in compiler.getElementsByTagName('IncludePath'):
            if include and include.firstChild:
                data = include.firstChild.data
                includedirs.extend(map(lambda x: x.replace('$(ProjectPath)', project_relpath), data.split(';')))
        for define in compiler.getElementsByTagName('Define'):
            if define and define.firstChild:
                data = define.firstChild.data
                defines.extend(data.split())
        prop[target_name] = {'includedirs': includedirs, 'defines': defines, 'tool': tool_name}
    return prop

def get_sysroot(cdk_path, tool_name):
    sysroot = {
        'CKV1ElfMinilib': 'csky-elf',
        'CKV2ElfMinilib': 'csky-elfabiv2'
    }
    toolchain_root = path.join(cdk_path, 'CDKRepo','Toolchain', tool_name)
    for root, dirs, _ in walk(toolchain_root):
        if sysroot[tool_name] in dirs:
            return path.join(root, sysroot[tool_name])
    return None

compile_flags = """
-target
csky-unknown-elf
-xc
-ffreestanding
"""
def gen_compile_flags(target, target_props):
    print(f'build compile_flags.txt for target: {target}')
    with open('compile_flags.txt', 'w') as f:
        f.write(compile_flags)
        f.write('-isystem%s/include\n'%target_props['sysroot'])
        #csi
        f.write('-isystem%s/include\n'%target_props['csi_core'])
        f.write('-isystem%s/include\n'%target_props['csi_driver'])
        for dir in target_props['includedirs']:
            f.write(f'-I{path.join(root, dir)}\n')
        #std
        f.write('-Drsize_t=size_t\n')
        for define in target_props['defines']:
            f.write(f'-D{define}\n')

if __name__ == '__main__':
    args = parser.parse_args()
    props = paser_cdk_project(args.project)
    root = path.dirname(args.project)
    for target_name, target_props in props.items():
        print(f'Use target: {target_name} [Y]/N')
        if input().upper() == 'N':
            continue
        target_props['sysroot'] = get_sysroot(args.CDK, target_props['tool'])
        target_props['csi_core'] = path.join(args.CDK, 'CDK\CSKY\csi\csi_core')
        target_props['csi_driver'] = path.join(args.CDK, 'CDK\CSKY\csi\csi_driver')
        gen_compile_flags(target_name, target_props)

