# Chessist GitHub Page

This folder contains the static site for **Chessist**, hosted on GitHub Pages.

## Add your video

To show a demo video in the hero header:

1. Add your video file as **`video/hero.mp4`** in this folder.
2. The page will automatically use it as the full-width header video (autoplay, muted, loop).
3. If the file is missing, a styled placeholder is shown instead.

Recommended: keep the video short (e.g. 10–30 seconds), and use a reasonable resolution (e.g. 1920×1080 or 1280×720) for fast loading.

## Enable GitHub Pages

1. Open your repo on GitHub: **Settings → Pages**.
2. Under **Build and deployment**, set **Source** to **Deploy from a branch**.
3. Choose **Branch:** `main` (or `master`), **Folder:** **`/docs`**.
4. Click **Save**. The site will be published at:
   - **`https://<username>.github.io/chessist`** (if the repo is named `chessist`)
   - or **`https://<username>.github.io/<repo-name>`** for your actual repo name.

Changes pushed to the `main` branch in the `docs/` folder will update the live site after a short delay.

## Screenshot on the page

To show the app screenshot in the **Screenshots** section, copy the repo’s sample image into this folder:

- From repo root: copy `sample_screenshot.png` to `docs/assets/img/screenshot.png`.

If the file is missing, the page shows a short placeholder message instead.

## Local preview

Open `docs/index.html` in a browser, or serve the folder with any static server, for example:

```bash
cd docs && python -m http.server 8000
```

Then visit `http://localhost:8000`.
