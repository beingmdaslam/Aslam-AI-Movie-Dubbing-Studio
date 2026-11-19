import { S3Client, PutObjectCommand, DeleteObjectCommand } from "@aws-sdk/client-s3";
import { randomUUID } from "node:crypto";

const reply = (data, status = 200) =>
  new Response(JSON.stringify(data), {
    status,
    headers: {
      "Content-Type": "application/json",
      "Cache-Control": "no-store"
    }
  });

export default async (request) => {
  if (request.method !== "GET") {
    return reply({ success: false, error: "Method not allowed. Open this diagnostic URL with GET." }, 405);
  }

  const {
    R2_ACCOUNT_ID,
    R2_ACCESS_KEY_ID,
    R2_SECRET_ACCESS_KEY,
    R2_BUCKET_NAME,
    R2_ENDPOINT
  } = process.env;

  const missing = [
    ["R2_ACCOUNT_ID", R2_ACCOUNT_ID],
    ["R2_ACCESS_KEY_ID", R2_ACCESS_KEY_ID],
    ["R2_SECRET_ACCESS_KEY", R2_SECRET_ACCESS_KEY],
    ["R2_BUCKET_NAME", R2_BUCKET_NAME],
    ["R2_ENDPOINT", R2_ENDPOINT]
  ].filter(([, value]) => !value).map(([name]) => name);

  if (missing.length) {
    return reply({
      success: false,
      stage: "configuration",
      error: "Missing Netlify environment variables.",
      missing
    }, 500);
  }

  const client = new S3Client({
    region: "auto",
    endpoint: R2_ENDPOINT,
    credentials: {
      accessKeyId: R2_ACCESS_KEY_ID,
      secretAccessKey: R2_SECRET_ACCESS_KEY
    }
  });

  const key = `diagnostics/connection-test-${randomUUID()}.txt`;

  try {
    await client.send(new PutObjectCommand({
      Bucket: R2_BUCKET_NAME,
      Key: key,
      Body: "ASLAM AI R2 connection test",
      ContentType: "text/plain"
    }));
  } catch (error) {
    console.error("R2 diagnostic write failed:", error);
    return reply({
      success: false,
      stage: "r2_write",
      error: "Netlify could not write a small test object to the configured R2 bucket.",
      r2Error: error.name || "UnknownError",
      message: String(error.message || "No error message").slice(0, 300),
      httpStatus: error.$metadata?.httpStatusCode || null
    }, 502);
  }

  let cleanedUp = false;
  try {
    await client.send(new DeleteObjectCommand({
      Bucket: R2_BUCKET_NAME,
      Key: key
    }));
    cleanedUp = true;
  } catch (error) {
    console.warn("R2 diagnostic cleanup failed:", error);
  }

  return reply({
    success: true,
    stage: "r2_write",
    message: "Netlify successfully wrote a test object to the configured R2 bucket.",
    bucket: R2_BUCKET_NAME,
    testObjectDeleted: cleanedUp,
    note: cleanedUp ? "The temporary test object was deleted." : "The temporary test object may remain under diagnostics/ in the R2 bucket."
  });
};
