# 用clang-format格式化文件，通过在文件夹下添加.formatignore文件
# 可以将同级别目录下的对应文件夹或文件忽略
# 配置网站 https://clang-format-configurator.site

from subprocess import check_call
from os import path, walk
from concurrent.futures import ThreadPoolExecutor

formattool = "/opt/homebrew/opt/llvm/bin/clang-format"
mutithreads = 4

pwd = path.abspath(path.dirname(__file__))

suffixs = [".c", ".h", ".cpp", ".hpp"]


def run_clang_fmt(file):
    print(f"Formatting {file}")
    check_call([formattool, "-i", file])


def formatignore(ignorefile):
    with open(ignorefile, "r") as f:
        return f.read().splitlines()


def get_format_files(root):
    file_list = []
    for root, dirs, files in walk(pwd):
        if ".formatignore" in files:
            for entry in formatignore(path.join(root, ".formatignore")):
                if path.isdir(path.join(root, entry)):
                    dirs.remove(entry)
                else:
                    files.remove(entry)
        for file in files:
            if file.endswith(tuple(suffixs)):
                file_list.append(path.join(root, file))
    return file_list


if __name__ == "__main__":
    file_list = get_format_files(pwd)
    print("Starting format using mutithread")
    with ThreadPoolExecutor(max_workers=mutithreads) as pool:
        pool.map(run_clang_fmt, file_list)
    print("format completed")
