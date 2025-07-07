# Suggested Commands for MountainStat Development

## Package Management (Yarn)
```bash
# Install dependencies
yarn

# Add new dependency
yarn add <package-name>

# Add dev dependency
yarn add -D <package-name>

# Update dependencies
yarn upgrade
```

## Development Commands
```bash
# Start development server with network access
yarn dev
# or explicitly with host flag
yarn run dev --host

# Build for production
yarn build

# Preview production build
yarn preview
```

## Darwin/macOS System Commands
```bash
# File operations
ls -la              # List files with details
find . -name "*.jsx"  # Find files by pattern
grep -r "pattern" .   # Search in files recursively
rg "pattern"          # Faster search with ripgrep

# Git commands
git status
git diff
git add .
git commit -m "message"
git push
git log --oneline

# Process management
ps aux | grep node    # Find node processes
lsof -i :5173        # Check what's using port 5173
kill -9 <PID>        # Force kill process

# Network debugging
netstat -an | grep LISTEN  # Show listening ports
curl -I <URL>             # Check HTTP headers
```

## API Testing (Node-RED endpoints)
```bash
# Test API endpoints
curl https://nodered.mtnhouse.casa/hvac/system/mode?mode=Heat
curl https://nodered.mtnhouse.casa/hvac/system/fan?fan=Auto
curl https://nodered.mtnhouse.casa/hvac/zone/hold/1?enable=true
curl https://nodered.mtnhouse.casa/hvac/zone/temp/1?temp=72
curl https://nodered.mtnhouse.casa/hvac/allmode?allmode=1
```

## Development Notes
- Connect using Tailscale IP for hot reload to work properly
- No linting or formatting tools configured
- No test framework configured