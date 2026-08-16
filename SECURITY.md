# Security policy

Do not open a public issue containing credentials, private media, identifiable-person records, reviewer payloads, or publication tokens.

Use **Security > Report a vulnerability** on GitHub when that option is available. If it is unavailable, contact the repository owner through the private contact method listed on their GitHub profile. Do not include live secrets in the first message.

Supported security fixes target the latest release. Never commit `.env` files, account registries, campaign folders, archives, or local toolchain configuration.

Repository CI combines project-specific public-safety rules with Gitleaks. Contributors must still inspect staged files because automated scanning cannot prove that media, identities, or business context are safe to publish.