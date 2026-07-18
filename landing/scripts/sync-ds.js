/**
 * Copy shared design-system CSS into landing so Next/PostCSS can resolve it
 * (Turbopack cannot import outside the app, and Windows junctions are
 * unreliable here). Source of truth: /design-system.
 *
 * Dual dest: app/theme (file-relative from app/globals.css) and theme
 * (PostCSS/Tailwind resolves ./theme from the landing package root).
 */
const fs = require("fs");
const path = require("path");

const root = path.join(__dirname, "..", "..", "design-system");
const dests = [
  path.join(__dirname, "..", "app", "theme"),
  path.join(__dirname, "..", "theme"),
];

for (const dest of dests) {
  fs.mkdirSync(dest, { recursive: true });
  for (const file of ["tokens.css", "components.css"]) {
    fs.copyFileSync(path.join(root, file), path.join(dest, file));
  }
}
console.log("synced design-system → landing/app/theme + landing/theme");
