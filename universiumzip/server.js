import { createServer } from "node:http";
import { request as httpsRequest } from "node:https";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { readFile } from "node:fs/promises";
import express from "express";
import { uvPath } from "@titaniumnetwork-dev/ultraviolet";
import { epoxyPath } from "@mercuryworkshop/epoxy-transport";
import { baremuxPath } from "@mercuryworkshop/bare-mux/node";
import wisp from "wisp-server-node";
import barePkg from "@tomphttp/bare-server-node";
const { createBareServer } = barePkg;

const __dirname = dirname(fileURLToPath(import.meta.url));
const bare = createBareServer("/bare/");
const app = express();

// ── SW suppressor ─────────────────────────────────────────────────────────────
const SW_SUPPRESSOR = `<script>(function(){try{
var noop=function(){return Promise.resolve({scope:'/'})};
var fake={register:noop,getRegistration:function(){return Promise.resolve(undefined)},getRegistrations:function(){return Promise.resolve([])},ready:Promise.resolve({scope:'/'}),addEventListener:function(){},removeEventListener:function(){}};
Object.defineProperty(navigator,'serviceWorker',{get:function(){return fake},configurable:false});
}catch(e){}})();</script>`;

// ── CDN proxy helpers ─────────────────────────────────────────────────────────
// jsdelivr has a 50 MB per-file limit. Game repos store large files split as
// filename.ext.part1, filename.ext.part2, … which jsDelivr auto-assembled.
// We replicate that: fetch directly from GitHub raw, and if we get a 404
// automatically fetch and stream the parts concatenated.

// Convert cdn.jsdelivr.net/gh/USER/REPO@BRANCH/PATH → raw.githubusercontent.com/USER/REPO/BRANCH/PATH
function jsdToRaw(hostAndPath) {
  const m = hostAndPath.match(/^cdn\.jsdelivr\.net\/gh\/([^/@]+)\/([^@]+)@([^/]+)\/?(.*)$/);
  if (m) {
    const [, user, repo, branch, rest] = m;
    // web-dashers publishes its live site on jsDelivr's @latest alias, but
    // GitHub's raw host only exposes the main branch. Keep the proxy's
    // same-origin behavior while resolving that alias correctly.
    const rawBranch =
      user === "web-dashers" && repo === "web-dashers.github.io" && branch === "latest"
        ? "main"
        : branch;
    return { hostname: "raw.githubusercontent.com", path: `/${user}/${repo}/${rawBranch}/${rest}` };
  }
  try {
    const u = new URL("https://" + hostAndPath);
    return { hostname: u.hostname, path: u.pathname + u.search };
  } catch { return null; }
}

const CONTENT_TYPES = {
  wasm: "application/wasm",
  js:   "application/javascript",
  pck:  "application/octet-stream",
  data: "application/octet-stream",
  png:  "image/png",
  html: "text/html",
};

// ── IcyStreaming integration ─────────────────────────────────────────────────
// The uploaded Python app contains a self-contained HTML template. Reuse that
// template in the existing Node app so the Movies tab can be upgraded without
// introducing a second server or changing the project's runtime.
const ICY_SOURCE_PATH = join(__dirname, "attached_assets", "icystreaming_1788158658690.py");
const TMDB_BASE = "https://api.themoviedb.org/3";
const ICY_NAVIGATION_GUARD = `<script>
(() => {
  // Keep the movie site in its tab: no popups, external links, or form jumps.
  window.open = () => null;
  document.addEventListener("click", (event) => {
    const link = event.target.closest?.("a");
    if (!link) return;
    const href = link.getAttribute("href") || "";
    if (href && href !== "#" && !href.startsWith("#")) event.preventDefault();
    link.removeAttribute("target");
  }, true);
  document.addEventListener("submit", (event) => event.preventDefault(), true);
})();
</script>`;
let icySourceCache;

async function readIcySource() {
  if (!icySourceCache) icySourceCache = await readFile(ICY_SOURCE_PATH, "utf8");
  return icySourceCache;
}

async function getIcyTemplate() {
  const source = await readIcySource();
  const marker = 'HTML_TEMPLATE = """';
  const start = source.indexOf(marker);
  const end = source.indexOf('"""', start + marker.length);
  if (start === -1 || end === -1) throw new Error("IcyStreaming template not found");
  return source
    .slice(start + marker.length, end)
    .replace("</head>", `${ICY_NAVIGATION_GUARD}</head>`);
}

async function getTmdbApiKey() {
  if (process.env.TMDB_API_KEY) return process.env.TMDB_API_KEY;
  const source = await readIcySource();
  const match = source.match(/TMDB_API_KEY\s*=\s*["']([^"']+)["']/);
  return match?.[1];
}

async function proxyTmdb(res, path, params = {}) {
  try {
    const apiKey = await getTmdbApiKey();
    if (!apiKey) {
      return res.status(503).json({ error: "TMDB_API_KEY is not configured" });
    }

    const url = new URL(`${TMDB_BASE}${path}`);
    url.searchParams.set("api_key", apiKey);
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== "") url.searchParams.set(key, value);
    }

    const upstream = await fetch(url);
    const body = await upstream.text();
    res.setHeader("Cache-Control", "no-store");
    res.setHeader("Content-Type", upstream.headers.get("content-type") || "application/json");
    return res.status(upstream.status).send(body);
  } catch (error) {
    console.error("TMDB proxy error:", error.message);
    return res.status(502).json({ error: "Unable to reach TMDB" });
  }
}

// Fetch a URL following up to 5 redirects; calls back with (err, incomingMsg)
function fetchFollowRedirects(hostname, path, redirectsLeft, cb) {
  if (redirectsLeft <= 0) return cb(new Error("Too many redirects"), null);
  const req = httpsRequest(
    { hostname, path, method: "GET",
      headers: { "User-Agent": "Mozilla/5.0", "Accept": "*/*", "Accept-Encoding": "identity" } },
    (res) => {
      const loc = res.headers.location;
      if ((res.statusCode === 301 || res.statusCode === 302 ||
           res.statusCode === 307 || res.statusCode === 308) && loc) {
        res.resume();
        try {
          const r = new URL(loc);
          fetchFollowRedirects(r.hostname, r.pathname + r.search, redirectsLeft - 1, cb);
        } catch(e) { cb(e, null); }
        return;
      }
      cb(null, res);
    }
  );
  req.on("error", (e) => cb(e, null));
  req.end();
}

// Stream one part (partNum). On success, pipe to res then recurse for next part.
// On 404, close res (all parts done) or send 404 if no parts found.
function streamPart(hostname, basePath, partNum, res, headersWritten) {
  const path = `${basePath}.part${partNum}`;
  fetchFollowRedirects(hostname, path, 5, (err, upstream) => {
    if (err || !upstream || upstream.statusCode !== 200) {
      if (upstream) upstream.resume();
      if (!headersWritten) {
        if (!res.headersSent) res.status(404).send("File not found (no parts)");
      } else {
        res.end();
      }
      return;
    }
    if (!headersWritten) {
      res.status(200);
      res.setHeader("Access-Control-Allow-Origin", "*");
      const ext = basePath.split(".").pop().toLowerCase();
      res.setHeader("Content-Type", CONTENT_TYPES[ext] || "application/octet-stream");
    }
    upstream.on("end", () => streamPart(hostname, basePath, partNum + 1, res, true));
    upstream.on("error", () => { if (!res.writableEnded) res.end(); });
    upstream.pipe(res, { end: false });
  });
}

// Main proxy handler: try direct file first, fall back to part stitching on 404
function proxyFile(hostname, path, res) {
  fetchFollowRedirects(hostname, path, 5, (err, upstream) => {
    if (err) {
      if (!res.headersSent) res.status(502).send("Proxy error: " + err.message);
      return;
    }
    if (upstream.statusCode === 200) {
      res.status(200);
      res.setHeader("Access-Control-Allow-Origin", "*");
      const fwd = ["content-type", "content-length", "cache-control", "last-modified", "etag"];
      fwd.forEach(h => { if (upstream.headers[h]) res.setHeader(h, upstream.headers[h]); });
      upstream.pipe(res);
      return;
    }
    if (upstream.statusCode === 404) {
      upstream.resume();
      // Try assembling from split parts
      streamPart(hostname, path, 1, res, false);
      return;
    }
    if (!res.headersSent) res.status(upstream.statusCode).send("CDN error");
    upstream.resume();
  });
}

// ── CDN proxy route ───────────────────────────────────────────────────────────
app.get("/cdn-proxy/*", (req, res) => {
  const target = jsdToRaw(req.params[0]);
  if (!target) return res.status(400).send("Bad CDN URL");
  proxyFile(target.hostname, target.path, res);
});

// ── Game HTML serving ─────────────────────────────────────────────────────────
// 1. Normalises dead 40-char commit SHA refs → @main  (covers both base href
//    and any hardcoded cdn.jsdelivr.net URLs in script/link tags)
// 2. Rewrites <base href="https://cdn.X.net/..."> → <base href="/cdn-proxy/...">
//    so every asset the game engine resolves goes through our proxy on the same origin.
const SHA_RE = /(cdn\.jsdelivr\.net\/gh\/[^@"']+)@([0-9a-f]{40})/gi;

app.get("/games/:name.html", async (req, res) => {
  try {
    const filePath = join(__dirname, "public", "games", req.params.name + ".html");
    let html = await readFile(filePath, "utf8");

    // Normalise all dead-SHA CDN refs to @main
    html = html.replace(SHA_RE, "$1@main");
    // The geometry game uses jsDelivr's @latest alias, which cannot be
    // translated to raw.githubusercontent.com without resolving the branch.
    html = html.replace(
      /cdn\.jsdelivr\.net\/gh\/web-dashers\/web-dashers\.github\.io@latest/gi,
      "cdn.jsdelivr.net/gh/web-dashers/web-dashers.github.io@main"
    );
    // Avoid a local 404 for the game's root-relative favicon.
    if (req.params.name === "geometry_dash") {
      html = html.replace(
        /(["'])\/assets\//g,
        "$1/cdn-proxy/cdn.jsdelivr.net/gh/web-dashers/web-dashers.github.io@main/assets/"
      );
    }

    // Rewrite ALL absolute cdn.jsdelivr.net and raw.githubusercontent.com references
    // through our proxy — covers <base href>, <script src>, <link href>, and JS strings
    html = html.replace(
      /https?:\/\/(cdn\.jsdelivr\.net|raw\.githubusercontent\.com)\//gi,
      "/cdn-proxy/$1/"
    );

    res.setHeader("Content-Type", "text/html; charset=utf-8");
    res.send(SW_SUPPRESSOR + html);
  } catch {
    res.status(404).send("Game not found");
  }
});

// ── IcyStreaming movie site ──────────────────────────────────────────────────
app.get("/movies.html", async (_req, res) => {
  try {
    res.setHeader("Content-Type", "text/html; charset=utf-8");
    res.setHeader("Cache-Control", "no-store");
    res.setHeader(
      "Content-Security-Policy",
      [
        "default-src 'self'",
        "base-uri 'none'",
        "form-action 'none'",
        "object-src 'none'",
        "script-src 'unsafe-inline'",
        "style-src 'unsafe-inline'",
        "img-src 'self' data: https://image.tmdb.org",
        "connect-src 'self'",
        "frame-src https://player.videasy.net",
        "font-src 'self' data:",
      ].join("; ")
    );
    res.send(await getIcyTemplate());
  } catch {
    res.status(404).send("IcyStreaming page not found");
  }
});

app.get("/api/search", (req, res) =>
  proxyTmdb(res, "/search/multi", { query: req.query.q || "", page: 1 })
);
app.get("/api/trending", (_req, res) =>
  proxyTmdb(res, "/trending/all/week")
);
app.get("/api/now_playing", (_req, res) =>
  proxyTmdb(res, "/movie/now_playing")
);
app.get("/api/upcoming", (_req, res) =>
  proxyTmdb(res, "/movie/upcoming")
);
app.get("/api/top_rated", (req, res) => {
  const mediaType = req.query.type === "tv" ? "tv" : "movie";
  return proxyTmdb(res, `/${mediaType}/top_rated`);
});
app.get("/api/movie/:id", (req, res) =>
  proxyTmdb(res, `/movie/${encodeURIComponent(req.params.id)}`, { append_to_response: "credits" })
);
app.get("/api/tv/:id/season/:season", (req, res) =>
  proxyTmdb(
    res,
    `/tv/${encodeURIComponent(req.params.id)}/season/${encodeURIComponent(req.params.season)}`
  )
);
app.get("/api/tv/:id", (req, res) =>
  proxyTmdb(res, `/tv/${encodeURIComponent(req.params.id)}`, { append_to_response: "credits" })
);

// ── UV / transport routes ─────────────────────────────────────────────────────
app.get("/sw.js", (_req, res) => {
  res.setHeader("Service-Worker-Allowed", "/");
  res.setHeader("Content-Type", "application/javascript");
  res.sendFile(join(__dirname, "public", "sw.js"));
});
app.get("/uv/uv.config.js", (_req, res) => {
  res.setHeader("Content-Type", "application/javascript");
  res.sendFile(join(__dirname, "public", "uv", "uv.config.js"));
});
app.use("/uv/", express.static(uvPath));
app.use("/epoxy/", express.static(epoxyPath));
app.use("/baremux/", express.static(baremuxPath));

// ── Static + fallback ─────────────────────────────────────────────────────────
app.use(express.static(join(__dirname, "public")));
app.get("*", (_req, res) => res.sendFile(join(__dirname, "public", "index.html")));

// ── HTTP server ───────────────────────────────────────────────────────────────
const server = createServer();
server.on("request", (req, res) => {
  if (bare.shouldRoute(req)) bare.routeRequest(req, res);
  else app(req, res);
});
server.on("upgrade", (req, socket, head) => {
  if (bare.shouldRoute(req)) bare.routeUpgrade(req, socket, head);
  else wisp.routeRequest(req, socket, head);
});
server.listen(5000, "0.0.0.0", () => {
  console.log("\n  ★  Universe OS  →  http://localhost:5000\n");
});
