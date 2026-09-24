import { handleAuth } from "../_github-oauth.js";

export async function onRequest({ env, request }) {
  return handleAuth(request, env, "/api/oauth/callback");
}
