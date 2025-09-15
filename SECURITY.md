# Security Policy

## Supported Versions

QQQ Orb follows semantic versioning and provides security updates for the following versions:

| Version | Supported          | End of Life |
| ------- | ------------------ | ----------- |
| 2.1.x   | :white_check_mark: | TBD         |
| 2.0.x   | :white_check_mark: | TBD         |
| 1.x.x   | :white_check_mark: | TBD         |
| < 1.0   | :x:                | EOL         |

**Note**: We recommend using the latest stable version for security updates.

## Reporting a Vulnerability

**🚨 Security vulnerabilities should NEVER be reported publicly.**

If you discover a security vulnerability in QQQ Orb, please report it privately:

### **Email Security Reports**
Send security reports to: **security@kingsrook.com**

### **What to Include**
- **Description**: Clear description of the vulnerability
- **Impact**: Potential impact on users and CI/CD systems
- **Reproduction**: Steps to reproduce the issue
- **Environment**: QQQ Orb version, CircleCI version, OS details
- **Timeline**: If you need disclosure by a specific date

### **Response Timeline**
- **Initial Response**: Within 24 hours
- **Assessment**: Within 3 business days
- **Update**: Regular updates on progress
- **Resolution**: As quickly as possible based on severity

### **What Happens Next**
1. **Acknowledgment**: We'll acknowledge receipt within 24 hours
2. **Investigation**: Our security team will investigate the report
3. **Assessment**: We'll assess the severity and impact
4. **Fix Development**: Develop and test a security fix
5. **Release**: Release a security update
6. **Disclosure**: Public disclosure with credit (if requested)

## Security Best Practices

### **For Users**
- **Keep Updated**: Always use the latest stable version
- **Monitor Releases**: Watch for security advisories
- **Report Issues**: Report any security concerns immediately
- **Follow Guidelines**: Use QQQ Orb according to security best practices
- **Secure Contexts**: Ensure CircleCI contexts contain only necessary secrets

### **For Contributors**
- **Security Review**: All code changes undergo security review
- **Dependency Scanning**: Regular vulnerability scanning of dependencies
- **Secure Development**: Follow secure coding practices
- **Testing**: Security testing is part of our development process
- **Secret Management**: Never commit secrets or credentials

## Security Features

QQQ Orb includes several security features:

- **Input Validation**: Comprehensive input validation and sanitization
- **Secret Management**: Secure handling of CI/CD secrets and credentials
- **Audit Logging**: Comprehensive audit trails for CI/CD events
- **Secure Defaults**: Secure-by-default configuration
- **Dependency Scanning**: Regular scanning of orb dependencies

## Security Updates

### **Release Process**
Security updates follow our standard [Release Flow](https://github.com/Kingsrook/qqq/wiki/Release-Flow):

1. **Security Fix**: Develop and test security fix
2. **Release Branch**: Create release branch for security update
3. **Testing**: Thorough testing of security fix
4. **Release**: Release security update to users
5. **Communication**: Notify users of security update

### **Update Notifications**
- **GitHub Releases**: Security updates announced in release notes
- **Security Advisories**: GitHub security advisories for critical issues
- **Email Notifications**: Direct notifications for critical vulnerabilities
- **CircleCI Registry**: Updated orb versions in CircleCI registry

## CI/CD Security Considerations

### **CircleCI Context Security**
- **Minimal Permissions**: Use least-privilege access for contexts
- **Secret Rotation**: Regularly rotate secrets and credentials
- **Access Control**: Limit access to sensitive contexts
- **Audit Logs**: Monitor context usage and access

### **Orb Security**
- **Version Pinning**: Always pin specific orb versions
- **Source Verification**: Verify orb source and integrity
- **Regular Updates**: Keep orb versions up to date
- **Security Scanning**: Scan orb dependencies regularly

## Contact Information

- **Security Email**: security@kingsrook.com
- **General Contact**: contact@kingsrook.com
- **Company**: Kingsrook, LLC
- **Website**: https://qrun.io

---

**Thank you for helping keep QQQ Orb secure!** 🛡️