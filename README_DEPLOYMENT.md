# Deployment Guide

## Quick Setup (Recommended: SSH Keys)

1. **One-time setup** - Set up passwordless SSH:
   ```bash
   ./setup-passwordless-ssh.sh
   ```
   This will:
   - Generate an SSH key if you don't have one
   - Show you how to add it to the server
   - Test the connection

2. **Deploy automatically** (git push + deploy):
   ```bash
   ./deploy-auto.sh "Your commit message"
   ```
   Or just:
   ```bash
   ./deploy-auto.sh
   ```
   (Uses auto-generated commit message)

## Alternative: Password-Based (Less Secure)

If you prefer to use password instead of SSH keys:

1. **Store password in environment variable** (one-time per terminal session):
   ```bash
   export SERVER_PASSWORD="your_server_password"
   ```

2. **Install sshpass** (if not installed):
   - macOS: `brew install hudochenkov/sshpass/sshpass`
   - Linux: `sudo apt-get install sshpass`

3. **Modify deploy.sh** to use sshpass (see below)

## Manual Deployment

Just run:
```bash
./deploy.sh
```

## Notes

- SSH keys are more secure and don't require entering password each time
- The password is never stored in files (only in environment variable)
- After setting up SSH keys, `deploy.sh` and `deploy-auto.sh` will work without passwords
