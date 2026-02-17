# Navigator CLI — Landing Page

A React splash page for [Navigator CLI](https://github.com/.../navigator), styled like the Ollama homepage.

## Run locally

```bash
npm install
npm run dev
```

Open http://localhost:5173

## Build

```bash
npm run build
```

Output is in `dist/`.

To include the CLI wheel in the build (for the Download page):

```bash
npm run build:all
```

This builds the Navigator Python package, copies the wheel to `public/downloads/`, then builds the site.

## Deploy to Netlify

1. **Connect your repo** — In [Netlify](https://app.netlify.com), add a new site and connect your Git repository.

2. **Set the base directory** — If your repo root is `shell-chat` or `navigator`, set the base directory to `landing` (or `navigator/landing` if the repo root is `shell-chat`).

3. **Build settings** — Netlify will use `netlify.toml` in this folder:
   - Build command: `npm run build:all`
   - Publish directory: `dist`

4. **Custom domain** — For the one-line install to work, add a custom domain (e.g. `getnavigator.app`) in Netlify. The install script uses `https://getnavigator.app` by default. For testing on a Netlify subdomain, run: `curl -fsSL https://yoursite.netlify.app/install.sh | NAVIGATOR_INSTALL_URL=https://yoursite.netlify.app sh`

5. **Deploy** — Netlify will build and deploy. The SPA redirect is configured so `/docs` and other routes work correctly. `/install.sh` and `/downloads/*` are served as static files.
