# Public calculator boundary

This repository is the public calculation boundary for AYKALEN. It deliberately excludes reporting, prompts, client data, AI calls, publication and PDF rendering.

The current distribution is a Python library and a JSON CLI. A future HTTP wrapper must preserve the same request/response contract and identify the exact source revision offered to users of the network service.

The private reporting system must consume the calculator through this documented JSON boundary rather than bundling calculator source into a separate closed distribution.
