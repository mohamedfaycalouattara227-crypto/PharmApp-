import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Alert, AlertDescription, AlertTitle } from "./alert";
import { Avatar, AvatarFallback } from "./avatar";
import { Badge } from "./badge";
import { Button } from "./button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "./card";
import { Input } from "./input";
import { Label } from "./label";
import { Progress } from "./progress";
import { Separator } from "./separator";
import { Skeleton } from "./skeleton";
import { Spinner } from "./spinner";
import { Switch } from "./switch";
import { Textarea } from "./textarea";

function renderFondamentaux() {
  return render(
    <main>
      <Button>Enregistrer</Button>
      <Button variant="secondary" size="sm">Secondaire</Button>
      <Button variant="destructive" size="lg">Supprimer</Button>
      <Button variant="outline" size="icon" aria-label="Ouvrir">+</Button>
      <Badge>Actif</Badge>
      <Badge variant="destructive">Erreur</Badge>
      <Card>
        <CardHeader><CardTitle>Catalogue</CardTitle><CardDescription>Gestion des produits</CardDescription></CardHeader>
        <CardContent><p>Contenu</p></CardContent>
        <CardFooter><span>Pied</span></CardFooter>
      </Card>
      <Label htmlFor="nom">Nom</Label>
      <Input id="nom" aria-label="Nom" placeholder="Nom du produit" />
      <Textarea aria-label="Description" />
      <Alert><AlertTitle>Information</AlertTitle><AlertDescription>Opération réussie</AlertDescription></Alert>
      <Avatar><AvatarFallback>PH</AvatarFallback></Avatar>
      <Progress value={42} aria-label="Progression" />
      <Separator />
      <Skeleton data-testid="squelette" />
      <Spinner aria-label="Chargement" />
      <Switch aria-label="Activer" />
    </main>,
  );
}

describe("composants UI fondamentaux", () => {
  it("rend les variantes principales avec leur contenu accessible", () => {
    renderFondamentaux();
    expect(screen.getByRole("button", { name: "Enregistrer" })).toBeVisible();
    expect(screen.getByRole("button", { name: "Secondaire" })).toBeVisible();
    expect(screen.getByRole("button", { name: "Supprimer" })).toBeVisible();
    expect(screen.getByRole("button", { name: "Ouvrir" })).toBeVisible();
    expect(screen.getByText("Actif")).toBeVisible();
    expect(screen.getByText("Catalogue")).toBeVisible();
    expect(screen.getByText("Opération réussie")).toBeVisible();
    expect(screen.getByText("PH")).toBeVisible();
    expect(screen.getByRole("progressbar", { name: "Progression" })).toBeInTheDocument();
  });

  it("expose les champs, états et attributs d’accessibilité", () => {
    renderFondamentaux();
    expect(screen.getByLabelText("Nom")).toHaveAttribute("placeholder", "Nom du produit");
    expect(screen.getByLabelText("Description")).toBeInTheDocument();
    expect(screen.getByRole("switch", { name: "Activer" })).toBeEnabled();
    expect(screen.getByRole("status", { name: "Chargement" })).toBeInTheDocument();
    expect(screen.getByTestId("squelette")).toBeInTheDocument();
  });
});
