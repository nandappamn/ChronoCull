---
name: cybersecurity-audit
description: >-
  Perform defensive cybersecurity assessments, threat modeling (STRIDE), static code analysis,
  credential leak detection, and vulnerability remediation. Use this skill when asked to review
  code security, analyze attack surfaces, triage vulnerabilities, or audit dependencies.
---

# Cybersecurity Audit Skill

Inspired by [`mukul975/Anthropic-Cybersecurity-Skills`](https://github.com/mukul975/Anthropic-Cybersecurity-Skills) and Anthropic's defensive security harness, this skill equips the agent to perform disciplined security reviews adhering to industry standards (MITRE ATT&CK, NIST CSF 2.0, OWASP Top 10).

## When to Use

- Conducting Pre-PR security scans for hardcoded secrets, API tokens, or private keys.
- Auditing backend code for injection vectors (SQLi, Command Injection, SSRF, Path Traversal).
- Threat modeling software architectures using the STRIDE methodology.
- Verifying defensive configurations (TLS settings, CSP headers, rate-limiting rules).

---

## 4-Step Defensive Audit Protocol

### Step 1: Automated Static Analysis (SAST)
Run the built-in scanner script in `scripts/security_scan.py` against the target directory:

```bash
# Scan current repository for common security anti-patterns and exposed secrets
python .agents/skills/cybersecurity-audit/scripts/security_scan.py --target .
```

### Step 2: Architecture & Threat Modeling (STRIDE)
Examine components against STRIDE categories:
1. **Spoofing**: Are authentication tokens cryptographically signed and validated?
2. **Tampering**: Are data payloads integrity-checked with HMACs or checksums?
3. **Repudiation**: Are critical audit events logged securely without sensitive PII?
4. **Information Disclosure**: Are stack traces, internal IPs, or secrets leaked in errors?
5. **Denial of Service**: Are request bodies capped and rate limits enforced?
6. **Elevation of Privilege**: Are RBAC / ABAC policies checked at the API boundary?

### Step 3: Dependency Vulnerability Check
Inspect package manifests (`requirements.txt`, `package.json`, `Cargo.lock`):
- Check for known high/critical CVEs.
- Avoid deprecated or unmaintained packages.

### Step 4: Actionable Remediation Output
Deliver findings using standard vulnerability formatting:
- **Vulnerability Title & Severity** (Critical / High / Medium / Low)
- **Vulnerable Code Location** (file and line numbers)
- **Attack Scenario & Impact**
- **Drop-in Remediated Code Snippet**

---

## Guardrails

- **Defensive Focus Only**: This skill is strictly for defensive auditing, code hardening, and authorized testing. Never generate functional exploit payloads against unauthorized targets.
