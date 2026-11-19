# Vendored GSAP

- **Package:** `gsap`
- **Version:** `3.14.2`
- **File:** `gsap.min.js` (minified `dist/` build)
- **Upstream:** <https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js>
  (taken from the `gsap@3.14.2` npm tarball, `dist/gsap.min.js`)
- **License:** GreenSock Standard "No Charge" License —
  <https://gsap.com/standard-license>. The license header is preserved in
  `gsap.min.js`.

## Why this file is committed

The HyperFrames templates (`../templates/index.html.j2`,
`../templates/scene.html.j2`) load GSAP from this directory with a relative
`src` first, so rendering works on hosts without outbound network access. A
CDN copy is kept only as a fallback for projects rendered without the vendored
asset (issue #869).
