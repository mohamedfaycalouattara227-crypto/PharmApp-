import "@testing-library/jest-dom/vitest";

// JSDOM ne fournit pas les méthodes Pointer Capture utilisées par Radix.
// Le polyfill reste volontairement sans état : il reproduit l’API nécessaire
// aux événements de test sans modifier le comportement applicatif.
if (!HTMLElement.prototype.hasPointerCapture) {
  HTMLElement.prototype.hasPointerCapture = () => false;
}
if (!HTMLElement.prototype.setPointerCapture) {
  HTMLElement.prototype.setPointerCapture = () => undefined;
}
if (!HTMLElement.prototype.releasePointerCapture) {
  HTMLElement.prototype.releasePointerCapture = () => undefined;
}
if (!HTMLElement.prototype.scrollIntoView) {
  HTMLElement.prototype.scrollIntoView = () => undefined;
}
