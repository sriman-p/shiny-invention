# URL Shortener Requirements

## REQ-001: Shorten URL
The service must accept a long URL and return a shortened version.
- Priority: High
- Type: Functional
- Acceptance Criteria:
  - Returns a short URL with 6-character code
  - Same URL always generates the same short code

## REQ-002: Redirect
Accessing a short URL must redirect to the original URL.
- Priority: High
- Type: Functional
- Acceptance Criteria:
  - Valid short code redirects to original URL
  - Invalid short code returns 404

## REQ-003: URL Validation
Only valid URLs should be accepted.
- Priority: Medium
- Type: Non-functional
- Acceptance Criteria:
  - Invalid URLs are rejected with an error message
  - URLs must start with http:// or https://
