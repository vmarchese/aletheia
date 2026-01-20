---
inclusion: always
---

# Security and Encryption

## Security Overview

Aletheia handles sensitive data including:
- Cloud provider credentials
- API keys and tokens
- System logs and metrics
- Source code
- Session conversation history

All sensitive data must be properly secured.

## Session Encryption

### Encrypted Sessions (Default)

By default, sessions are encrypted with a password-protected key:

```bash
# Open encrypted session (prompts for password)
aletheia session open

# Password is used to encrypt/decrypt session data
# Session key is derived from password using PBKDF2
```

### Unsafe Mode (Development Only)

For development/testing, plaintext storage can be used:

```bash
# WARNING: Data stored in plaintext
aletheia session open --unsafe
```

**Never use `--unsafe` in production or with real credentials!**

## Encryption Implementation

### Session Key Derivation

```python
from aletheia.encryption import derive_key

# Derive encryption key from password
password = "user_password"
salt = os.urandom(32)  # Random salt per session
key = derive_key(password, salt)

# Key derivation uses PBKDF2-HMAC-SHA256
# 100,000 iterations for security
```

### Data Encryption

```python
from aletheia.encryption import encrypt_data, decrypt_data

# Encrypt sensitive data
plaintext = "sensitive information"
encrypted = encrypt_data(plaintext, key)

# Decrypt when needed
decrypted = decrypt_data(encrypted, key)
```

### Encryption Algorithm

- **Algorithm**: AES-256-GCM
- **Key Derivation**: PBKDF2-HMAC-SHA256
- **Iterations**: 100,000
- **Salt**: 32 bytes random per session
- **IV**: 16 bytes random per encryption

## Credential Storage

### Storage Types

#### 1. Environment Variables

```bash
# Simple but visible in process list
export AWS_ACCESS_KEY_ID=AKIA...
export AWS_SECRET_ACCESS_KEY=secret...
export PROMETHEUS_PASSWORD=password
```

**Pros**: Simple, works everywhere
**Cons**: Visible in process list, shell history

#### 2. System Keychain

```bash
# Store in OS keychain
aletheia config set-credential aws access_key_id
aletheia config set-credential aws secret_access_key

# Credentials stored in:
# - macOS: Keychain Access
# - Windows: Credential Manager
# - Linux: Secret Service (gnome-keyring, kwallet)
```

**Pros**: Most secure, OS-managed
**Cons**: Requires user interaction, platform-specific

#### 3. Encrypted File

```bash
# Store in encrypted file
aletheia session open --encrypted

# Credentials stored in:
# ~/.config/aletheia/credentials.enc
```

**Pros**: Portable, no OS dependencies
**Cons**: Requires password on each session

### Credential Access

```python
from aletheia.config import Config

config = Config()

# Credentials loaded based on credentials_type
# Automatically decrypted if needed
aws_key = config.get_credential("aws", "access_key_id")
```

## Secrets Management Best Practices

### 1. Never Commit Secrets

```bash
# Add to .gitignore
echo "config.yaml" >> .gitignore
echo ".env" >> .gitignore
echo "credentials.enc" >> .gitignore
```

### 2. Use Environment Variables for CI/CD

```yaml
# GitHub Actions example
env:
  ALETHEIA_OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
  AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
  AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
```

### 3. Rotate Credentials Regularly

```bash
# Update credentials
aletheia config set-credential aws access_key_id
aletheia config set-credential aws secret_access_key

# Or update environment variables
export AWS_ACCESS_KEY_ID=new_key
export AWS_SECRET_ACCESS_KEY=new_secret
```

### 4. Use Least Privilege

Grant only necessary permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "logs:GetLogEvents",
        "logs:FilterLogEvents",
        "cloudwatch:GetMetricData"
      ],
      "Resource": "*"
    }
  ]
}
```

### 5. Audit Credential Usage

```bash
# Enable verbose logging to track credential usage
aletheia session open -vv

# Review session logs for credential access
aletheia session view <session_id>
```

## Session Data Security

### Session Storage Location

```
~/.local/share/aletheia/sessions/
├── INC-ABC123/
│   ├── metadata.json.enc      # Encrypted metadata
│   ├── messages.json.enc      # Encrypted conversation
│   ├── artifacts/             # Encrypted artifacts
│   │   ├── logs.txt.enc
│   │   └── metrics.json.enc
│   └── session.key.enc        # Encrypted session key
```

### What Gets Encrypted

1. **Conversation History**: All messages between user and agents
2. **Fetched Data**: Logs, metrics, traces, code
3. **Credentials**: API keys, passwords, tokens
4. **Metadata**: Session name, timestamps, agent info
5. **Artifacts**: Downloaded files, analysis results

### What Doesn't Get Encrypted

1. **Session ID**: Used for session identification
2. **Session List**: Basic session info for listing
3. **Configuration**: Non-sensitive config values

## Secure Session Export

```bash
# Export encrypted session
aletheia session export <session_id> --output session.enc

# Export includes:
# - Encrypted conversation history
# - Encrypted artifacts
# - Encryption metadata (salt, IV)
# - Does NOT include password/key

# Import requires same password
aletheia session import session.enc
```

## Network Security

### TLS/SSL Verification

```python
# Always verify SSL certificates
import requests

response = requests.get(
    "https://prometheus.example.com/api/v1/query",
    verify=True  # Default, always use
)
```

### Proxy Support

```bash
# Use corporate proxy
export HTTPS_PROXY=https://proxy.example.com:8080
export HTTP_PROXY=http://proxy.example.com:8080

# With authentication
export HTTPS_PROXY=https://user:pass@proxy.example.com:8080
```

### Certificate Pinning (Advanced)

```python
# Pin specific certificate
import requests

response = requests.get(
    "https://api.example.com",
    verify="/path/to/cert.pem"
)
```

## Code Security

### Input Validation

```python
from aletheia.utils.validation import validate_input

# Validate user input
def fetch_logs(namespace: str, pod_name: str) -> str:
    # Prevent command injection
    validate_input(namespace, pattern=r'^[a-z0-9-]+$')
    validate_input(pod_name, pattern=r'^[a-z0-9-]+$')
    
    # Safe to use in command
    cmd = f"kubectl logs -n {namespace} {pod_name}"
    return execute_command(cmd)
```

### Command Injection Prevention

```python
import shlex

# BAD: Vulnerable to injection
cmd = f"kubectl logs {user_input}"

# GOOD: Use parameterized commands
cmd = ["kubectl", "logs", user_input]

# GOOD: Escape shell arguments
cmd = f"kubectl logs {shlex.quote(user_input)}"
```

### Path Traversal Prevention

```python
import os
from pathlib import Path

def read_file(filename: str) -> str:
    # Prevent path traversal
    base_dir = Path("/safe/directory")
    file_path = (base_dir / filename).resolve()
    
    # Ensure path is within base directory
    if not file_path.is_relative_to(base_dir):
        raise ValueError("Invalid file path")
    
    return file_path.read_text()
```

## Dependency Security

### Regular Updates

```bash
# Update dependencies
uv pip install --upgrade -r requirements.txt

# Check for vulnerabilities
pip-audit

# Or use safety
safety check
```

### Pinned Versions

```txt
# requirements.txt - pin major versions
typer>=0.9.0,<1.0.0
pyyaml>=6.0,<7.0
cryptography>=41.0.0,<42.0.0
```

## Security Checklist

### Development

- [ ] Never commit credentials or API keys
- [ ] Use `.gitignore` for sensitive files
- [ ] Validate all user inputs
- [ ] Use parameterized commands
- [ ] Enable type checking with mypy
- [ ] Run security linters (bandit, safety)

### Deployment

- [ ] Use encrypted sessions in production
- [ ] Store credentials in keychain or encrypted file
- [ ] Use least privilege IAM policies
- [ ] Enable TLS/SSL verification
- [ ] Rotate credentials regularly
- [ ] Monitor credential usage
- [ ] Keep dependencies updated

### Code Review

- [ ] Check for hardcoded secrets
- [ ] Verify input validation
- [ ] Review command construction
- [ ] Check file path handling
- [ ] Verify encryption usage
- [ ] Review error messages (no sensitive data)

## Incident Response

### Credential Compromise

1. **Immediately rotate** compromised credentials
2. **Revoke** old credentials
3. **Audit** usage logs for unauthorized access
4. **Update** all systems with new credentials
5. **Review** how compromise occurred
6. **Implement** additional controls

### Data Breach

1. **Identify** what data was exposed
2. **Contain** the breach (revoke access)
3. **Assess** impact and affected users
4. **Notify** affected parties if required
5. **Remediate** vulnerability
6. **Document** incident and response

## Security Tools

### Static Analysis

```bash
# Check for security issues
bandit -r aletheia/

# Check dependencies
safety check

# Audit pip packages
pip-audit
```

### Secrets Scanning

```bash
# Scan for committed secrets
truffleHog --regex --entropy=True .

# Or use gitleaks
gitleaks detect --source . --verbose
```

### Encryption Testing

```python
# Test encryption/decryption
from aletheia.encryption import encrypt_data, decrypt_data, derive_key

password = "test_password"
salt = os.urandom(32)
key = derive_key(password, salt)

plaintext = "sensitive data"
encrypted = encrypt_data(plaintext, key)
decrypted = decrypt_data(encrypted, key)

assert plaintext == decrypted
```

## Compliance Considerations

### Data Retention

```bash
# Delete old sessions
aletheia session delete <session_id>

# Automatic cleanup (configure in config.yaml)
session_retention_days: 90
```

### Audit Logging

```bash
# Enable audit logging
export ALETHEIA_AUDIT_LOG=/var/log/aletheia/audit.log

# Log includes:
# - Session creation/deletion
# - Credential access
# - Data fetching operations
# - Agent invocations
```

### Data Residency

```bash
# Configure data storage location
export ALETHEIA_DATA_DIR=/compliant/storage/path

# Ensure location meets compliance requirements
# (e.g., GDPR, HIPAA, SOC2)
```
