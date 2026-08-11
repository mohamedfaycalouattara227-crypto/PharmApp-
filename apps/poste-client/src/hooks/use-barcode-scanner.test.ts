/**
 * Tests — hooks/use-barcode-scanner.ts
 * Couvre : useCodeBarreScanner — onScan, actif, longueurMin, ignorer champs formulaire
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useCodeBarreScanner } from "@/hooks/use-barcode-scanner";

// ── Helpers pour simuler les keydown ─────────────────────────────────────────

function pressKey(key: string, target?: EventTarget) {
  const event = new KeyboardEvent("keydown", { key, bubbles: true });
  if (target) {
    Object.defineProperty(event, "target", { value: target, configurable: true });
  }
  document.dispatchEvent(event);
}

function simuFastScan(code: string) {
  // Scan rapide : chaque touche envoyée sans délai (< 50ms → scanner)
  for (const char of code) {
    pressKey(char);
  }
  pressKey("Enter");
}

// ── Tests ─────────────────────────────────────────────────────────────────────

describe("useCodeBarreScanner", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.runAllTimers();
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("appelle onScan avec le bon code après un scan rapide + Enter", () => {
    const onScan = vi.fn();
    renderHook(() => useCodeBarreScanner({ onScan, actif: true }));

    act(() => {
      simuFastScan("5901234123457");
    });

    expect(onScan).toHaveBeenCalledWith("5901234123457");
  });

  it("n'appelle pas onScan si actif=false", () => {
    const onScan = vi.fn();
    renderHook(() => useCodeBarreScanner({ onScan, actif: false }));

    act(() => {
      simuFastScan("1234567890");
    });

    expect(onScan).not.toHaveBeenCalled();
  });

  it("n'appelle pas onScan si le code est trop court (< longueurMin)", () => {
    const onScan = vi.fn();
    renderHook(() => useCodeBarreScanner({ onScan, actif: true, longueurMin: 6 }));

    act(() => {
      simuFastScan("abc"); // longueur 3 < 6
    });

    expect(onScan).not.toHaveBeenCalled();
  });

  it("n'appelle pas onScan si le focus est sur un INPUT", () => {
    const onScan = vi.fn();
    renderHook(() => useCodeBarreScanner({ onScan, actif: true }));

    // Créer un input focusé
    const input = document.createElement("input");
    document.body.appendChild(input);

    act(() => {
      for (const char of "1234567") {
        const event = new KeyboardEvent("keydown", { key: char, bubbles: true });
        Object.defineProperty(event, "target", { value: input, configurable: true });
        document.dispatchEvent(event);
      }
      const enter = new KeyboardEvent("keydown", { key: "Enter", bubbles: true });
      Object.defineProperty(enter, "target", { value: input, configurable: true });
      document.dispatchEvent(enter);
    });

    expect(onScan).not.toHaveBeenCalled();
    document.body.removeChild(input);
  });

  it("retourne dernierCode=null initialement", () => {
    const onScan = vi.fn();
    const { result } = renderHook(() => useCodeBarreScanner({ onScan, actif: true }));
    expect(result.current.dernierCode).toBeNull();
  });

  it("retourne scanEnCours=false initialement", () => {
    const onScan = vi.fn();
    const { result } = renderHook(() => useCodeBarreScanner({ onScan, actif: true }));
    expect(result.current.scanEnCours).toBe(false);
  });

  it("met à jour dernierCode après un scan réussi", () => {
    const onScan = vi.fn();
    const { result } = renderHook(() => useCodeBarreScanner({ onScan, actif: true }));

    act(() => {
      simuFastScan("9876543210123");
    });

    expect(result.current.dernierCode).toBe("9876543210123");
  });

  it("se désabonne proprement au démontage", () => {
    const onScan = vi.fn();
    const removeEventListenerSpy = vi.spyOn(document, "removeEventListener");
    const { unmount } = renderHook(() => useCodeBarreScanner({ onScan, actif: true }));

    unmount();

    expect(removeEventListenerSpy).toHaveBeenCalledWith("keydown", expect.any(Function));
  });

  it("annule le timer de flush au démontage si un scan est en cours", () => {
    const onScan = vi.fn();
    const { unmount } = renderHook(() => useCodeBarreScanner({ onScan, actif: true }));

    act(() => {
      pressKey("A");
    });

    unmount();
  });

  it("ne fait rien si Enter est pressé alors que le buffer est vide", () => {
    const onScan = vi.fn();
    renderHook(() => useCodeBarreScanner({ onScan, actif: true }));

    act(() => {
      pressKey("Enter");
    });

    expect(onScan).not.toHaveBeenCalled();
  });

  it("ignore les saisies lentes d'un humain après un premier scan", () => {
    const onScan = vi.fn();
    renderHook(() => useCodeBarreScanner({ onScan, actif: true }));

    act(() => {
      simuFastScan("1234");
    });
    expect(onScan).toHaveBeenCalledWith("1234");
    onScan.mockClear();

    // Attendre plus que delaiInterTouche (ex: 200ms)
    act(() => {
      vi.advanceTimersByTime(200);
      pressKey("A");
    });

    // "A" doit être ignoré, le buffer reste vide
    act(() => {
      pressKey("Enter");
    });
    expect(onScan).not.toHaveBeenCalled();
  });
});
