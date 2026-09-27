# PhishGuard web preview

A responsive React/Vite page with a live URL scanner and four requested visual integrations.

## Run locally

From the repository root, start the model:

```powershell
python -m uvicorn api:app --app-dir src --port 8001
```

In another terminal:

```powershell
cd web
npm ci
npm run dev
```

Open http://127.0.0.1:5173. Vite proxies /model/health and /model/predict to the local FastAPI service. Copy .env.example to .env to change PHISHGUARD_MODEL_URL.

This page is a local model preview. It does not authenticate or save scans; the existing Express/Expo application remains separate. No sample scores are fabricated when the service is offline.

## Build and verify

```powershell
npm run build
npm run test:e2e
```

Browser tests require both services above and Google Chrome installed. Override the browser channel in playwright.config.js if using Playwright's bundled Chromium. Screenshots and test outputs go to the repository's ignored artifacts directory.

Production builds are in dist/. A production host must reverse-proxy /model to a trusted FastAPI service (or integrate the authenticated Express API). Vite's development proxy does not exist in the built files. The model server does not fetch submitted destinations.

## Visual integrations

- [React Three Fiber](https://github.com/pmndrs/react-three-fiber): custom extruded glass shield, orbit, geometry, lights, and locally generated environment reflections in Visuals.jsx.
- [ShaderGradient](https://github.com/ruucm/shadergradient): animated 3D gradient behind the shield.
- [Liquid Glass JS](https://github.com/dashersw/liquid-glass-js): actual WebGL refraction shader on the floating panel. GlassSurface samples only decorative scene canvases on setup and resize; it never captures the URL field or other page text.
- [Paper liquid-logo](https://github.com/paper-design/liquid-logo): vendored fragment shader and image preprocessing for the liquid-metal shield mark, rendered by LiquidMark.jsx.

The 3D module is loaded separately. Pixel density is capped. Motion can be paused, system reduced-motion preferences are respected, and a static shield replaces WebGL effects when unavailable. Google Fonts is used for Manrope/DM Sans, with local sans-serif fallbacks.

## Design

Pearl (#f8f9fc), ink (#17233e), mist (#dfe6f7), cobalt (#405dcc), and muted slate (#657088).
Manrope carries the headings; DM Sans carries the interface. The main composition pairs left-aligned copy with one floating 3D shield. A full-width scanner anchors the hero, followed by process, research metrics, and questions. Glass is concentrated around the illustration to preserve form readability.

See THIRD_PARTY_NOTICES.md for vendor origins, modifications, and licenses.
