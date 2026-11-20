# Cloudflare Pages deployment

This repository now includes a Cloudflare Pages Functions adapter. The existing Netlify files and live Netlify site are intentionally retained as a rollback option.

## Cloudflare Pages project

1. In Cloudflare Dashboard, open **Workers & Pages** and create a Pages project from the GitHub repository `beingmdaslam/Aslam-AI-Movie-Dubbing-Studio`.
2. Select the `main` branch.
3. Use build command `npm run build` and build output directory `.`.
4. Deploy the project. The Pages Functions routes are:
   - `/api/status`
   - `/api/create-upload`

## R2 credentials

In the Pages project settings, add these as encrypted environment variables for Production (and Preview only if needed):

- `R2_ACCOUNT_ID`
- `R2_ACCESS_KEY_ID`
- `R2_SECRET_ACCESS_KEY`
- `R2_BUCKET_NAME`
- `R2_ENDPOINT` (optional; if omitted, the endpoint is derived from `R2_ACCOUNT_ID`)

Create an R2 API token with access limited to the one bucket used by this project. Never put R2 secrets in frontend HTML or commit them to Git.

## Verification before switching traffic

After setting the secrets and deploying:

1. Open `https://YOUR-PAGES-DOMAIN/api/status`; confirm JSON reports success.
2. Test `/api/create-upload` with a small video using a same-origin browser request.
3. Confirm the returned presigned URL accepts a PUT and the object appears in the intended R2 bucket.
4. Only after these checks pass should the frontend be switched to the Cloudflare API and the Netlify site be retired.

## Notes

- The current frontend uses the device-local mobile studio and IndexedDB handoff; it does not currently need to upload the selected movie to a server. The new upload endpoint is prepared for the existing R2 upload flow without changing the current UI.
- Cloudflare free-plan quotas and R2 storage/operation limits still apply. This setup does not promise unlimited or zero-cost video storage.
- Netlify configuration and functions are retained unchanged for rollback.
