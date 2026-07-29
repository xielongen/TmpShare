import homePage from "./home";

type FileRow = {
  token: string;
  object_key: string;
  download_name: string;
  size_bytes: number;
  created_at: number;
  first_download_at: number | null;
  expire_at: number | null;
};

type ExpiredRow = Pick<FileRow, "token" | "object_key">;

const JSON_HEADERS = {
  "Content-Type": "application/json; charset=utf-8",
  "Cache-Control": "no-store",
  "X-Content-Type-Options": "nosniff",
};

function json(payload: object, status = 200): Response {
  return new Response(JSON.stringify(payload), { status, headers: JSON_HEADERS });
}

function home(): Response {
  return new Response(homePage, {
    headers: {
      "Content-Type": "text/html; charset=utf-8",
      "Cache-Control": "public, max-age=300",
      "X-Content-Type-Options": "nosniff",
      "Referrer-Policy": "no-referrer",
    },
  });
}

function redirectHome(): Response {
  return new Response(null, {
    status: 302,
    headers: {
      Location: "/",
      "Cache-Control": "no-store",
    },
  });
}

function randomToken(byteLength: number): string {
  const bytes = new Uint8Array(byteLength);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (value) => value.toString(16).padStart(2, "0")).join("");
}

function safeExtension(fileName: string): string {
  const match = fileName.match(/(\.[A-Za-z0-9]{1,15})$/);
  return match?.[1] ?? "";
}

function parsePositiveInteger(value: string, name: string): number {
  const parsed = Number(value);
  if (!Number.isSafeInteger(parsed) || parsed <= 0) {
    throw new Error(`Invalid ${name} configuration`);
  }
  return parsed;
}

async function secretMatches(provided: string, expected: string): Promise<boolean> {
  const encoder = new TextEncoder();
  const [providedHash, expectedHash] = await Promise.all([
    crypto.subtle.digest("SHA-256", encoder.encode(provided)),
    crypto.subtle.digest("SHA-256", encoder.encode(expected)),
  ]);
  const providedBytes = new Uint8Array(providedHash);
  const expectedBytes = new Uint8Array(expectedHash);
  let difference = 0;
  for (let index = 0; index < providedBytes.length; index += 1) {
    difference |= providedBytes[index]! ^ expectedBytes[index]!;
  }
  return difference === 0;
}

async function upload(request: Request, env: Env): Promise<Response> {
  const authorization = request.headers.get("Authorization") ?? "";
  const providedToken = authorization.startsWith("Bearer ")
    ? authorization.slice("Bearer ".length)
    : "";
  if (!(await secretMatches(providedToken, env.UPLOAD_TOKEN))) {
    return json({ error: "unauthorized" }, 401);
  }

  if (request.headers.get("Content-Type")?.split(";", 1)[0] !== "application/octet-stream") {
    return json({ error: "Content-Type must be application/octet-stream" }, 415);
  }
  const encodedName = request.headers.get("X-File-Name") ?? "";
  if (!encodedName || encodedName.length > 1024) {
    return json({ error: "X-File-Name is required" }, 400);
  }
  if (request.body === null) {
    return json({ error: "empty file" }, 400);
  }

  const contentLength = Number(request.headers.get("Content-Length"));
  const maxUploadBytes = parsePositiveInteger(env.MAX_UPLOAD_BYTES, "MAX_UPLOAD_BYTES");
  if (!Number.isSafeInteger(contentLength) || contentLength <= 0) {
    return json({ error: "a positive Content-Length is required" }, 411);
  }
  if (contentLength > maxUploadBytes) {
    return json({ error: "upload exceeds configured size limit" }, 413);
  }

  let originalName: string;
  try {
    originalName = decodeURIComponent(encodedName);
  } catch {
    return json({ error: "X-File-Name is not valid URL encoding" }, 400);
  }

  const token = randomToken(24);
  const objectKey = `files/${token}`;
  const downloadName = `${randomToken(8)}${safeExtension(originalName)}`;
  const now = Math.floor(Date.now() / 1000);

  await env.FILES.put(objectKey, request.body, {
    expirationTtl: parsePositiveInteger(
      env.UNCLAIMED_EXPIRE_SECONDS,
      "UNCLAIMED_EXPIRE_SECONDS",
    ),
    metadata: { downloadName },
  });

  try {
    await env.DB.prepare(
      `INSERT INTO files (
        token, object_key, download_name, size_bytes, created_at,
        first_download_at, expire_at
      ) VALUES (?, ?, ?, ?, ?, NULL, NULL)`,
    )
      .bind(token, objectKey, downloadName, contentLength, now)
      .run();
  } catch (error) {
    await env.FILES.delete(objectKey);
    throw error;
  }

  const origin = new URL(request.url).origin;
  const downloadUrl = `${origin}/d/${token}`;
  return json({
    message: "upload ok",
    uploaded_at: new Date().toISOString(),
    download_url: downloadUrl,
    download_filename: downloadName,
    expires_rule: (
      `The link expires after ${env.UNCLAIMED_EXPIRE_SECONDS} seconds if unused; ` +
      `the first successful download starts a ${env.DOWNLOAD_GRACE_SECONDS}-second grace period.`
    ),
    curl_download: `curl -L '${downloadUrl}' -o '${downloadName}'`,
  });
}

async function removeFile(env: Env, row: ExpiredRow): Promise<void> {
  await env.FILES.delete(row.object_key);
  await env.DB.prepare("DELETE FROM files WHERE token = ?").bind(row.token).run();
}

async function download(token: string, env: Env): Promise<Response> {
  if (!/^[a-f0-9]{48}$/.test(token)) {
    return redirectHome();
  }

  const row = await env.DB.prepare("SELECT * FROM files WHERE token = ?")
    .bind(token)
    .first<FileRow>();
  if (row === null) {
    return redirectHome();
  }

  const now = Math.floor(Date.now() / 1000);
  const unclaimedSeconds = parsePositiveInteger(
    env.UNCLAIMED_EXPIRE_SECONDS,
    "UNCLAIMED_EXPIRE_SECONDS",
  );
  const expired =
    (row.expire_at !== null && row.expire_at <= now) ||
    (row.first_download_at === null && row.created_at + unclaimedSeconds <= now);
  if (expired) {
    await removeFile(env, row);
    return redirectHome();
  }

  const object = await env.FILES.get(row.object_key, { type: "stream" });
  if (object === null) {
    return new Response(JSON.stringify({ error: "file is propagating; retry shortly" }), {
      status: 503,
      headers: { ...JSON_HEADERS, "Retry-After": "5" },
    });
  }

  if (row.first_download_at === null) {
    const graceSeconds = parsePositiveInteger(
      env.DOWNLOAD_GRACE_SECONDS,
      "DOWNLOAD_GRACE_SECONDS",
    );
    await env.DB.prepare(
      `UPDATE files
       SET first_download_at = ?, expire_at = ?
       WHERE token = ? AND first_download_at IS NULL`,
    )
      .bind(now, now + graceSeconds, token)
      .run();
  }

  return new Response(object, {
    headers: {
      "Content-Type": "application/octet-stream",
      "Content-Disposition": `attachment; filename="${row.download_name}"`,
      "Content-Length": String(row.size_bytes),
      "Cache-Control": "no-store, max-age=0",
      "X-Content-Type-Options": "nosniff",
      "Referrer-Policy": "no-referrer",
    },
  });
}

async function cleanupExpired(env: Env): Promise<number> {
  const now = Math.floor(Date.now() / 1000);
  const unclaimedBefore =
    now - parsePositiveInteger(env.UNCLAIMED_EXPIRE_SECONDS, "UNCLAIMED_EXPIRE_SECONDS");
  const result = await env.DB.prepare(
    `SELECT token, object_key FROM files
     WHERE (expire_at IS NOT NULL AND expire_at <= ?)
        OR (first_download_at IS NULL AND created_at <= ?)
     LIMIT 100`,
  )
    .bind(now, unclaimedBefore)
    .all<ExpiredRow>();

  if (result.results.length === 0) {
    return 0;
  }
  await Promise.all(result.results.map((row) => env.FILES.delete(row.object_key)));
  await env.DB.batch(
    result.results.map((row) =>
      env.DB.prepare("DELETE FROM files WHERE token = ?").bind(row.token),
    ),
  );
  return result.results.length;
}

async function handleRequest(request: Request, env: Env): Promise<Response> {
  const url = new URL(request.url);
  if (url.pathname === "/__scheduled") {
    return new Response("Not Found", { status: 404 });
  }
  if (request.method === "POST" && url.pathname === "/api/upload") {
    return upload(request, env);
  }
  if (request.method === "GET" && url.pathname.startsWith("/d/")) {
    return download(url.pathname.slice(3), env);
  }
  if (request.method === "GET") {
    return home();
  }
  return json({ error: "method not allowed" }, 405);
}

export default {
  async fetch(request: Request, env: Env, _ctx: ExecutionContext): Promise<Response> {
    try {
      return await handleRequest(request, env);
    } catch (error) {
      console.error(
        JSON.stringify({
          message: "request failed",
          path: new URL(request.url).pathname,
          error: error instanceof Error ? error.message : "unknown error",
        }),
      );
      return json({ error: "internal server error" }, 500);
    }
  },

  async scheduled(
    controller: ScheduledController,
    env: Env,
    _ctx: ExecutionContext,
  ): Promise<void> {
    const removed = await cleanupExpired(env);
    console.log(
      JSON.stringify({
        message: "expired file cleanup complete",
        scheduledTime: controller.scheduledTime,
        removed,
      }),
    );
  },
} satisfies ExportedHandler<Env>;
