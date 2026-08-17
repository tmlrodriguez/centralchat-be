# Sealena Commit Message Guidelines

To ensure consistency, readability, and clarity across the development team, all commits in the Sealena project must follow this structured format.

---

## Commit Message Structure

Each commit should include the following sections:

### 1. Commit Title

Format:
[module] Clear and concise description of the change

- Use lowercase for the module name (e.g., `auth`, `whatsapp`)
- Use the imperative mood (e.g., "add", "fix", "implement")
- Keep it under 70 characters

Examples:
- [auth] Add token-based authentication system

---

### 2. Commit Body (Bullet Points)

List what was done in detail using bullet points (-). Focus on the technical changes and affected areas.

Example:
- Added TokenAuthentication class to auth module
- Updated login endpoint to issue access and refresh tokens
- Added unit tests for token generation and validation

---

### 3. Notes

Explain why these changes were made or how they improve the system. Mention any impacts, future considerations, or resolved issues.

Example:
Notes:
Introduces secure token-based login, improving authentication performance and scalability. Prepares backend for future role-based access control.

---

## Full Template

[module] Short title of what was changed

- Bullet point describing the first technical change
- Bullet point describing the second change
- Bullet point describing any additional changes

Notes:
Brief explanation of why this change matters and how it impacts the project.

---

## Example Commit

[auth] Implement secure login with token authentication

- Replaced session-based login with JWT authentication
- Updated user model to support token generation
- Added unit tests for login and token validation flows

Notes:
Enhances security and enables future support for mobile authentication and third-party integrations.

---

## Guidelines

- Always commit atomic changes (one logical change per commit)
- Do not use vague titles like "fix stuff" or "updates"
- Use this format for every commit, even for small fixes
- If multiple modules are affected, use `core:` or list them separated by `+`

Example:
[auth + whatsapp] Optimize query for invoice aggregation