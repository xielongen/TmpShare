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
- A Cloudflare-native public deployment path. It was reimplemented as a tested Worker
  with a dedicated KV namespace for short-lived file bodies and D1 for durable expiry
  metadata; it does not reuse the old Worker's source or credentials.

## Deliberately not kept

- The old Cloudflare KV implementation: it duplicated the server, lacked tests and
  persistent metadata, and its deployed version did not match the repository's source.
  The new Worker has explicit 25 MiB validation, D1 metadata, runtime tests, scheduled
  cleanup, and a documented R2 upgrade path. Only the useful deployment capability was
  retained; the old implementation itself was not copied.
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

## Current production deployment

On 2026-07-29, `ishare` was deployed at
`https://ishare.up2sky.top`. New dedicated resources are named
`ishare-files` and `ishare-metadata`; they do not reuse or recover any deleted Krypton
data. Cloudflare R2 was preferred but could not be provisioned because it is not enabled
for the account, so the deployed KV fallback intentionally limits files to 25 MiB.
