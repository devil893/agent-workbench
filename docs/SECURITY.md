# Security and evaluation boundaries

- Identity comes from a configured bearer token or an allowlisted, signature-verified Twilio sender. HTTP bodies do not select the tenant.
- Every application data query is tenant-scoped. Model-authored SQL operates on a separate tenant snapshot.
- Approvals bind to stored arguments, tenant, tool, and expiry. They are one-shot; the model has no approval capability.
- External services are simulated. Simulation creates local records, not external effects.
- No shell, arbitrary filesystem, secret-read, or repository-management tool exists.
- Research and browser tools accept named fixtures only. They do not resolve DNS or follow URLs.
- JSON schemas reject unexpected arguments. Chart text is escaped; chart values are bounded and finite.
- Twilio's exact configured webhook URL is used for signature checks rather than attacker-controlled forwarding headers.
- Audit traces are tenant-scoped and include explicit no-tool-call run summaries.

Do not interpret passing unit tests or a clean evaluation score as a security certification. In particular, the refusal wording in a model answer is not evidence that a tool action was blocked. Review the corresponding tool outcome.

Application tokens and the SQLite database are sensitive. Keep them out of Git. Prompt and tool content can appear in stored history and traces. Use synthetic inputs for public demonstrations. No client data, production tokens, or previous repository history belongs in this source tree.
