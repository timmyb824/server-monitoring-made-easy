#!/bin/bash

# Create necessary directories if they don't exist
mkdir -p logs
chmod 777 logs  # This ensures the container can write to the directory regardless of user

# Export current user's UID and GID for docker-compose
export SME_UID=$(id -u)
export SME_GID=$(id -g)

echo "Setup complete. You can now run: docker-compose up"
