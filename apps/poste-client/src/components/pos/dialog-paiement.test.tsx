import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

const mockDetail = vi.hoisted(() => vi.fn());
vi.mock("@/lib/api-client", () => ({
  api: { clients: { detail: mockDetail } },
}));

import { DialogPaiement } from "./dialog-paiement";

function renderDialog(overrides: Partial<React.ComponentProps<typeof DialogPaiement>> = {}) {
  const onValider = vi.fn();
  const onFermer = vi.fn();
  render(<DialogPaiement ouvert total={1000} enCours={false} onValider={onValider} onFermer={onFermer} {...overrides} />);
  return { onValider, onFermer };
}

describe("DialogPaiement", () => {
  it("initialise le montant espèces au total et permet de valider", async () => {
    const user = userEvent.setup();
    const { onValider } = renderDialog();
    expect(screen.getByLabelText(/Montant reçu/)).toHaveValue(1000);
    await user.click(screen.getByRole("button", { name: "Valider la vente" }));
    expect(onValider).toHaveBeenCalledWith({ mode: "especes", encaisse: 1000, referenceMobileMoney: undefined });
  });

  it("bloque les espèces insuffisantes", async () => {
    const user = userEvent.setup();
    renderDialog();
    const input = screen.getByLabelText(/Montant reçu/);
    await user.clear(input);
    await user.type(input, "500");
    expect(screen.getByText("Manque")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Valider la vente" })).toBeDisabled();
  });

  it("exige une référence en mobile money", async () => {
    const user = userEvent.setup();
    const { onValider } = renderDialog();
    await user.click(screen.getByRole("button", { name: /Mobile Money/i }));
    expect(screen.getByText(/référence de transaction est obligatoire/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Valider la vente" })).toBeDisabled();
    await user.type(screen.getByPlaceholderText(/OM-2024/), "OM-123");
    await user.click(screen.getByRole("button", { name: "Valider la vente" }));
    expect(onValider).toHaveBeenCalledWith({ mode: "mobile_money", encaisse: 1000, referenceMobileMoney: "OM-123" });
  });

  it("refuse le crédit sans client et charge les informations avec client", async () => {
    const user = userEvent.setup();
    const { onValider } = renderDialog();
    await user.click(screen.getByRole("button", { name: "Crédit client" }));
    expect(screen.getByText(/Aucun client sélectionné/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Valider la vente" })).toBeDisabled();
    onValider.mockClear();
    mockDetail.mockResolvedValue({ encours_credit: 0, plafond_credit: 5000, credit_autorise: true });
    cleanup();
    const client = renderDialog({ clientId: "client-1" });
    await user.click(screen.getByRole("button", { name: "Crédit client" }));
    await waitFor(() => expect(mockDetail).toHaveBeenCalledWith("client-1"));
    expect(screen.getByRole("button", { name: "Valider la vente" })).not.toBeDisabled();
    expect(client.onFermer).not.toHaveBeenCalled();
  });
});
