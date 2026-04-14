#!/bin/bash
set -e

FRIDAY_DIR="$HOME/Projects/friday"
CONFIG_DIR="$HOME/.config/friday"
DATA_DIR="$HOME/.local/share/friday"

# --- First-run: copy default config if needed ---
if [ ! -f "$CONFIG_DIR/config.toml" ]; then
    echo "First run detected. Setting up Friday..."
    mkdir -p "$CONFIG_DIR/tools/plugins"
    mkdir -p "$DATA_DIR/memory" "$DATA_DIR/history"
    cp "$FRIDAY_DIR/config/config.toml" "$CONFIG_DIR/"
    cp "$FRIDAY_DIR/config/SOUL.md" "$CONFIG_DIR/"
    cp "$FRIDAY_DIR/config/USER.md" "$CONFIG_DIR/"
    cp "$FRIDAY_DIR/config/AGENTS.md" "$CONFIG_DIR/"
    cp "$FRIDAY_DIR/config/BOOTSTRAP.md" "$CONFIG_DIR/"
    echo "Config written to $CONFIG_DIR"
fi

# --- Load .env if it exists ---
if [ -f "$FRIDAY_DIR/.env" ]; then
    set -a
    source "$FRIDAY_DIR/.env"
    set +a
fi

# --- Start Python backend ---
echo "Starting Friday AI backend..."
cd "$FRIDAY_DIR"
.venv/bin/uvicorn friday_ai.server:app \
    --host 127.0.0.1 \
    --port 65535 \
    --log-level warning \
    > "$DATA_DIR/uvicorn.log" 2>&1 &
BACKEND_PID=$!

# Wait for backend to be ready
for i in {1..10}; do
    if curl -s http://127.0.0.1:65535/health > /dev/null 2>&1; then
        break
    fi
    sleep 0.5
done

# --- Parse args ---
case "${1:-}" in
    --install-keybind)
        "$FRIDAY_DIR/bin/friday-install-keybind"
        exit 0
        ;;
    --daemon)
        # Start Rust core in daemon mode (socket listener + panel)
        cd "$FRIDAY_DIR/friday_core"
        if [ ! -f "target/release/friday_core" ]; then
            cargo build --release 2>&1 | tail -1
        fi
        ./target/release/friday_core --daemon &
        RUST_PID=$!

        # Start Chrome bridge if google mode is active
        CHROME_PID=""
        MODE=$(grep "provider_mode" "$CONFIG_DIR/config.toml" 2>/dev/null | cut -d'"' -f2)
        if [ "$MODE" = "google" ]; then
            echo "Google mode detected — starting Chrome bridge..."
            "$FRIDAY_DIR/bin/friday-chrome-bridge" start
            CHROME_PID=$(cat /tmp/friday-chrome-bridge.pid 2>/dev/null)
        fi

        trap "kill $BACKEND_PID $RUST_PID 2>/dev/null; [ -n '$CHROME_PID' ] && $FRIDAY_DIR/bin/friday-chrome-bridge stop" EXIT
        # Wait on both — if either dies, cleanup
        wait $BACKEND_PID $RUST_PID
        ;;
    --cli-only|"")
        # Start Rust core
        cd "$FRIDAY_DIR/friday_core"
        if [ -f "target/release/friday_core" ]; then
            ./target/release/friday_core "${@}"
        else
            echo "Building Friday Core (first time)..."
            cargo build --release 2>&1 | tail -1
            ./target/release/friday_core "${@}"
        fi
        # Cleanup
        echo "Shutting down backend..."
        kill $BACKEND_PID 2>/dev/null
        ;;
esac
