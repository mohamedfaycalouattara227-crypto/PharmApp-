/**
 * use-mobile.test.ts — Tests du hook useIsMobile
 * Couverture : 100% lignes/branches
 */

import { describe, it, expect, beforeEach, vi } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useIsMobile } from "@/hooks/use-mobile";

// ── Helpers mock MediaQueryList ─────────────────────────────────────────────

function mockMatchMedia(largeur: number) {
  const listeners: Array<() => void> = [];
  const mql = {
    matches: largeur < 768,
    addEventListener: vi.fn((_evt: string, cb: () => void) => listeners.push(cb)),
    removeEventListener: vi.fn(),
  };
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: vi.fn().mockReturnValue(mql),
  });
  Object.defineProperty(window, "innerWidth", {
    writable: true,
    value: largeur,
  });
  return { mql, listeners };
}

describe("useIsMobile", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("retourne true sur mobile (375px)", () => {
    mockMatchMedia(375);
    const { result } = renderHook(() => useIsMobile());
    expect(result.current).toBe(true);
  });

  it("retourne false sur desktop (1280px)", () => {
    mockMatchMedia(1280);
    const { result } = renderHook(() => useIsMobile());
    expect(result.current).toBe(false);
  });

  it("retourne false exactement à 768px (breakpoint exclu)", () => {
    mockMatchMedia(768);
    const { result } = renderHook(() => useIsMobile());
    expect(result.current).toBe(false);
  });

  it("retourne true à 767px (juste sous le breakpoint)", () => {
    mockMatchMedia(767);
    const { result } = renderHook(() => useIsMobile());
    expect(result.current).toBe(true);
  });

  it("réagit au changement de taille via l'écouteur MQ", () => {
    const { listeners } = mockMatchMedia(1280);
    const { result } = renderHook(() => useIsMobile());
    expect(result.current).toBe(false);

    // Simuler passage en mobile
    Object.defineProperty(window, "innerWidth", { writable: true, value: 375 });
    act(() => {
      listeners.forEach((fn) => fn());
    });
    expect(result.current).toBe(true);
  });

  it("supprime l'écouteur au démontage", () => {
    const { mql } = mockMatchMedia(1280);
    const { unmount } = renderHook(() => useIsMobile());
    unmount();
    expect(mql.removeEventListener).toHaveBeenCalledTimes(1);
  });
});
