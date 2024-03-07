#!/usr/bin/env python3

from argparse import ArgumentParser
from subprocess import check_call
from os import chmod, path, remove, environ
from tempfile import NamedTemporaryFile

difftoolscript = """\
from argparse import ArgumentParser
from os import environ, path
from zipfile import ZipFile
parser = ArgumentParser("compressdiff")
parser.add_argument("left", help="left file for compare")
parser.add_argument("right", help="right file for compare")

args = parser.parse_args()
leftfile = environ['LEFTFILE'] if environ['LEFTFILE'] else 'left.zip'
rightfile = environ['RIGHTFILE'] if environ['RIGHTFILE'] else 'right.zip'
with ZipFile(leftfile, "a") as lf, ZipFile(rightfile, "a") as rf:
	if path.getsize(args.left):
		lf.write(args.left, environ["BASE"])
	if path.getsize(args.right):
		rf.write(args.right, environ["BASE"])
"""

parser = ArgumentParser("gitdiff2zip")
parser.add_argument("revnew", help="new revision", type=str)
parser.add_argument("revold", help="old revision", type=str)
parser.add_argument("-r", "--repo", help="path to repository", default=".")
parser.add_argument("--filenew", help="path to new file", default="new.zip")
parser.add_argument("--fileold", help="path to old file", default="old.zip")


def dumpdiff(repo, revnew, revold, filenew, fileold):
    if path.exists(path.join(repo, filenew)):
        remove(path.join(repo, filenew))
    if path.exists(path.join(repo, fileold)):
        remove(path.join(repo, fileold))
    env = environ.copy()
    env["LEFTFILE"] = "old.zip"
    env["RIGHTFILE"] = "new.zip"
    # windows的API行为与UNIX不一致，这里采用了手动删除进行
    script = NamedTemporaryFile(mode="w+", delete=False)
    script.write(difftoolscript)
    script.flush()
    script.close()
    check_call(
        ["git", "difftool", "-x", f"python3 '{script.name}'", "-y", revold, revnew],
        cwd=repo,
        env=env,
    )
    remove(script.name)


if __name__ == "__main__":
    args = parser.parse_args()
    dumpdiff(args.repo, args.revnew, args.revold, args.filenew, args.fileold)
