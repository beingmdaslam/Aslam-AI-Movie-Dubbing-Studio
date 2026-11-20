export async function onRequestGet() {
  return Response.json({
    success: true,
    project: "Aslam AI Movie Dubbing Studio",
    backend: "Cloudflare Pages Functions",
    version: "1.0.0",
    services: {
      videoUpload: "Ready when R2 credentials are configured",
      voiceExtraction: "Pending",
      translation: "Browser-based where supported",
      voiceCloning: "Not available",
      lipSync: "Not available",
      videoExport: "Browser-based"
    },
    message: "Cloudflare API is responding. AI processing remains local to the user's device."
  }, {
    headers: { "Cache-Control": "no-store" }
  });
}
