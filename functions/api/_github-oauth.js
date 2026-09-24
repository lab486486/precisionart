const GITHUB_AUTHORIZE = "https://github.com/login/oauth/authorize";
const GITHUB_TOKEN = "https://github.com/login/oauth/access_token";
const REPO = "lab486486/precisionart";

export function oauthCreds(env) {
  return {
    clientId: env.GITHUB_CLIENT_ID || env.GITHUB_OAUTH_CLIENT_ID || "",
    clientSecret: env.GITHUB_CLIENT_SECRET || env.GITHUB_OAUTH_CLIENT_SECRET || "",
  };
}

export async function handleAuth(request, env, callbackPath) {
  const { clientId, clientSecret } = oauthCreds(env);
  if (!clientId || !clientSecret) {
    return new Response("GITHUB_CLIENT_ID / GITHUB_CLIENT_SECRET not set in Pages env", {
      status: 500,
      headers: { "content-type": "text/plain; charset=utf-8" },
    });
  }

  const params = new URL(request.url).searchParams;
  const provider = params.get("provider");
  if (provider && provider !== "github") {
    return new Response("Unsupported provider", { status: 400 });
  }

  const origin = new URL(request.url).origin;
  const redirectUri = `${origin}${callbackPath}`;
  const state = await createSignedState(clientSecret);
  const authorize = new URL(GITHUB_AUTHORIZE);
  authorize.searchParams.set("client_id", clientId);
  authorize.searchParams.set("redirect_uri", redirectUri);
  authorize.searchParams.set("scope", params.get("scope") || "repo,user");
  authorize.searchParams.set("state", state);
  return Response.redirect(authorize.toString(), 302);
}

export async function handleCallback(request, env, callbackPath) {
  const { clientId, clientSecret } = oauthCreds(env);
  const url = new URL(request.url);
  const code = url.searchParams.get("code");
  const state = url.searchParams.get("state");
  const error = url.searchParams.get("error");

  if (error) {
    return htmlResponse(errorPage(`GitHub OAuth 거부: ${error}`), 400);
  }
  if (!clientId || !clientSecret || !code || !state) {
    return new Response("GitHub 로그인 정보가 없습니다.", {
      status: 400,
      headers: { "content-type": "text/plain; charset=utf-8" },
    });
  }
  if (!(await verifySignedState(state, clientSecret))) {
    return htmlResponse(errorPage("OAuth state 검증 실패. CMS에서 다시 Login with GitHub를 눌러주세요."), 400);
  }

  const tokenRes = await fetch(GITHUB_TOKEN, {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify({
      client_id: clientId,
      client_secret: clientSecret,
      code,
      redirect_uri: `${url.origin}${callbackPath}`,
    }),
  });
  const tokenData = await tokenRes.json();
  const token = tokenData.access_token;
  if (!token) {
    return htmlResponse(
      errorPage(`토큰 발급 실패: ${tokenData.error_description || tokenData.error || "unknown"}`),
      400,
    );
  }

  const userRes = await fetch("https://api.github.com/user", {
    headers: {
      Accept: "application/vnd.github+json",
      Authorization: `Bearer ${token}`,
      "User-Agent": "precisionart-decap",
    },
  });
  const user = await userRes.json();
  if (!(await canWrite(token, user.login || ""))) {
    return htmlResponse(errorPage("이 저장소에 글을 넣을 권한이 없습니다."), 403);
  }

  return htmlResponse(successPage({ token, provider: "github" }));
}

async function canWrite(token, login) {
  const res = await fetch(
    `https://api.github.com/repos/${REPO}/collaborators/${encodeURIComponent(login)}/permission`,
    {
      headers: {
        Accept: "application/vnd.github+json",
        Authorization: `Bearer ${token}`,
        "User-Agent": "precisionart-decap",
      },
    },
  );
  if (!res.ok) return false;
  const data = await res.json();
  return ["admin", "maintain", "write"].includes(String(data.permission || ""));
}

function successPage(content) {
  const contentJson = JSON.stringify(content);
  return `<!DOCTYPE html>
<html lang="ko">
<head><meta charset="utf-8"><title>Authorizing...</title></head>
<body>
<p>로그인 완료. 잠시만 기다려주세요...</p>
<script>
(function () {
  var content = ${contentJson};
  var sent = false;

  function sendToken(targetOrigin) {
    if (sent || !window.opener) return;
    sent = true;
    window.opener.postMessage(
      "authorization:github:success:" + JSON.stringify(content),
      targetOrigin
    );
    window.close();
  }

  function receiveMessage(e) {
    if (sent) return;
    if (e.data !== "authorizing:github") return;
    sendToken(e.origin);
  }

  window.addEventListener("message", receiveMessage, false);

  function ping() {
    if (sent || !window.opener) return;
    window.opener.postMessage("authorizing:github", "*");
  }

  if (window.opener) {
    ping();
    setTimeout(ping, 300);
    setTimeout(ping, 1000);
    setTimeout(function () {
      if (!sent) {
        document.body.innerHTML =
          "<h1>CMS 연결 대기 중...</h1><p>팝업을 닫지 말고 잠시만 기다려주세요.</p>";
      }
    }, 2000);
  } else {
    document.body.innerHTML =
      "<h1>팝업 연결 실패</h1><p>브라우저가 팝업 연결을 차단했습니다.</p>" +
      "<p>팝업 차단을 해제하고 CMS에서 다시 Login with GitHub를 눌러주세요.</p>";
  }
})();
</script>
</body></html>`;
}

function errorPage(message) {
  return `<!DOCTYPE html>
<html lang="ko">
<head><meta charset="utf-8"><title>OAuth Error</title></head>
<body style="font-family:sans-serif;padding:2rem;max-width:480px">
  <h1>로그인 실패</h1>
  <p>${escapeHtml(message)}</p>
  <p>이 창을 닫고 CMS에서 다시 시도해주세요.</p>
</body></html>`;
}

function htmlResponse(body, status = 200) {
  return new Response(body, {
    status,
    headers: { "Content-Type": "text/html; charset=utf-8" },
  });
}

async function createSignedState(secret) {
  const nonce = crypto.randomUUID();
  const issuedAt = Date.now();
  const payload = `${nonce}:${issuedAt}`;
  const signature = await hmacSha256Hex(secret, payload);
  return `${payload}:${signature}`;
}

async function verifySignedState(state, secret) {
  const parts = state.split(":");
  if (parts.length !== 3) return false;
  const [nonce, issuedAt, signature] = parts;
  if (!nonce || !issuedAt || !signature) return false;
  const age = Date.now() - Number(issuedAt);
  if (Number.isNaN(age) || age < 0 || age > 10 * 60 * 1000) return false;
  const expected = await hmacSha256Hex(secret, `${nonce}:${issuedAt}`);
  return timingSafeEqual(signature, expected);
}

async function hmacSha256Hex(secret, message) {
  const encoder = new TextEncoder();
  const key = await crypto.subtle.importKey(
    "raw",
    encoder.encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const sig = await crypto.subtle.sign("HMAC", key, encoder.encode(message));
  return [...new Uint8Array(sig)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

function timingSafeEqual(a, b) {
  if (a.length !== b.length) return false;
  let result = 0;
  for (let i = 0; i < a.length; i++) result |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return result === 0;
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
