# Security Policy

## Supported Versions

We support only the latest major version of Home Assistant Test Harness with security updates. This includes all minor and patch versions within that major version.

For example, if the latest version is 2.3.1, all 2.x.x versions are supported, but 1.x.x versions are not.

**We strongly recommend always using the latest released version** to ensure you have the most recent security fixes and features.

## Reporting a Vulnerability

We take the security of Home Assistant Test Harness seriously. If you discover a security vulnerability, please report it responsibly.

### How to Report

**Please do not report security vulnerabilities through public GitHub issues.**

Instead, please use GitHub's private vulnerability reporting feature:

1. Navigate to the [Security tab](https://github.com/HeadlessTarry/HomeAssistant-Test-Harness/security) of this repository
2. Click **"Report a vulnerability"**
3. Fill out the vulnerability report form with the details below

### What to Include

When using GitHub's vulnerability reporting form, please include the following information:

1. **Description**: Clear description of the vulnerability
2. **Impact**: Potential impact and severity assessment
3. **Reproduction**: Step-by-step instructions to reproduce the issue
4. **Affected versions**: Which versions are affected (if known)
5. **Proof of concept**: Code or commands demonstrating the vulnerability (if applicable)
6. **Suggested fix**: If you have ideas on how to fix it (optional)

### What to Expect

After submitting a report, you can expect:

1. **Acknowledgment**: We'll acknowledge receipt of your report
2. **Assessment**: We'll provide an initial assessment
3. **Updates**: We'll keep you informed of progress toward a fix
4. **Resolution**: Once fixed, we'll notify you and coordinate disclosure
5. **Credit**: With your permission, we'll credit you in the security advisory

### Security Update Process

When a security vulnerability is confirmed:

1. We'll develop and test a fix
2. We'll prepare a security advisory
3. We'll release a new version with the fix
4. We'll publish the security advisory with details
5. We'll update this SECURITY.md with the new supported version

## Security Best Practices

When using Home Assistant Test Harness:

- **Keep updated**: Always use the latest version
- **Isolate testing**: Run tests in isolated environments (Docker containers)
- **Protect credentials**: Never commit real credentials or secrets to version control
- **Review logs**: Check Docker container logs for any suspicious activity
- **Network isolation**: Consider using Docker networks to isolate test containers
- **Dependency updates**: Keep Python and Docker dependencies up to date

## Known Security Considerations

### Docker Container Security

This tool runs Docker containers with Home Assistant. Consider:

- Containers run with default Docker security settings
- Test credentials are ephemeral and generated per-session
- No privileged container access is required
- Containers are automatically cleaned up after tests

### Test Data

- Test data is isolated within Docker containers
- Configuration directories are mounted read-write (Home Assistant requires this)
- No real credentials should be used in test configurations

## Scope

Security issues within scope:

- **Code execution vulnerabilities** in the harness itself
- **Credential handling issues** in the harness or setup scripts
- **Docker container escape** scenarios
- **Dependency vulnerabilities** in required packages
- **Injection vulnerabilities** in Docker Compose or shell commands

Out of scope:

- Vulnerabilities in Home Assistant itself (report to the Home Assistant project)
- Vulnerabilities in Docker Engine
- Issues in user's test configurations
- General Docker security hardening recommendations

## Attribution

We appreciate the work of security researchers and will publicly acknowledge contributors who report valid security issues (with their permission).

---

Thank you for helping keep Home Assistant Test Harness and its users safe!
