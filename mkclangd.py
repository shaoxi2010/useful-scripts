# 用于快速创建clangd项目描述文件，方便代码阅读
# 注意未必会与实际匹配

from os import walk, path
	
pwd = path.abspath(path.dirname(__file__))

compile_flags_nolibc = """
-target
arm-none-eabi
-xc
-ffreestanding
-nostdinc
-nostdlib
"""

if __name__ == "__main__":
    includes = set()
    for root, dirs, files in walk(pwd):
        if any(map(lambda x: x.endswith(".h"), files)):
            includes.add(root)
    with open("compile_flags.txt", "w") as f:
        f.write(compile_flags_nolibc)
        for dir in includes:
            f.write("-I%s\n" % dir)