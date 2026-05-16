/**
 * Oubon Shop Automation — TikTok Developer Demo Site
 * ===================================================
 *
 * Purpose: pass TikTok's app review by demonstrating EVERY requested
 * scope end-to-end in the sandbox environment. Built specifically to
 * address the prior rejection:
 *
 *   "Scopes mismatch — All selected products and scopes must be
 *    clearly demonstrated in the video... You are required to use
 *    sandbox to demonstrate the integration. Please remove Share
 *    Kit, as it is only applicable to mobile apps."
 *
 * Scopes demonstrated (Share Kit was removed per the rejection):
 *
 *   Login Kit:
 *     - user.info.basic       (open_id, avatar, display_name)
 *
 *   Identity (Login Kit beyond basic):
 *     - user.info.profile     (profile_web_link, bio, is_verified)
 *     - user.info.stats       (follower/following/likes/video counts)
 *
 *   Content Posting API:
 *     - video.upload          (upload to user's account as DRAFT)
 *     - video.publish         (publish directly to user's profile)
 *
 * Each route renders a banner naming the scope being exercised so the
 * reviewer can verify every scope is actually used in the video.
 */

require('dotenv').config();
const express = require('express');
const session = require('express-session');
const axios = require('axios');
const multer = require('multer');
const crypto = require('crypto');
const fs = require('fs');
const path = require('path');

const app = express();
const upload = multer({ dest: path.join(__dirname, 'uploads/') });

// Make sure uploads dir exists
const uploadsDir = path.join(__dirname, 'uploads');
if (!fs.existsSync(uploadsDir)) fs.mkdirSync(uploadsDir, { recursive: true });

// --- Config ----------------------------------------------------------
const CLIENT_KEY      = process.env.TIKTOK_CLIENT_KEY      || '';
const CLIENT_SECRET   = process.env.TIKTOK_CLIENT_SECRET   || '';
const REDIRECT_URI    = process.env.TIKTOK_REDIRECT_URI    || 'http://localhost:3000/auth/tiktok/callback';
const API_BASE        = process.env.TIKTOK_API_BASE        || 'https://open.tiktokapis.com';
const AUTH_BASE       = process.env.TIKTOK_AUTH_BASE       || 'https://www.tiktok.com';
const SESSION_SECRET  = process.env.SESSION_SECRET         || 'demo-session-secret-change-me';
const PORT            = parseInt(process.env.PORT || '3000', 10);

// All scopes we need to demonstrate. Order matters for clarity in the
// authorization URL (TikTok shows them to the user during consent).
const SCOPES = [
  'user.info.basic',
  'user.info.profile',
  'user.info.stats',
  'video.upload',
  'video.publish',
].join(',');

if (!CLIENT_KEY || !CLIENT_SECRET) {
  console.error('\n[FATAL] TIKTOK_CLIENT_KEY and TIKTOK_CLIENT_SECRET must be set.');
  console.error('Copy .env.example to .env and fill in your sandbox credentials from');
  console.error('the TikTok Developer Portal.\n');
  process.exit(1);
}

// --- Middleware ------------------------------------------------------
app.use(express.urlencoded({ extended: true }));
app.use(express.json());
app.use(session({
  secret: SESSION_SECRET,
  resave: false,
  saveUninitialized: false,
  cookie: { httpOnly: true, maxAge: 24 * 60 * 60 * 1000 },
}));

// --- Tiny HTML helper ------------------------------------------------
// One layout to keep the demo recording visually consistent. The
// "Now demonstrating: <scope>" banner is the most important part —
// it's what the reviewer is looking for.
function page({ title, scope, body, user }) {
  const scopeBanner = scope
    ? `<div class="scope-banner">📍 NOW DEMONSTRATING SCOPE: <code>${scope}</code></div>`
    : '';
  const userLine = user
    ? `<div class="user-pill">Logged in as ${user.display_name || user.open_id} (sandbox)</div>`
    : '';
  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>${title} — Oubon Shop Automation</title>
  <style>
    :root {
      --bg: #0a0a0f;
      --card: #14141c;
      --border: #2a2a3a;
      --accent: #25f4ee;
      --accent2: #fe2c55;
      --text: #f3f3f5;
      --muted: #9b9bb0;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      background: var(--bg);
      color: var(--text);
      min-height: 100vh;
    }
    header {
      padding: 20px 32px;
      border-bottom: 1px solid var(--border);
      display: flex;
      align-items: center;
      justify-content: space-between;
    }
    header h1 { margin: 0; font-size: 22px; }
    header .brand { display: flex; align-items: center; gap: 12px; }
    header .brand .logo {
      width: 36px; height: 36px; border-radius: 8px;
      background: linear-gradient(135deg, var(--accent), var(--accent2));
      color: #000; font-weight: 900; display: grid; place-items: center;
    }
    nav { display: flex; gap: 16px; }
    nav a { color: var(--muted); text-decoration: none; padding: 6px 12px; border-radius: 6px; }
    nav a:hover { background: var(--card); color: var(--text); }
    .scope-banner {
      background: linear-gradient(90deg, rgba(37,244,238,0.12), rgba(254,44,85,0.12));
      border: 1px solid var(--accent);
      padding: 12px 32px;
      font-weight: 600;
      letter-spacing: 0.02em;
    }
    .scope-banner code {
      background: rgba(0,0,0,0.3); padding: 2px 8px; border-radius: 4px;
      color: var(--accent);
    }
    .user-pill {
      background: var(--card); border: 1px solid var(--border);
      padding: 6px 12px; border-radius: 6px; font-size: 13px;
      color: var(--muted);
    }
    .why-box {
      background: rgba(37,244,238,0.06);
      border-left: 3px solid var(--accent);
      padding: 12px 16px;
      margin: 12px 0 24px 0;
      font-size: 14px;
      line-height: 1.5;
      color: var(--text);
    }
    .why-box strong { color: var(--accent); }
    main { max-width: 900px; margin: 32px auto; padding: 0 32px; }
    .card {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 24px;
      margin-bottom: 20px;
    }
    h2 { margin-top: 0; }
    .btn {
      display: inline-block;
      background: linear-gradient(90deg, var(--accent), var(--accent2));
      color: #000;
      padding: 12px 24px;
      border-radius: 8px;
      text-decoration: none;
      font-weight: 700;
      border: none;
      cursor: pointer;
      font-size: 16px;
    }
    .btn.secondary {
      background: var(--card); color: var(--text);
      border: 1px solid var(--border);
    }
    .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
    .stat { background: var(--bg); padding: 16px; border-radius: 8px; border: 1px solid var(--border); }
    .stat .label { color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: 0.05em; }
    .stat .value { font-size: 24px; font-weight: 700; margin-top: 4px; }
    .videos { display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 12px; }
    .video { background: var(--bg); border-radius: 8px; overflow: hidden; border: 1px solid var(--border); }
    .video img { width: 100%; aspect-ratio: 9/16; object-fit: cover; display: block; }
    .video .meta { padding: 8px; font-size: 12px; }
    .raw {
      background: #050507; padding: 16px; border-radius: 8px;
      font-family: 'SF Mono', Menlo, monospace; font-size: 12px;
      white-space: pre-wrap; word-break: break-word; color: var(--muted);
      max-height: 280px; overflow: auto;
    }
    .avatar { width: 64px; height: 64px; border-radius: 50%; vertical-align: middle; }
    .muted { color: var(--muted); font-size: 14px; }
    .row { display: flex; gap: 12px; flex-wrap: wrap; align-items: center; margin-top: 16px; }
    form .form-row { margin-bottom: 12px; }
    form input[type=file], form input[type=text] {
      background: var(--bg); border: 1px solid var(--border); color: var(--text);
      padding: 8px 12px; border-radius: 6px; width: 100%;
    }
    form label { display: block; color: var(--muted); font-size: 13px; margin-bottom: 4px; }
    .ok { color: var(--accent); }
    .err { color: var(--accent2); }
  </style>
</head>
<body>
  <header>
    <div class="brand">
      <div class="logo">O</div>
      <h1>Oubon Shop Automation</h1>
    </div>
    <nav>
      <a href="/">Home</a>
      ${user ? `<a href="/dashboard">Dashboard</a>` : ''}
      ${user ? `<a href="/upload">Upload</a>` : ''}
      ${user ? `<a href="/summary">Demo Summary</a>` : ''}
      ${user ? `<a href="/logout">Logout</a>` : ''}
    </nav>
  </header>
  ${scopeBanner}
  ${userLine ? `<div style="padding: 8px 32px; background: var(--card); border-bottom: 1px solid var(--border);">${userLine}</div>` : ''}
  <main>
    ${body}
  </main>
</body>
</html>`;
}

// --- Routes ----------------------------------------------------------

// Landing page
app.get('/', (req, res) => {
  const user = req.session.user;
  if (user) return res.redirect('/dashboard');

  res.send(page({
    title: 'Welcome',
    body: `
      <div class="card">
        <h2>Oubon Shop Automation</h2>
        <p class="muted">
          Automates product discovery for Shopify dropshipping merchants
          using TikTok creator presence as a winner-proof signal. To
          analyze trending products in your TikTok account, connect your
          TikTok via Login Kit below.
        </p>
        <p class="muted">
          This demo runs against the TikTok <strong>Sandbox</strong>
          environment for app review purposes.
        </p>
        <div class="row">
          <a class="btn" href="/auth/login">Continue with TikTok</a>
          <span class="muted">— required scopes: user.info.basic, user.info.profile, user.info.stats, video.upload, video.publish</span>
        </div>
      </div>
    `,
  }));
});

// Step 1 — Login Kit: kick off OAuth flow
app.get('/auth/login', (req, res) => {
  const state = crypto.randomBytes(16).toString('hex');
  req.session.oauth_state = state;

  // TikTok OAuth authorize URL. `scope` is the comma-separated list
  // of scopes we want — Login Kit consent screen will show each one.
  const params = new URLSearchParams({
    client_key: CLIENT_KEY,
    response_type: 'code',
    scope: SCOPES,
    redirect_uri: REDIRECT_URI,
    state,
  });
  const authorizeUrl = `${AUTH_BASE}/v2/auth/authorize/?${params.toString()}`;
  console.log('\n[Login Kit] Redirecting user to TikTok authorize URL:');
  console.log(authorizeUrl);
  console.log('');
  res.redirect(authorizeUrl);
});

// Step 2 — Login Kit callback: exchange code for access token
app.get('/auth/tiktok/callback', async (req, res) => {
  const { code, state, error, error_description } = req.query;

  if (error) {
    return res.send(page({
      title: 'Login failed',
      body: `<div class="card"><h2>❌ Login error</h2>
        <p class="err">${error}: ${error_description || ''}</p>
        <a class="btn secondary" href="/">Back home</a></div>`,
    }));
  }
  if (!code) {
    return res.status(400).send('Missing code');
  }
  if (!state || state !== req.session.oauth_state) {
    return res.status(400).send('State mismatch — possible CSRF');
  }

  // Exchange the authorization code for an access token
  try {
    const tokenResp = await axios.post(
      `${API_BASE}/v2/oauth/token/`,
      new URLSearchParams({
        client_key: CLIENT_KEY,
        client_secret: CLIENT_SECRET,
        code,
        grant_type: 'authorization_code',
        redirect_uri: REDIRECT_URI,
      }).toString(),
      { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } },
    );

    const { access_token, refresh_token, open_id, scope, expires_in } = tokenResp.data;
    if (!access_token) {
      throw new Error('No access_token in response: ' + JSON.stringify(tokenResp.data));
    }

    req.session.tokens = { access_token, refresh_token, open_id, scope, expires_in };
    console.log('[Login Kit] Token exchange success. Scopes granted:', scope);

    res.redirect('/dashboard');
  } catch (e) {
    console.error('[Login Kit] Token exchange failed:', e.response?.data || e.message);
    res.status(500).send(page({
      title: 'Token exchange failed',
      body: `<div class="card"><h2>❌ Token exchange failed</h2>
        <pre class="raw">${JSON.stringify(e.response?.data || e.message, null, 2)}</pre>
        <a class="btn secondary" href="/">Back home</a></div>`,
    }));
  }
});

// Logout
app.get('/logout', (req, res) => {
  req.session.destroy(() => res.redirect('/'));
});

// Helper: bail to login if no token
function requireAuth(req, res, next) {
  if (!req.session.tokens?.access_token) return res.redirect('/');
  next();
}

// Step 3 — Dashboard: demonstrates user.info.basic + user.info.profile + user.info.stats
//
// Calls /v2/user/info/ once with a `fields` parameter covering all three
// scopes, then renders the data clearly labeled so each scope is visible.
app.get('/dashboard', requireAuth, async (req, res) => {
  const { access_token } = req.session.tokens;

  // Field list maps to scopes:
  //   user.info.basic    → open_id, union_id, avatar_url, display_name
  //   user.info.profile  → bio_description, profile_deep_link, is_verified, username
  //   user.info.stats    → follower_count, following_count, likes_count, video_count
  const fields = [
    // user.info.basic
    'open_id', 'union_id', 'avatar_url', 'display_name',
    // user.info.profile
    'bio_description', 'profile_deep_link', 'is_verified', 'username',
    // user.info.stats
    'follower_count', 'following_count', 'likes_count', 'video_count',
  ].join(',');

  try {
    const resp = await axios.get(`${API_BASE}/v2/user/info/?fields=${fields}`, {
      headers: { Authorization: `Bearer ${access_token}` },
    });
    const data = resp.data?.data?.user || {};
    req.session.user = data;

    res.send(page({
      title: 'Dashboard',
      scope: 'user.info.basic + user.info.profile + user.info.stats',
      user: data,
      body: `
        <div class="card">
          <h2>Connected TikTok Account</h2>
          <p class="muted">Below shows data fetched from <code>GET /v2/user/info/</code>
          using all three identity scopes. Each section is labeled with the
          scope that authorized it.</p>

          <h3>📍 Scope: <code>user.info.basic</code></h3>
          <p>
            <img class="avatar" src="${data.avatar_url || ''}" alt="avatar" />
            <strong>${data.display_name || '(no name)'}</strong><br/>
            <span class="muted">open_id: ${data.open_id || ''}</span><br/>
            <span class="muted">union_id: ${data.union_id || ''}</span>
          </p>
          <div class="why-box">
            <strong>Why Oubon Shop Automation needs this:</strong>
            We display the connected creator's identity in the Oubon Shop
            Automation dashboard so multiple users managing the same
            dropshipping store can see who's authorized to post on TikTok.
          </div>

          <h3>📍 Scope: <code>user.info.profile</code></h3>
          <p>
            <strong>Username:</strong> @${data.username || '(none)'}<br/>
            <strong>Verified:</strong> ${data.is_verified ? '✓ Verified' : 'No'}<br/>
            <strong>Profile URL:</strong> ${data.profile_deep_link
              ? `<a href="${data.profile_deep_link}" target="_blank">${data.profile_deep_link}</a>` : '(none)'}<br/>
            <strong>Bio:</strong> ${data.bio_description || '(empty)'}
          </p>
          <div class="why-box">
            <strong>Why Oubon Shop Automation needs this:</strong>
            We read the verified status and profile URL to determine whether
            the connected account meets TikTok's monetization criteria, and
            to deep-link customers to the seller's TikTok shop from Oubon
            Shop product pages.
          </div>

          <h3>📍 Scope: <code>user.info.stats</code></h3>
          <div class="grid">
            <div class="stat"><div class="label">Followers</div><div class="value">${data.follower_count ?? 0}</div></div>
            <div class="stat"><div class="label">Following</div><div class="value">${data.following_count ?? 0}</div></div>
            <div class="stat"><div class="label">Total Likes</div><div class="value">${data.likes_count ?? 0}</div></div>
            <div class="stat"><div class="label">Total Videos</div><div class="value">${data.video_count ?? 0}</div></div>
          </div>
          <div class="why-box">
            <strong>Why Oubon Shop Automation needs this:</strong>
            We use follower count, engagement totals, and video count to
            recommend ad spend tiers and creative angles. A creator with
            50k+ followers gets a different campaign suggestion than a
            creator just starting out.
          </div>

          <div class="row">
            <a class="btn" href="/upload">Next: upload a video →</a>
          </div>
        </div>

        <details class="card"><summary class="muted">Raw API response</summary>
          <pre class="raw">${JSON.stringify(resp.data, null, 2)}</pre>
        </details>
      `,
    }));
  } catch (e) {
    console.error('[user.info] fetch failed:', e.response?.data || e.message);
    res.status(500).send(page({
      title: 'User info failed',
      body: `<div class="card"><h2>❌ user.info fetch failed</h2>
        <pre class="raw">${JSON.stringify(e.response?.data || e.message, null, 2)}</pre>
        <a class="btn secondary" href="/">Back home</a></div>`,
    }));
  }
});

// Step 4 — upload form: render the page that exercises video.upload + video.publish
app.get('/upload', requireAuth, (req, res) => {
  const flash = req.session.flash;
  req.session.flash = null;

  // Privacy options shared by both forms.
  const privacySelect = `
    <select name="privacy_level" style="background: var(--bg); color: var(--text); border: 1px solid var(--border); padding: 8px 12px; border-radius: 6px;">
      <option value="SELF_ONLY">SELF_ONLY (private — recommended for sandbox demo)</option>
      <option value="MUTUAL_FOLLOW_FRIENDS">MUTUAL_FOLLOW_FRIENDS</option>
      <option value="PUBLIC_TO_EVERYONE">PUBLIC_TO_EVERYONE</option>
    </select>
  `;

  res.send(page({
    title: 'Upload',
    user: req.session.user,
    body: `
      ${flash ? `<div class="card"><p class="${flash.ok ? 'ok' : 'err'}">${flash.message}</p></div>` : ''}

      <!-- ============ SECTION 1: video.upload (draft) ============ -->
      <div class="card">
        <div class="scope-banner" style="margin: -24px -24px 16px -24px; border-radius: 8px 8px 0 0;">
          📍 NOW DEMONSTRATING SCOPE: <code>video.upload</code>
        </div>
        <h2>Upload as DRAFT</h2>
        <p class="muted">
          Calls <code>POST /v2/post/publish/inbox/video/init/</code> with the
          <code>video.upload</code> scope. The video lands in the connected
          user's TikTok drafts where they can edit it before publishing.
        </p>
        <div class="why-box">
          <strong>What this scope does for the seller:</strong>
          Sellers can stage promotional videos as drafts in their TikTok
          account, then edit captions and hashtags in TikTok before going
          live.
        </div>

        <form method="post" action="/upload" enctype="multipart/form-data">
          <input type="hidden" name="action" value="upload" />
          <div class="form-row">
            <label>Video file (mp4/mov, ≤ 50MB)</label>
            <input type="file" name="video" accept="video/mp4,video/quicktime" required />
          </div>
          <div class="form-row">
            <label>Post caption</label>
            <input type="text" name="title" placeholder="Demo post from Oubon Shop Automation" />
          </div>
          <div class="row">
            <button class="btn" type="submit">video.upload (save as draft)</button>
          </div>
        </form>
      </div>

      <!-- ============ SECTION 2: video.publish (direct) ============ -->
      <div class="card">
        <div class="scope-banner" style="margin: -24px -24px 16px -24px; border-radius: 8px 8px 0 0;">
          📍 NOW DEMONSTRATING SCOPE: <code>video.publish</code>
        </div>
        <h2>Publish DIRECTLY</h2>
        <p class="muted">
          Calls <code>POST /v2/post/publish/video/init/</code> with the
          <code>video.publish</code> scope. The video posts straight to the
          connected user's profile — no draft step.
        </p>
        <div class="why-box">
          <strong>What this scope does for the seller:</strong>
          When a campaign is approved by the seller, Oubon Shop Automation
          auto-publishes the promotional video directly to TikTok without
          manual intervention.
        </div>

        <form method="post" action="/upload" enctype="multipart/form-data">
          <input type="hidden" name="action" value="publish" />
          <div class="form-row">
            <label>Video file (mp4/mov, ≤ 50MB)</label>
            <input type="file" name="video" accept="video/mp4,video/quicktime" required />
          </div>
          <div class="form-row">
            <label>Post caption</label>
            <input type="text" name="title" placeholder="Demo post from Oubon Shop Automation" />
          </div>
          <div class="form-row">
            <label>Privacy</label>
            ${privacySelect}
          </div>
          <div class="row">
            <button class="btn secondary" type="submit">video.publish (post directly)</button>
          </div>
        </form>
      </div>
    `,
  }));
});

// Step 5b — handle the upload + publish form post
app.post('/upload', requireAuth, upload.single('video'), async (req, res) => {
  const { access_token } = req.session.tokens;
  const { action, title = '', privacy_level = 'SELF_ONLY' } = req.body;
  const file = req.file;

  if (!file) {
    req.session.flash = { ok: false, message: 'No file uploaded' };
    return res.redirect('/upload');
  }

  const videoSize = fs.statSync(file.path).size;

  try {
    // STEP 1: init the upload. The endpoint differs by action.
    //   - video.upload   → /v2/post/publish/inbox/video/init/   (draft)
    //   - video.publish  → /v2/post/publish/video/init/          (direct post)
    const initUrl = action === 'publish'
      ? `${API_BASE}/v2/post/publish/video/init/`
      : `${API_BASE}/v2/post/publish/inbox/video/init/`;

    const initPayload = action === 'publish'
      ? {
          post_info: {
            title: title || 'Demo post from Oubon Shop Automation',
            privacy_level,
            disable_duet: false,
            disable_comment: false,
            disable_stitch: false,
            video_cover_timestamp_ms: 1000,
          },
          source_info: {
            source: 'FILE_UPLOAD',
            video_size: videoSize,
            chunk_size: videoSize,
            total_chunk_count: 1,
          },
        }
      : {
          source_info: {
            source: 'FILE_UPLOAD',
            video_size: videoSize,
            chunk_size: videoSize,
            total_chunk_count: 1,
          },
        };

    const initResp = await axios.post(initUrl, initPayload, {
      headers: { Authorization: `Bearer ${access_token}`, 'Content-Type': 'application/json' },
    });

    const { publish_id, upload_url } = initResp.data?.data || {};
    if (!publish_id || !upload_url) {
      throw new Error('Init returned no publish_id or upload_url: ' + JSON.stringify(initResp.data));
    }

    // STEP 2: actually upload the video bytes to the upload_url
    const videoBuffer = fs.readFileSync(file.path);
    await axios.put(upload_url, videoBuffer, {
      headers: {
        'Content-Type': 'video/mp4',
        'Content-Length': videoSize.toString(),
        'Content-Range': `bytes 0-${videoSize - 1}/${videoSize}`,
      },
      maxBodyLength: Infinity,
      maxContentLength: Infinity,
    });

    // Clean up the temp file
    try { fs.unlinkSync(file.path); } catch {}

    const scopeName = action === 'publish' ? 'video.publish' : 'video.upload';
    req.session.flash = {
      ok: true,
      message: `✅ ${scopeName} succeeded. publish_id=${publish_id}${action === 'publish' ? ' — Direct post submitted to TikTok.' : ' — Saved as draft on user account; open TikTok to publish.'}`,
    };
    req.session.completedScopes = req.session.completedScopes || {};
    req.session.completedScopes[scopeName] = true;
    res.redirect('/summary');
  } catch (e) {
    try { fs.unlinkSync(file.path); } catch {}
    console.error(`[${action}] failed:`, e.response?.data || e.message);
    req.session.flash = {
      ok: false,
      message: `❌ ${action} failed: ${JSON.stringify(e.response?.data || e.message)}`,
    };
    res.redirect('/upload');
  }
});

// Step 6 — Demo Summary: end-of-flow recap with checkmarks per scope.
// All identity scopes are marked done once the dashboard has been visited
// (because /dashboard issues the single /v2/user/info/ call that returns
// fields gated by all three). Content Posting scopes flip to done after
// the corresponding form submission succeeds (see completedScopes above).
app.get('/summary', requireAuth, (req, res) => {
  const completed = req.session.completedScopes || {};
  const flash = req.session.flash;
  req.session.flash = null;

  // The dashboard route caches the user blob; if we have it, all three
  // identity scopes have been demonstrated.
  const identityDone = !!req.session.user;

  const scopes = [
    {
      name: 'user.info.basic',
      done: identityDone,
      desc: 'Connected creator identity (avatar, display name, open_id). Shown on the Dashboard so multi-user dropshipping stores can see who is authorized to post.',
    },
    {
      name: 'user.info.profile',
      done: identityDone,
      desc: 'Verified status and profile URL. Used to gate monetization features and deep-link customers to the seller\'s TikTok shop from Oubon Shop product pages.',
    },
    {
      name: 'user.info.stats',
      done: identityDone,
      desc: 'Follower / engagement / video counts. Used to recommend ad spend tiers and creative angles per connected creator.',
    },
    {
      name: 'video.upload',
      done: !!completed['video.upload'],
      desc: 'Upload promotional video to the seller\'s TikTok as a DRAFT so they can edit caption and hashtags before publishing.',
    },
    {
      name: 'video.publish',
      done: !!completed['video.publish'],
      desc: 'Publish an approved campaign video directly to the seller\'s TikTok profile without manual intervention.',
    },
  ];

  const rows = scopes.map(s => `
    <tr>
      <td style="font-size: 22px; padding: 8px 12px;">${s.done ? '✅' : '⬜'}</td>
      <td style="padding: 8px 12px;"><code>${s.name}</code></td>
      <td style="padding: 8px 12px; color: var(--text);">${s.desc}</td>
    </tr>
  `).join('');

  res.send(page({
    title: 'Demo Summary',
    user: req.session.user,
    body: `
      ${flash ? `<div class="card"><p class="${flash.ok ? 'ok' : 'err'}">${flash.message}</p></div>` : ''}

      <div class="card">
        <h2>Scope Demonstration Recap</h2>
        <p class="muted">All five scopes the Oubon Shop Automation app requests. ✅ marks a scope whose API call this session has actually exercised.</p>

        <table style="width: 100%; border-collapse: collapse; margin-top: 16px;">
          <thead>
            <tr style="border-bottom: 1px solid var(--border);">
              <th style="text-align: left; padding: 8px 12px;">Status</th>
              <th style="text-align: left; padding: 8px 12px;">Scope</th>
              <th style="text-align: left; padding: 8px 12px;">How it's used</th>
            </tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>

        <div class="row" style="margin-top: 24px;">
          <a class="btn secondary" href="/dashboard">Re-visit Dashboard</a>
          <a class="btn secondary" href="/upload">Re-visit Upload</a>
        </div>
      </div>
    `,
  }));
});

// Health check (handy for confirming the server is up on Apple's reviewer's screen)
app.get('/health', (req, res) => res.json({ ok: true, demo: 'oubon-shop-automation' }));

// --- Start -----------------------------------------------------------
app.listen(PORT, () => {
  console.log(`\n╔════════════════════════════════════════════════════════════╗`);
  console.log(`║  Oubon Shop Automation — TikTok Demo Site                  ║`);
  console.log(`║  Sandbox-mode credentials in use                           ║`);
  console.log(`╠════════════════════════════════════════════════════════════╣`);
  console.log(`║  Server running at: http://localhost:${PORT}                  ║`);
  console.log(`║  Redirect URI:       ${REDIRECT_URI.padEnd(38)}║`);
  console.log(`║  Scopes:             ${SCOPES.padEnd(38)}║`);
  console.log(`╚════════════════════════════════════════════════════════════╝\n`);
  console.log(`Open http://localhost:${PORT} to start the demo flow.`);
});
