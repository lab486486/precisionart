import { handleCallback } from "../_github-oauth.js";

export async function onRequest({ env, request }) {
  return handleCallback(request, env, "/api/oauth/callback");
}
