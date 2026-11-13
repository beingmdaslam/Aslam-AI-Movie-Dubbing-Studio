
import { S3Client, PutObjectCommand } from "@aws-sdk/client-s3";
import { getSignedUrl } from "@aws-sdk/s3-request-presigner";
import { randomUUID } from "node:crypto";

const response = (data, status = 200) =>
  new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json" }
  });

export default async (request) => {
  if (request.method !== "POST") {
    return response({ error: "Method not allowed" }, 405);
  }

  const allowedOrigin = "https://dazzling-sawine-32156a.netlify.app";
  if (request.headers.get("origin") !== allowedOrigin) {
    return response({ error: "Origin not allowed" }, 403);
  }

  try {
    const {
      fileName,
      contentType,
      fileSize
    } = await request.json();

    if (
      typeof fileName !== "string" ||
      !fileName.trim() ||
      typeof contentType !== "string" ||
      !contentType.startsWith("video/") ||
      !Number.isFinite(fileSize) ||
      fileSize <= 0 ||
      fileSize > 5 * 1024 * 1024 * 1024
    ) {
      return response({ error: "Invalid video details. Maximum size is 5 GB." }, 400);
    }

    const {
      R2_ACCOUNT_ID,
      R2_ACCESS_KEY_ID,
      R2_SECRET_ACCESS_KEY,
      R2_BUCKET_NAME,
      R2_ENDPOINT
    } = process.env;

    if (
      !R2_ACCOUNT_ID ||
      !R2_ACCESS_KEY_ID ||
      !R2_SECRET_ACCESS_KEY ||
      !R2_BUCKET_NAME ||
      !R2_ENDPOINT
    ) {
      return response({ error: "R2 environment variables are missing." }, 500);
    }

    const client = new S3Client({
      region: "auto",
      endpoint: R2_ENDPOINT,
      credentials: {
        accessKeyId: R2_ACCESS_KEY_ID,
        secretAccessKey: R2_SECRET_ACCESS_KEY
      }
    });

    const safeName = fileName
      .split(/[\\/]/)
      .pop()
      .replace(/[^a-zA-Z0-9._-]/g, "_")
      .slice(-120);

    const key = `uploads/${randomUUID()}-${safeName}`;

    const command = new PutObjectCommand({
      Bucket: R2_BUCKET_NAME,
      Key: key,
      ContentType: contentType
    });

    const uploadUrl = await getSignedUrl(client, command, {
      expiresIn: 900
    });

    return response({
      success: true,
      uploadUrl,
      key,
      expiresIn: 900
    });

  } catch (error) {
    console.error("R2 upload URL error:", error);
    return response({ error: "Could not create upload URL." }, 500);
  }
};
