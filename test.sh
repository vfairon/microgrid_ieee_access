# Define the container name given by user
TARGET_NAME="master"  # <-- Replace this with your actual container name

# Start the container with that name (if not already running)
docker start "$TARGET_NAME" >/dev/null 2>&1 || {
    echo "❌ Failed to start container $TARGET_NAME. Does it exist?"
    exit 1
}

# Get its container ID
EXCLUDE_ID=$(docker inspect -f '{{.Id}}' "$TARGET_NAME")


for container in $(docker ps -q); do
    if [ "$container" != "bfb818df3960" ]; then
        docker cp setup_and_connect.sh "$container:/setup_and_connect.sh"
        echo "Copied setup_and_connect.sh to container $container"
    else
        echo "Skipping container $container"
    fi
done

