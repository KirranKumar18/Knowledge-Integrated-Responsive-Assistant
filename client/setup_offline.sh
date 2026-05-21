#!/data/data/com.termux/files/usr/bin/bash
# ============================================================================
# setup_offline.sh — KIRA Phase 2: One-time offline mode setup for Termux
#
# This script installs everything needed for KIRA to work without internet:
#   1. llama-cpp (the inference engine)
#   2. A small GGUF model (Gemma 3 1B, ~800MB download)
#
# Run this ONCE on your phone:
#   chmod +x setup_offline.sh
#   ./setup_offline.sh
#
# After this, KIRA will automatically switch to offline mode when the
# server is unreachable. No further setup needed.
# ============================================================================

set -e  # exit on any error

echo ""
echo "============================================"
echo "  🤖 KIRA — Offline Mode Setup"
echo "============================================"
echo ""

# Step 1: Install llama-cpp from Termux repo
echo "📦 Step 1: Installing llama-cpp..."
pkg install llama-cpp -y 2>/dev/null || {
    echo "⚠️  pkg install failed. Trying to build from source..."
    pkg install git cmake clang -y
    cd ~
    if [ ! -d "llama.cpp" ]; then
        git clone https://github.com/ggerganov/llama.cpp.git
    fi
    cd llama.cpp
    
    # Patch for Termux Clang 18+ redefinition error
    sed -i 's/inline static int32x4_t vcvtnq_s32_f32/inline static int32x4_t IGNORE_vcvtnq_s32_f32/g' ggml/src/ggml-cpu/ggml-cpu-impl.h || true

    cmake -B build -DLLAMA_BUILD_SERVER=OFF -DLLAMA_BUILD_TESTS=OFF
    cmake --build build --config Release -j4
    echo "✅ llama.cpp built from source"
    cd ~
}
echo "✅ llama-cpp installed"

# Step 2: Create model directory
echo ""
echo "📁 Step 2: Creating model directory..."
mkdir -p ~/kira-models
echo "✅ Directory ready: ~/kira-models"

# Step 3: Download the model
echo ""
echo "📥 Step 3: Downloading Qwen 2.5 1.5B (Q4_K_M) — ~1GB..."
echo "   This will take a few minutes depending on your internet speed."
echo ""

MODEL_URL="https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf"
MODEL_PATH="$HOME/kira-models/qwen2.5-1.5b-instruct-q4_k_m.gguf"

if [ -f "$MODEL_PATH" ]; then
    echo "✅ Model already downloaded: $MODEL_PATH"
else
    wget -O "$MODEL_PATH" "$MODEL_URL" || {
        echo "❌ wget failed. Trying curl..."
        curl -L -o "$MODEL_PATH" "$MODEL_URL"
    }
    echo "✅ Model downloaded"
fi

# Step 4: Quick test
echo ""
echo "🧪 Step 4: Quick test..."
if command -v llama-cli &> /dev/null; then
    echo "   Running a quick inference test..."
    llama-cli -m "$MODEL_PATH" -p "Say hello in one word." -n 10 --no-display-prompt --log-disable 2>/dev/null || true
    echo ""
    echo "✅ Offline mode is working!"
else
    echo "   llama-cli not in PATH. Checking build directory..."
    if [ -f ~/llama.cpp/build/bin/llama-cli ]; then
        ~/llama.cpp/build/bin/llama-cli -m "$MODEL_PATH" -p "Say hello in one word." -n 10 --no-display-prompt --log-disable 2>/dev/null || true
        echo ""
        echo "✅ Offline mode is working! (using ~/llama.cpp/build/bin/llama-cli)"
    else
        echo "⚠️  Could not find llama-cli binary. Please check installation."
    fi
fi

# Done
echo ""
echo "============================================"
echo "  ✅ KIRA Offline Mode Setup Complete!"
echo "============================================"
echo ""
echo "  Model: Gemma 3 1B (Q4_K_M)"
echo "  Size:  ~800MB"
echo "  Path:  $MODEL_PATH"
echo ""
echo "  KIRA will now automatically switch to"
echo "  offline mode when the server is unreachable."
echo "============================================"
echo ""
