# Oubon Shop Automation — TikTok Developer Demo Site

This is a tiny local Express server that demonstrates **every scope**
your TikTok Developer Portal app (`Oubon Shop Automation`) requests,
designed to pass app review.

It exists because of the prior rejection:

> **Scopes mismatch.** Note from reviewer: All selected products and
> scopes must be clearly demonstrated in the video. If you don't need
> certain products or scopes, make sure to remove them before review.
> You are required to use sandbox to demonstrate the integration.
> Please remove Share Kit, as it is only applicable to mobile apps.

This site exercises each scope in a way that's **visible on camera**
— every page shows a banner naming the scope being demonstrated.

---

## What it demonstrates

| Product | Scope | Where in this demo |
|---|---|---|
| Login Kit | `user.info.basic` | OAuth flow + Dashboard page |
| Login Kit | `user.info.profile` | Dashboard page (verified status, bio, profile URL) |
| Login Kit | `user.info.stats` | Dashboard page (follower/like/video counts) |
| Content Posting API | `video.upload` | Upload page (uploads file as DRAFT) |
| Content Posting API | `video.publish` | Upload page (publishes directly) |

**Share Kit is intentionally NOT requested.** It was removed from the
scope list per the reviewer's explicit instruction.

---

## Before You Run

### 1. In the TikTok Developer Portal

1. Go to your app → **Sandbox** tab (not Production).
2. Under **Login Kit → Redirect URI**, add:
   ```
   http://localhost:3000/auth/tiktok/callback
   ```
   You can have up to 10 redirect URIs — keep your existing
   `policies.oubonshop.com` one and just ADD the localhost one.
3. Under **Products**, make sure ONLY these are selected:
   - Login Kit
   - Content Posting API
   - **Remove Share Kit if it's still there**
4. Under **Scopes**, make sure these are checked:
   - `user.info.basic`
   - `user.info.profile`
   - `user.info.stats`
   - `video.upload`
   - `video.publish`
5. Copy the **sandbox** Client Key and Client Secret from the
   Credentials section.
6. Under **Sandbox → Target Users**, add yourself as a test user
   (the TikTok account you'll be filming with).

### 2. Install dependencies

```bash
cd tools/tiktok-demo
npm install
```

Requires Node 18+. If you don't have npm, install Node from
https://nodejs.org (use the LTS version).

### 3. Configure credentials

```bash
cp .env.example .env
```

Edit `.env` and paste in the **sandbox** Client Key and Client Secret
you copied from the developer portal. The pre-filled
`TIKTOK_CLIENT_KEY` is the Oubon Shop Automation client key from your
screenshots — verify it matches.

Set `SESSION_SECRET` to a random string (any string is fine for local
dev — e.g. `openssl rand -hex 32` or just type some random characters).

### 4. Start the server

```bash
npm start
```

You should see:
```
Server running at: http://localhost:3000
```

---

## Recording the Demo Video

Use **QuickTime Player** (built into macOS) → File → New Screen
Recording. Or Loom, OBS, whatever you prefer. The reviewer cares
about content, not production value.

### Recording Script (~3-5 minutes total)

Hit record, then walk through this script. **Narrate out loud as
you go** — the reviewer is matching your narration to the scope list.

---

**0:00 – Intro** (10 seconds)

> "Hi, this is the Oubon Shop Automation demo for TikTok app review.
> This integration helps Shopify dropshipping merchants discover
> winning products. I'm running this in the TikTok sandbox
> environment as required. Let's walk through every scope we
> requested."

Show the URL bar: `http://localhost:3000`. Make sure it's clearly
localhost (sandbox), not production.

---

**0:10 – Login Kit + `user.info.basic`** (45 seconds)

Click the **Continue with TikTok** button.

> "First, Login Kit. I'm clicking Continue with TikTok which redirects
> to the TikTok OAuth consent screen."

You'll be redirected to TikTok's sandbox auth. Log in with your test
account. Review the consent screen — point out the scopes being
requested.

> "Here you can see TikTok showing all five scopes I'm requesting:
> user.info.basic, user.info.profile, user.info.stats, video.upload,
> and video.publish. I'm clicking Authorize."

Approve. You'll be redirected back to your localhost dashboard.

> "I'm now logged in. The dashboard page demonstrates the first scope,
> **user.info.basic** — you can see the avatar, display name, and
> open ID rendered here. These came from a single call to
> GET /v2/user/info/."

Point at the on-screen banner that says "NOW DEMONSTRATING SCOPE:
user.info.basic + user.info.profile + user.info.stats".

---

**0:55 – `user.info.profile`** (30 seconds)

Stay on the Dashboard page. Scroll to the **Scope: user.info.profile**
section.

> "Next, the **user.info.profile** scope. The same /v2/user/info/
> call returns the verified status, the bio, and the profile URL.
> You can see those rendered here."

Point at the verified status, bio, profile URL on screen.

---

**1:25 – `user.info.stats`** (30 seconds)

Scroll to the **Scope: user.info.stats** section.

> "And third, the **user.info.stats** scope. The four count fields
> follower_count, following_count, likes_count, and video_count come
> back as part of the same call. You can see them as the four big
> numbers here."

Point at the four stat cards.

---

**1:55 – `video.upload` (DRAFT mode)** (45 seconds)

Click **Next: upload a video →** at the bottom of the Dashboard.

> "Next product — Content Posting API. Two scopes here, both for
> posting — video.upload posts as a draft, and video.publish posts
> directly to the user's profile. I'll demonstrate both."

Click **Choose File** and select a short test video (any .mp4 ≤ 50MB
will do — TikTok recommends keeping demo uploads short).

> "I'm selecting a test video. Now I click **video.upload (save as
> draft)** which calls POST /v2/post/publish/inbox/video/init/ with
> the video.upload scope. This uploads the file to my TikTok account
> as a draft for me to edit before publishing."

Click the **video.upload** button. Wait for the success banner.

> "Success — the response includes a publish_id, and the video is now
> in my drafts. The video.upload scope is verified."

---

**2:40 – `video.publish` (direct post)** (45 seconds)

> "Now video.publish. Same form, different endpoint. This time the
> request goes to POST /v2/post/publish/video/init/ with the
> video.publish scope, and posts directly to my profile."

Optionally select a different video, or use the same one. Click
**video.publish (post directly)**.

> "Success again — publish_id returned, and the video is now posted
> directly to my profile. Both Content Posting API scopes are
> demonstrated."

---

**3:25 – Wrap** (15 seconds)

> "That covers all five scopes I requested: user.info.basic,
> user.info.profile, user.info.stats, video.upload, and
> video.publish. Share Kit is intentionally removed since this is a
> web app. Thanks for reviewing."

Stop recording. Trim the start/end if needed. **Keep it under 5
minutes total** — reviewers prefer concise demos.

---

## Submission Checklist Before You Hit "Submit"

In the Developer Portal **App Review** section:

- [ ] **Products** shows only Login Kit + Content Posting API (no Share Kit)
- [ ] **Scopes** shows the 6 listed above, no more, no fewer
- [ ] **App description**: explain in 1-2 sentences how each product
      and scope is used by the app. Don't mention Share Kit.
- [ ] **Demo video** uploaded (≤ 50MB, mp4 or mov)
- [ ] **Privacy Policy URL** points to a live page
      (`https://policies.oubonshop.com/privacy.html`)
- [ ] **Terms of Service URL** points to a live page
- [ ] **Platforms**: only Web is checked
- [ ] **Web/Desktop URL**: a live page (e.g. policies.oubonshop.com)

Then resubmit. Review usually takes 2-5 business days.

---

## Troubleshooting

**"Authorization failed: redirect_uri mismatch"**
Make sure `TIKTOK_REDIRECT_URI` in your `.env` matches EXACTLY what's
in the Developer Portal Redirect URI list. Including the protocol
(`http://` vs `https://`) and any trailing slash.

**"invalid_client" on token exchange**
The Client Key or Client Secret is wrong. Re-copy from the Sandbox
tab of the Developer Portal — production credentials won't work in
sandbox mode.

**"403 Forbidden" on /v2/user/info/**
Your test TikTok account isn't approved as a sandbox user. Go to
Developer Portal → Sandbox → Target Users and add your account.

**Upload returns "video.upload not approved"**
Sandbox apps with not-yet-reviewed scopes can call them, but only
for whitelisted target users. Make sure your test account is added
as a sandbox target user.

---

## What This Site Does NOT Do

- It does NOT touch your production TikTok account — sandbox only.
- It does NOT publish public videos by default — the demo uses
  `SELF_ONLY` privacy so test posts are invisible to other users.
- It does NOT store your access tokens persistently — they live in
  an in-memory session and are cleared when the server restarts.
- It does NOT cover Marketing API (TikTok Ads) — that's a separate
  product with its own review process.
