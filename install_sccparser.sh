#!/usr/bin/env zsh
# SCC Parser Installation Script
# Adds sccparser command to your shell and sets up auto-start on login

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ALIAS_NAME="sccparser"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  SCC Parser Installation"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check if .zshrc exists
ZSHRC="$HOME/.zshrc"
if [ ! -f "$ZSHRC" ]; then
    echo "Creating .zshrc..."
    touch "$ZSHRC"
fi

# Add the alias/function to .zshrc
ALIAS_LINE="alias sccparser='$SCRIPT_DIR/sccparser'"

# Check if alias already exists
if grep -q "alias sccparser=" "$ZSHRC" 2>/dev/null; then
    echo "✓ sccparser alias already exists in .zshrc"
else
    echo "" >> "$ZSHRC"
    echo "# SCC Parser - Legal Citation Manager" >> "$ZSHRC"
    echo "$ALIAS_LINE" >> "$ZSHRC"
    echo "✓ Added sccparser alias to .zshrc"
fi

# Add optional auto-start on login (commented out by default)
if ! grep -q "SCC Parser Auto-start" "$ZSHRC" 2>/dev/null; then
    cat >> "$ZSHRC" << 'EOF'

# SCC Parser Auto-start (uncomment to start on login)
# [[ -z "$TMUX" ]] && "$HOME/Desktop/Mac/sccparser/sccparser" start &
EOF
    echo "✓ Added auto-start option to .zshrc (commented by default)"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Installation Complete!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "To use the sccparser command:"
echo "  1. Run:  source ~/.zshrc"
echo "  2. Or restart your terminal"
echo ""
echo "Then you can use:"
echo "  sccparser on       - Start SCC Parser 24/7"
echo "  sccparser off      - Stop SCC Parser"
echo "  sccparser status   - Check status"
echo "  sccparser logs     - View logs"
echo ""
echo "For auto-start on login, uncomment the relevant lines in .zshrc"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
