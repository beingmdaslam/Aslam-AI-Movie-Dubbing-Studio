import {
  S3Client,
  HeadObjectCommand,
  GetObjectCommand
} from "@aws-sdk/client-s3";
import { getSignedUrl } from "@aws-sdk/s3-request-presigner";

const json = (data, status = 200) =>
  new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json" }
  });

export default async (request) => {
  if (request.method !== "POST") {
    return json({ error: "Method not allowed" }, 405);
  }

  const allowedOrigin = "https://dazzling-sawine-32156a.netlify.app";
  if (request.headers.get("origin") !== allowedOrigin) {
    return json({ error: "Origin not allowed" }, 403);
  }

  try {
    const { key, sourceLanguage = "auto", targetLanguage } = await request.json();

    if (
      typeof key !== "string" ||
      !key.startsWith("uploads/") ||
      key.includes("..") ||
      typeof targetLanguage !== "string" ||
      !/^[a-z]{2,3}(-[A-Z]{2})?$/.test(targetLanguage)
    ) {
      return json({ error: "Invalid video key or language selection." }, 400);
    }

    const {
      R2_ACCESS_KEY_ID,
      R2_SECRET_ACCESS_KEY,
      R2_BUCKET_NAME,
      R2_ENDPOINT,
      ELEVENLABS_API_KEY
    } = process.env;

    if (!R2_ACCESS_KEY_ID || !R2_SECRET_ACCESS_KEY || !R2_BUCKET_NAME || !R2_ENDPOINT) {
      return json({ error: "R2 environment variables are missing." }, 500);
    }
    if (!ELEVENLABS_API_KEY) {
      return json({ error: "Dubbing service is not configured yet." }, 503);
    }

    const storage = new S3Client({
      region: "auto",
      endpoint: R2_ENDPOINT,
      credentials: {
        accessKeyId: R2_ACCESS_KEY_ID,
        secretAccessKey: R2_SECRET_ACCESS_KEY
      }
    });

    const head = await storage.send(new HeadObjectCommand({
      Bucket: R2_BUCKET_NAME,
      Key: key
    }));

    const maxBytes = 3 * 1024 * 1024 * 1024;
    if (!head.ContentLength || head.ContentLength > maxBytes) {
      return json({ error: "This dubbing provider accepts source files up to 3 GB." }, 413);
    }

    const sourceUrl = await getSignedUrl(
      storage,
      new GetObjectCommand({ Bucket: R2_BUCKET_NAME, Key: key }),
      { expiresIn: 3600 }
    );

    const form = new FormData();
    form.append("source_url", sourceUrl);
    form.append("model_id", "dubbing_v2");
    form.append("reference", key.split("/").pop().slice(0, 500));
    if (sourceLanguage !== "auto") form.append("source_language", sourceLanguage);
    form.append("target_language", targetLanguage);

    const upstream = await fetch("https://api.elevenlabs.io/v1/dubbing/project", {
      method: "POST",
      headers: { "xi-api-key": ELEVENLABS_API_KEY },
      body: form
    });

    const result = await upstream.json().catch(() => ({}));
    if (!upstream.ok) {
      console.error("Dubbing project creation failed:", upstream.status, result);
      return json({
        error: "The dubbing provider could not start this job.",
        providerStatus: upstream.status
      }, upstream.status === 429 ? 429 : 502);
    }

    return json({
      success: true,
      projectId: result.project_id,
      status: result.status,
      languageIds: result.language_ids || [],
      targetLanguage
    }, 202);
  } catch (error) {
    console.error("Create dubbing job error:", error);
    return json({ error: "Could not start the dubbing job." }, 500);
  }
};
