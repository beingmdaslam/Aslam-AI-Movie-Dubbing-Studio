import { S3Client, PutObjectCommand } from "@aws-sdk/client-s3";
import { getSignedUrl } from "@aws-sdk/s3-request-presigner";

const json = (data, status = 200) => Response.json(data, {
  status,
  headers: { "Cache-Control": "no-store" }
});

export async function onRequestPost({ request, env }) {
  const origin = request.headers.get("Origin");
  const requestOrigin = new URL(request.url).origin;

  if (origin && origin !== requestOrigin) {
    return json({ error: "Origin not allowed" }, 403);
  }

  let input;
  try {
    input = await request.json();
  } catch {
    return json({ error: "Invalid JSON request." }, 400);
  }

  const { fileName, contentType, fileSize } = input || {};
  const maxBytes = 5 * 1024 * 1024 * 1024;

  if (
    typeof fileName !== "string" ||
    !fileName.trim() ||
    typeof contentType !== "string" ||
    !contentType.startsWith("video/") ||
    !Number.isSafeInteger(fileSize) ||
    fileSize <= 0 ||
    fileSize > maxBytes
  ) {
    return json({ error: "Invalid video details. Maximum size is 5 GB." }, 400);
  }

  const {
    R2_ACCOUNT_ID,
    R2_ACCESS_KEY_ID,
    R2_SECRET_ACCESS_KEY,
    R2_BUCKET_NAME,
    R2_ENDPOINT
  } = env;

  const endpoint = R2_ENDPOINT || (R2_ACCOUNT_ID
    ? `https://${R2_ACCOUNT_ID}.r2.cloudflarestorage.com`
    : "");

  if (!R2_ACCESS_KEY_ID || !R2_SECRET_ACCESS_KEY || !R2_BUCKET_NAME || !endpoint) {
    return json({
      error: "Cloudflare R2 is not configured. Add the required R2 secrets and bucket name."
    }, 503);
  }

  try {
    const client = new S3Client({
      region: "auto",
      endpoint,
      credentials: {
        accessKeyId: R2_ACCESS_KEY_ID,
        secretAccessKey: R2_SECRET_ACCESS_KEY
      }
    });

    const safeName = fileName
      .split(/[\\/]/)
      .pop()
      .replace(/[^a-zA-Z0-9._-]/g, "_")
      .slice(-120) || "video";
    const key = `uploads/${crypto.randomUUID()}-${safeName}`;

    const command = new PutObjectCommand({
      Bucket: R2_BUCKET_NAME,
      Key: key,
      ContentType: contentType
    });

    const uploadUrl = await getSignedUrl(client, command, { expiresIn: 900 });

    return json({
      success: true,
      uploadUrl,
      key,
      expiresIn: 900
    });
  } catch (error) {
    console.error("R2 upload URL error:", error);
    return json({ error: "Could not create upload URL." }, 500);
  }
}
