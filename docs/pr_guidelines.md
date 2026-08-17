# Sealena Pull Request Guidelines

To ensure clarity, transparency, and team-wide consistency, all pull requests in the Sealena project must follow this structured format.

---

## Pull Request Structure

Each pull request should include the following sections:

### 1. Pull Request Title

Format:
Clear and concise description of the purpose of the PR

- Use imperative mood (e.g., "add", "fix", "implement")
- Keep it under 70 characters

Examples:
- Add token-based authentication system
- Fix invoice calculation bug
- Refactor plan renewal logic

---

### 2. Modules Affected

List the modules or components that were modified.

Example:
- auth
- users
- login API

---

### 3. Key Features and Enhancements

Bullet-point summary of major features or fixes included in the pull request.

Example:
- Implemented JWT-based login authentication in auth module
- Created refresh token generation logic and endpoint
- Added validation logic for expired or malformed tokens

---

### 4. How This Improves the Project

Explain the rationale behind the changes. What problem does it solve? What benefit does it bring to the codebase or users?

Example:
Replaces the outdated session-based login with a modern token-based flow. This improves security, enables scalable API authentication, and prepares the system for mobile clients.

---

### 5. Additional Notes

Add any considerations, warnings, blockers, or questions for the reviewer. Mention migrations, major refactors, or known limitations.

Example:
- Requires database migration for `refresh_token` field
- Auth module will need re-testing of login/logout flows
- Does not include role-based permissions yet (to be done in future PR)

---

## Full Template

**Title:**
One-line summary of the change

**Modules Affected:**
- Module 1
- Module 2

**Key Features and Enhancements:**
- Bullet 1
- Bullet 2
- Bullet 3

**How This Improves the Project:**
Short explanation of the benefit and purpose.

**Additional Notes:**
(Optional section for migrations, blockers, or review notes)

---

## Example Pull Request

**Title:**
[auth] Implement secure login with token authentication

**Modules Affected:**
- auth
- whatsapp

**Key Features and Enhancements:**
- Replaced session-based login with JWT authentication
- Added token refresh logic and secure storage
- Created login and token validation unit tests

**How This Improves the Project:**
Introduces scalable and secure authentication, improves API reliability, and lays the foundation for role-based access control.

**Additional Notes:**
Migration script included to update user model.