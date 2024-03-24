# 转换程序，用于想keil必须使用gbk2312会出现乱码
# windows bat必须采用crlf换行这些问题

from chardet import detect
from argparse import ArgumentParser
from os import path, walk, replace
from io import StringIO

def load_file(file_path) -> StringIO:
	with open(file_path, 'rb') as f:
		data = f.read()
		encoding = detect(data)['encoding']
		return StringIO(data.decode(encoding))

def covert_to_windows(file_path):
	shadow_file = path.join(path.dirname(file_path), 'windows_' + path.basename(file_path))
	with open(shadow_file, 'w', encoding='gb2312', errors='ignore') as f:
		content = load_file(file_path)
		while line := content.readline():
			f.write(line.strip() + '\r\n')
	replace(shadow_file, file_path)

def covert_to_linux(file_path):
	shadow_file = path.join(path.dirname(file_path), 'linux_' + path.basename(file_path))
	with open(shadow_file, 'w', encoding='utf-8', errors='ignore') as f:
		content = load_file(file_path)
		while line := content.readline():
			f.write(line.strip() + '\n')
	replace(shadow_file, file_path)

parser = ArgumentParser()
parser.print_help("将当前目录下的对应格式文件转换")
parser.add_argument('filetype', help='需要转换的文件类型')
parser.add_argument('-w', '--windows', help='将目标设置为windows', action='store_true')
parser.add_argument('-l', '--linux', help='将目标设置为linux', action='store_true')

pwd = path.abspath(path.dirname(__file__))

if __name__ == '__main__':
	args = parser.parse_args()
	for root, _, files in walk(pwd):
		for file in files:
			if file.endswith(f'.{args.filetype}'):
				file_path = path.join(root, file)
				if args.windows:
					covert_to_windows(file_path)
				if args.linux:
					covert_to_linux(file_path)