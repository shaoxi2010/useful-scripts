from paramiko import SSHClient,RSAKey,AutoAddPolicy
from argparse import ArgumentParser
from os import path

parser = ArgumentParser()
parser.add_argument('host', help='Hostname or IP address')
parser.add_argument('remote', help='chosse a remote file path')
parser.add_argument('local', help='chosse a local file path')
parser.add_argument('-p', '--port', type=int, default=22, help='SSH port (default: 22)')
parser.add_argument('-u', '--user', default='root', help='SSH username (default: root)')
parser.add_argument('-k', '--key', help='Path to private key file')

if __name__ == '__main__':
	args = parser.parse_args()
	private_key = RSAKey.from_private_key_file(args.key)
	with SSHClient() as client:
		client.set_missing_host_key_policy(AutoAddPolicy())
		client.connect(args.host, port=args.port, username=args.user, pkey=private_key)
		stdin, stdout, stderr = client.exec_command(f'dd if={args.remote}')
		localfile = path.join(args.local, path.basename(args.remote)) if path.isdir(args.local) else args.local
		with open(localfile,  'wb') as w:
			while data := stdout.read(4096):
				w.write(data)