#!/usr/bin/env python3

from argparse import ArgumentParser
from subprocess import check_call
from os import chmod, path, remove, environ
from tempfile import NamedTemporaryFile

difftoolcode = """\
#!/usr/bin/env python3

from argparse import ArgumentParser
from os import environ, path
from zipfile import ZipFile
parser = ArgumentParser("compressdiff")
parser.add_argument("left", help="left file for compare")
parser.add_argument("right", help="right file for compare")

if __name__ == "__main__":
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
parser.add_argument("revnew", help="new revision")
parser.add_argument("revold", help="old revision")
parser.add_argument("-r", "--repo", help="path to repository", default=".")
parser.add_argument("--filenew", help="path to new file", default="new.zip")
parser.add_argument("--fileold", help="path to old file", default="old.zip")


def dumpdiff(repo, revnew, revold, filenew, fileold):
    if path.exists(filenew):
        remove(filenew)
    if path.exists(fileold):
        remove(fileold)
    with NamedTemporaryFile(mode="w+") as tf:
        env = environ.copy()
        env["LEFTFILE"] = "old.zip"
        env["RIGHTFILE"] = "new.zip"
        tf.write(difftoolcode)
        tf.flush()
        chmod(tf.name, 0o766)
        check_call(
            ["git", "difftool", "-x", tf.name, "-y", revold, revnew],
            cwd=repo,
            env=env
        )


if __name__ == "__main__":
    args = parser.parse_args()
    dumpdiff(args.repo, args.revnew, args.revold, args.filenew, args.fileold)
