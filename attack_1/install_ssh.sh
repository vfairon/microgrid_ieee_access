service ssh start
mkdir ~/.ssh
echo 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIHAtbR5kFXxw+Sfkv9xSkwciAzrNcsib7n+k04cY9etW vfairon@gmail.com' >> ~/.ssh/authorized_keys
chmod --recursive go-rwx ~/.ssh
chmod go-w ~