#!/bin/bash

# Function to print messages
print_step() {
    echo "===> $1"
}

print_error() {
    echo "ERROR: $1" >&2
}

# Function to create directories with proper permissions
create_directories() {
    local user=$1
    local is_container=$2

    if [ "$is_container" = true ]; then
        # For container environment, create local directories that will be mounted
        mkdir -p ./logs
        mkdir -p ./run
        chmod -R 777 ./logs ./run  # Allow any user to write
        print_step "Created container mount directories with proper permissions"
    else
        # For local environment
        if [ "$EUID" -eq 0 ]; then
            # Running as root
            mkdir -p /var/log/sme
            mkdir -p /var/run/sme
            chmod -R 755 /var/log/sme /var/run/sme
            print_step "Created system directories with proper permissions"
        else
            # Running as non-root
            mkdir -p "$HOME/.local/sme/logs"
            mkdir -p "$HOME/.local/sme/run"
            chmod -R 700 "$HOME/.local/sme"
            print_step "Created local directories with proper permissions"
        fi
    fi
}

# Function to set up Python environment
setup_python_env() {
    if ! command -v python3 >/dev/null 2>&1; then
        print_error "Python 3 is not installed. Please install Python 3 first."
        exit 1
    fi

    if ! command -v pip3 >/dev/null 2>&1; then
        print_error "pip3 is not installed. Please install pip3 first."
        exit 1
    fi

    # Create virtual environment if it doesn't exist
    if [ ! -d ".venv" ]; then
        python3 -m venv .venv
        print_step "Created Python virtual environment"
    fi

    # Activate virtual environment and install dependencies
    source .venv/bin/activate
    pip install -r requirements.txt
    print_step "Installed Python dependencies"
}

# Main setup logic
main() {
    local is_container=false
    local skip_python=false

    # Parse command line arguments
    while [[ "$#" -gt 0 ]]; do
        case $1 in
        --container) is_container=true ;;
        --skip-python) skip_python=true ;;
        *)
            print_error "Unknown parameter: $1"
            exit 1
            ;;
        esac
        shift
    done

    # Check if running as root
    local user="regular"
    if [ "$EUID" -eq 0 ]; then
        user="root"
    fi

    # Create necessary directories with proper permissions
    if [ "$is_container" = true ]; then
        # For container environment, create local directories that will be mounted
        mkdir -p ./logs
        mkdir -p ./run
        chmod -R 777 ./logs ./run  # Allow any user to write
        print_step "Created container mount directories with proper permissions"
    else
        # For local environment
        if [ "$EUID" -eq 0 ]; then
            # Running as root
            mkdir -p /var/log/sme
            mkdir -p /var/run/sme
            chmod -R 755 /var/log/sme /var/run/sme
            print_step "Created system directories with proper permissions"
        else
            # Running as non-root
            mkdir -p "$HOME/.local/sme/logs"
            mkdir -p "$HOME/.local/sme/run"
            chmod -R 700 "$HOME/.local/sme"
            print_step "Created local directories with proper permissions"
        fi
    fi

    # Set up Python environment if not skipped
    if [ "$skip_python" = false ]; then
        setup_python_env
    fi

    if [ "$is_container" = true ]; then
        # Export current user's UID and GID for docker-compose
        export SME_UID=$(id -u)
        export SME_GID=$(id -g)
        print_step "Exported user UID and GID for container"
        echo -e "\nSetup complete! You can now run: docker-compose up or podman-compose up"
    else
        echo -e "\nSetup complete! Next steps:"
        echo "1. Initialize configuration: sme init"
        echo "2. Review and customize the generated config.yaml"
        echo "3. Start monitoring: sme start"
    fi
}

# Run main function with all arguments
main "$@"
