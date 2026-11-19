const json = (data, status = 200) =>
  new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json" }
  });

export default async (request) => {
  if (request.method !== "GET") {
    return json({ error: "Method not allowed" }, 405);
  }

  const allowedOrigin = "https://dazzling-sawine-32156a.netlify.app";
  if (request.headers.get("origin") !== allowedOrigin) {
    return json({ error: "Origin not allowed" }, 403);
  }

  try {
    const apiKey = process.env.ELEVENLABS_API_KEY;
    if (!apiKey) {
      return json({ error: "Dubbing service is not configured yet." }, 503);
    }

    const url = new URL(request.url);
    const projectId = url.searchParams.get("projectId");
    const languageId = url.searchParams.get("languageId");

    if (
      !projectId ||
      !/^proj_[a-zA-Z0-9]+$/.test(projectId) ||
      !languageId ||
      !/^[a-zA-Z0-9_-]+$/.test(languageId)
    ) {
      return json({ error: "Valid projectId and languageId are required." }, 400);
    }

    const headers = { "xi-api-key": apiKey };
    const base = "https://api.elevenlabs.io/v1/dubbing/project";

    const [projectResponse, languageResponse] = await Promise.all([
      fetch(`${base}/${encodeURIComponent(projectId)}`, { headers }),
      fetch(
        `${base}/${encodeURIComponent(projectId)}/language/${encodeURIComponent(languageId)}`,
        { headers }
      )
    ]);

    const project = await projectResponse.json().catch(() => ({}));
    const language = await languageResponse.json().catch(() => ({}));

    if (!projectResponse.ok || !languageResponse.ok) {
      const status = !projectResponse.ok ? projectResponse.status : languageResponse.status;
      console.error("Dubbing status lookup failed:", status);
      return json({ error: "Could not retrieve dubbing status." }, 502);
    }

    return json({
      success: true,
      projectStatus: project.status,
      languageStatus: language.status,
      targetLanguage: language.target_language,
      outputAudioUrl: language.outputs?.lossless_audio || null,
      error: language.error || project.error || null
    });
  } catch (error) {
    console.error("Dubbing status error:", error);
    return json({ error: "Could not check dubbing status." }, 500);
  }
};
