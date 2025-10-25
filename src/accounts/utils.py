# Account utilities for email domain validation


def is_email_domain_allowed(email: str, allowed_domains: list[str]) -> bool:
    """
    Check if email domain is allowed, supporting subdomains.

    Args:
        email: Email address to validate
        allowed_domains: List of allowed domains (e.g., ['uw.edu'])

    Returns:
        True if domain is allowed, False otherwise

    Examples:
        is_email_domain_allowed('user@uw.edu', ['uw.edu']) -> True
        is_email_domain_allowed('user@cs.uw.edu', ['uw.edu']) -> True
        is_email_domain_allowed('user@gmail.com', ['uw.edu']) -> False
    """
    if not email or "@" not in email:
        return False

    # Split email and check for valid format
    parts = email.split("@")
    if len(parts) != 2 or not parts[0] or not parts[1]:
        return False

    domain = parts[1].lower()

    for allowed_domain in allowed_domains:
        allowed_domain = allowed_domain.lower()
        # Check exact match or subdomain
        if domain == allowed_domain or domain.endswith("." + allowed_domain):
            return True

    return False
