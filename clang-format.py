# 用clang-format格式化文件，通过在文件夹下添加.formatignore文件
# 可以将同级别目录下的对应文件夹或文件忽略
# 配置网站 https://clang-format-configurator.site

from subprocess import check_call
from os import path, walk
from concurrent.futures import ThreadPoolExecutor

mutithreads = 8

pwd = path.abspath(path.dirname(__file__))

suffixs = ['.c', '.h', '.cpp', '.hpp']

def run_clang_fmt(files):
    for file in files:
        print(f"Formatting {file}")
        check_call(["/opt/homebrew/opt/llvm/bin/clang-format", "-i", file])


def split_list(lst, n):
    return [lst[i : i + n] for i in range(0, len(lst), n)]


def formatignore(ignorefile):
    with open(ignorefile, 'r') as f:
        return f.read().splitlines()

if __name__ == "__main__":
    file_list = []
    for root, dirs, files in walk(pwd):
        if '.formatignore' in files:
            for entry in formatignore(path.join(root, '.formatignore')):
                if path.isdir(path.join(root, entry)):
                    dirs.remove(entry)
                else:
                    files.remove(entry)
        for file in files:
            if file.endswith(tuple(suffixs)):
                file_list.append(path.join(root, file))

    print("Starting format using mutithread")
    pool = ThreadPoolExecutor(max_workers=mutithreads)  
    for file_chunk in split_list(file_list, 10):
        pool.submit(run_clang_fmt, file_chunk)
    print("format completed")
