# Third-party source notices

## dashersw/liquid-glass-js

Source: https://github.com/dashersw/liquid-glass-js
Vendored file: src/vendor/liquid-glass/container.js
License: MIT; full notice in src/vendor/liquid-glass/LICENSE.
Local changes: add ES module export and retain the scroll-handler reference for cleanup.
GlassSurface.jsx subclasses the container to supply a decorative-only canvas snapshot instead of html2canvas page capture. No upstream controls or demo application are included.

## paper-design/liquid-logo

Source: https://github.com/paper-design/liquid-logo
Vendored files: src/vendor/liquid-logo/liquid-frag.ts and parse-logo-image.ts.
License: PolyForm Shield 1.0.0; full terms in src/vendor/liquid-logo/LICENSE.
Local changes: reduce preprocessing resolution to 128–192 pixels for the small navigation mark.
LiquidMark.jsx supplies an application-specific WebGL lifecycle and the original PhishGuard shield SVG.

## Installed packages

React Three Fiber and ShaderGradient are installed through npm; versions are locked in package-lock.json.
Their original repositories are https://github.com/pmndrs/react-three-fiber and https://github.com/ruucm/shadergradient.
Package notices and licenses remain in the installed packages.
