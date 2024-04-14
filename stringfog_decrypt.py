from os import path, walk, replace
from contextlib import contextmanager
from argparse import ArgumentParser
from re import findall
import jpype

pwd = path.abspath(path.dirname(__file__))
paser = ArgumentParser()
paser.add_argument("source", help="source file path")


@contextmanager
def jvm_with_jar(jarpath):
    try:
        jpype.startJVM(
            jpype.getDefaultJVMPath(),
            "-Djava.class.path=%s" % jarpath,
            convertStrings=True,
        )
        yield
    finally:
        jpype.shutdownJVM()


# 将文本中的换行符和特殊字符转义
def escape_string(string):
    return string.encode().decode("unicode_escape")


def scan_crypto_string(decrypt_method, source):
    if path.basename(source) == "tmp.java":
        return
    tmpfile = path.join(path.dirname(source), "tmp.java")
    with open(source, "r") as f, open(tmpfile, "w+") as w:
        while line := f.readline():
            # 匹配加密字符串
            matches = findall(r"StringFog.OooO00o\((\".*?\"), (\".*?\")\)", line)
            if matches:
                decrypt_strings = [
                    decrypt_method(escape_string(x[0]), escape_string(x[1]))
                    for x in matches
                ]
                w.write(f"// {' '.join(decrypt_strings)}\n")
            w.write(line)
    replace(tmpfile, source)


if __name__ == "__main__":
    args = paser.parse_args()
    with jvm_with_jar(path.join(pwd, "com.github.megatronking.stringfog.jar")):
        xor = jpype.JClass("com.github.megatronking.stringfog.xor.StringFogImpl")
        base64 = jpype.JClass("com.github.megatronking.stringfog.Base64")

        def decrypt(ciphertext, key):
            return xor().decrypt(base64.decode(ciphertext, 0), base64.decode(key, 0))

        for root, _, files in walk(args.source):
            for file in files:
                filepath = path.join(root, file)
                scan_crypto_string(decrypt, filepath)
