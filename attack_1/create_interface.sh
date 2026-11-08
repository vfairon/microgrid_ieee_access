
if [ "$1" = "-q" ]; then
    sudo ip link delete vlaptop
    echo "deleted link"
    exit
fi

sudo ip link add vlaptop type veth peer name vlaptop-br
sudo ip link set vlaptop-br master b.40.1
sudo ip link set vlaptop-br up
sudo ip addr add 10.0.14.21/24 dev vlaptop
sudo ip link set vlaptop up

