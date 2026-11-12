
export default async (request) => {
  return new Response(
    JSON.stringify({
      success: true,
      project: "Aslam AI Movie Dubbing Studio",
      backend: "Online",
      version: "1.0.0",
      services: {
        videoUpload: "Pending",
        voiceExtraction: "Pending",
        translation: "Pending",
        voiceCloning: "Pending",
        lipSync: "Pending",
        videoExport: "Pending"
      },
      message: "Backend API is responding. AI processing services are not connected yet."
    }),
    {
      status: 200,
      headers: {
        "Content-Type": "application/json"
      }
    }
  );
};
