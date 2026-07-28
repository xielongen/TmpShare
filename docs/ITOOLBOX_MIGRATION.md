# itoolbox consolidation record

TmpShare is the canonical temporary file-transfer project. The former `itoolbox`
repository was a single-purpose Krypton prototype despite its generic name.

## Kept in TmpShare

- The one-argument file-upload command-line workflow, now provided by the same Python
  package as both `tmpshare` and the easier-to-remember alias `ishare`.
- Streaming uploads in 1 MiB chunks instead of reading the whole file into memory.
- An optional bearer token for upload authorization. Tokens come only from environment
  or command-line configuration; there is no built-in credential.
- A five-minute default lifetime for files that have never been downloaded. This closes
  TmpShare's previous unlimited retention path.

## Deliberately not kept

- The Cloudflare KV storage implementation: it duplicated the server, constrained file
  storage, lacked this project's tests and persistent metadata model, and the deployed
  version did not match the repository's latest source.
- The Worker-to-VPS proxy and Node VPS agent: the Worker configuration still described
  KV bindings, its origin URL was a placeholder, and the agent stored metadata only in
  memory. A restart made on-disk files unreachable.
- The hard-coded shared keys and claims of application-level encryption. HTTPS protects
  transport, but neither project encrypts file contents end-to-end.
- Generated JavaScript, dependency directories, and local credential files.

Configuration now consistently uses `TMPSHARE_URL` and `TMPSHARE_UPLOAD_TOKEN`; the old
Krypton command and environment-variable names were removed to avoid retaining a second
product vocabulary.

## Retirement status

The consolidation was completed on 2026-07-29:

- GitHub repository `transcendentaloop/itoolbox` was archived after its committed SHA was
  verified against the remote. Its history remains available for recovery.
- Cloudflare Worker `krypton-transfer-node` was deleted. Analytics showed only its three
  deployment-time calls and three maintenance probes over the preceding 27 days, with no
  user traffic.
- Its dedicated `METADATA` and `DATA` KV namespaces were confirmed empty and deleted.
- The old global npm link was replaced with this package's `tmpshare` and `ishare`
  commands.
