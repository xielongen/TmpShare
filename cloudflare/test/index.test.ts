import { env } from "cloudflare:workers";
import {
  createExecutionContext,
  createScheduledController,
  waitOnExecutionContext,
} from "cloudflare:test";
import { describe, expect, it } from "vitest";

import worker from "../src/index";

async function dispatch(request: Request): Promise<Response> {
  const context = createExecutionContext();
  const response = await worker.fetch(request, env, context);
  await waitOnExecutionContext(context);
  return response;
}

async function upload(body = "hello from worker"): Promise<{ response: Response; token: string }> {
  const response = await dispatch(
    new Request("https://ishare.example/api/upload", {
      method: "POST",
      headers: {
        Authorization: "Bearer test-upload-token",
        "Content-Type": "application/octet-stream",
        "Content-Length": String(body.length),
        "X-File-Name": "example.txt",
      },
      body,
    }),
  );
  const payload = await response.clone().json<{ download_url: string }>();
  return { response, token: payload.download_url.split("/").at(-1) ?? "" };
}

describe("ishare worker", () => {
  it("serves the camouflage home page", async () => {
    const response = await dispatch(new Request("https://ishare.example/"));
    expect(response.status).toBe(200);
    expect(await response.text()).toContain("ClickHouse 数据库简介");
  });

  it("rejects uploads without the configured secret", async () => {
    const response = await dispatch(
      new Request("https://ishare.example/api/upload", {
        method: "POST",
        headers: {
          "Content-Type": "application/octet-stream",
          "Content-Length": "5",
          "X-File-Name": "a.txt",
        },
        body: "hello",
      }),
    );
    expect(response.status).toBe(401);
  });

  it("streams an authenticated upload through a temporary download link", async () => {
    const { response, token } = await upload();
    expect(response.status).toBe(200);
    expect(token).toMatch(/^[a-f0-9]{48}$/);

    const download = await dispatch(new Request(`https://ishare.example/d/${token}`));
    expect(download.status).toBe(200);
    expect(new TextDecoder().decode(await download.arrayBuffer())).toBe("hello from worker");
    expect(download.headers.get("Content-Disposition")).toMatch(/attachment; filename="[a-f0-9]{16}\.txt"/);

    const row = await env.DB.prepare("SELECT first_download_at, expire_at FROM files WHERE token = ?")
      .bind(token)
      .first<{ first_download_at: number; expire_at: number }>();
    expect(row).not.toBeNull();
    expect((row?.expire_at ?? 0) - (row?.first_download_at ?? 0)).toBe(60);
  });

  it("removes an expired file and redirects to the home page", async () => {
    const { token } = await upload("expired");
    await env.DB.prepare("UPDATE files SET created_at = 0 WHERE token = ?").bind(token).run();

    const response = await dispatch(new Request(`https://ishare.example/d/${token}`));
    expect(response.status).toBe(302);
    expect(await env.DB.prepare("SELECT token FROM files WHERE token = ?").bind(token).first()).toBeNull();
    expect(await env.FILES.get(`files/${token}`)).toBeNull();
  });

  it("cleans expired files from D1 and R2 on schedule", async () => {
    const { token } = await upload("scheduled cleanup");
    await env.DB.prepare("UPDATE files SET created_at = 0 WHERE token = ?").bind(token).run();
    const context = createExecutionContext();
    await worker.scheduled(createScheduledController(), env, context);
    await waitOnExecutionContext(context);

    expect(await env.DB.prepare("SELECT token FROM files WHERE token = ?").bind(token).first()).toBeNull();
    expect(await env.FILES.get(`files/${token}`)).toBeNull();
  });

  it("does not expose the local scheduled-test endpoint", async () => {
    const response = await dispatch(new Request("https://ishare.example/__scheduled"));
    expect(response.status).toBe(404);
  });
});
