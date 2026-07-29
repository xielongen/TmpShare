# ishare Cloudflare deployment

This directory is the production Cloudflare implementation of TmpShare.

## Live deployment

- Worker: `ishare`
- URL: `https://ishare.up2sky.top`
- File binding: KV namespace `ishare-files`
- Metadata binding: D1 database `ishare-metadata` in APAC
- Cleanup trigger: every minute
- Required secret: `UPLOAD_TOKEN`

The upload secret is never committed. The deployed value is stored as a Cloudflare Worker secret, and the matching client value is stored in `~/.config/ishare/config.json` with mode `600`.

## Storage choice

R2 is the preferred object store for larger files, but the account returned Cloudflare API error `10042` because R2 has not been enabled in the dashboard. The reachable VPS was not used because its root disk was 96% full and ports 80/443 were already occupied by proxy services.

The deployed fallback uses Workers KV for file bodies and D1 for authoritative expiry metadata:

- maximum file size: 25 MiB, matching the KV value-size hard limit;
- unclaimed KV values expire after 300 seconds;
- D1 starts a 60-second grace window after the first successful download;
- the scheduled handler deletes expired values and rows;
- a temporary cross-region KV propagation miss returns `503` with `Retry-After: 5` instead of incorrectly deleting metadata.

Once R2 is enabled, replace the `FILES` KV binding with an R2 bucket and restore a larger `MAX_UPLOAD_BYTES`. Do not silently raise the current limit while KV is in use.

## Development and verification

```bash
npm ci
npm run check
npm run deploy:dry
```

`npm run check` regenerates binding/runtime types, runs strict TypeScript checking, and executes the Worker tests inside Cloudflare's `workerd` runtime with isolated local KV and D1 storage.

## Recreating resources

Resource creation changes the Cloudflare account. Run only against the intended account:

```bash
npx wrangler whoami
npx wrangler kv namespace create ishare-files
npx wrangler d1 create ishare-metadata --location apac
```

Put the returned IDs in `wrangler.jsonc`, then apply migrations:

```bash
npx wrangler d1 migrations apply ishare-metadata --remote
```

For the first deployment, create a root-readable temporary JSON or dotenv secrets file outside the repository and deploy it without printing the value:

```bash
npx wrangler deploy --secrets-file /secure/path/ishare-secrets.json
```

For later rotations, use Wrangler's hidden prompt:

```bash
npx wrangler secret put UPLOAD_TOKEN
```

Then update the local client through its hidden prompt:

```bash
ishare setup https://ishare.up2sky.top
```

## Production smoke test

```bash
ishare ./example.txt
curl -L 'https://ishare.up2sky.top/d/<token>' -o downloaded.file
```

Expected controls:

- `GET /` returns `200`;
- unauthenticated `POST /api/upload` returns `401`;
- a valid upload can be downloaded byte-for-byte;
- an expired link returns `302` to `/`;
- `GET /__scheduled` returns `404` and cannot trigger cleanup from the public internet.

## Rollback and removal

Inspect deployments before changing traffic:

```bash
npx wrangler deployments list
npx wrangler rollback
```

Deleting the Worker, KV namespace, or D1 database is destructive and is not part of a normal rollback. Verify the exact resource names and preserve any needed data before using the corresponding Wrangler delete commands.
