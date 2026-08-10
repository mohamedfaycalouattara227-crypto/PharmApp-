import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "./accordion";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogTrigger } from "./alert-dialog";
import { Checkbox } from "./checkbox";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "./collapsible";
import { Dialog, DialogContent, DialogTitle, DialogTrigger } from "./dialog";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "./dropdown-menu";
import { Popover, PopoverContent, PopoverTrigger } from "./popover";
import { RadioGroup, RadioGroupItem } from "./radio-group";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./select";
import { Sheet, SheetContent, SheetTitle, SheetTrigger } from "./sheet";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "./tabs";
import { Toggle } from "./toggle";
import { ToggleGroup, ToggleGroupItem } from "./toggle-group";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "./tooltip";

function InteractiveFixture() {
  return <TooltipProvider>
    <Accordion type="single" collapsible><AccordionItem value="a"><AccordionTrigger>Section</AccordionTrigger><AccordionContent>Texte accordéon</AccordionContent></AccordionItem></Accordion>
    <AlertDialog><AlertDialogTrigger>Supprimer</AlertDialogTrigger><AlertDialogContent><AlertDialogAction>Confirmer</AlertDialogAction><AlertDialogCancel>Annuler</AlertDialogCancel></AlertDialogContent></AlertDialog>
    <Checkbox aria-label="Autoriser" />
    <Collapsible><CollapsibleTrigger>Plus</CollapsibleTrigger><CollapsibleContent>Contenu repliable</CollapsibleContent></Collapsible>
    <Dialog><DialogTrigger>Ouvrir dialogue</DialogTrigger><DialogContent><DialogTitle>Dialogue</DialogTitle>Corps</DialogContent></Dialog>
    <DropdownMenu><DropdownMenuTrigger>Menu</DropdownMenuTrigger><DropdownMenuContent><DropdownMenuItem>Action</DropdownMenuItem></DropdownMenuContent></DropdownMenu>
    <Popover><PopoverTrigger>Info</PopoverTrigger><PopoverContent>Information</PopoverContent></Popover>
    <RadioGroup defaultValue="a"><RadioGroupItem value="a" aria-label="Option A" /><RadioGroupItem value="b" aria-label="Option B" /></RadioGroup>
    <Select defaultValue="a"><SelectTrigger aria-label="Choix"><SelectValue placeholder="Choisir" /></SelectTrigger><SelectContent><SelectItem value="a">Alpha</SelectItem><SelectItem value="b">Beta</SelectItem></SelectContent></Select>
    <Sheet><SheetTrigger>Ouvrir panneau</SheetTrigger><SheetContent><SheetTitle>Panneau</SheetTitle>Contenu</SheetContent></Sheet>
    <Tabs defaultValue="a"><TabsList><TabsTrigger value="a">A</TabsTrigger><TabsTrigger value="b">B</TabsTrigger></TabsList><TabsContent value="a">Onglet A</TabsContent><TabsContent value="b">Onglet B</TabsContent></Tabs>
    <Toggle aria-label="Épingler">Épingler</Toggle>
    <ToggleGroup type="single"><ToggleGroupItem value="a">Gauche</ToggleGroupItem><ToggleGroupItem value="b">Droite</ToggleGroupItem></ToggleGroup>
    <Tooltip><TooltipTrigger>Survol</TooltipTrigger><TooltipContent>Conseil</TooltipContent></Tooltip>
  </TooltipProvider>;
}

describe("primitives interactives", () => {
  it("ouvre et ferme les composants de contenu", async () => {
    const user = userEvent.setup();
    render(<InteractiveFixture />);
    fireEvent.click(screen.getByText("Section"));
    expect(screen.getByText("Texte accordéon")).toBeVisible();
    fireEvent.click(screen.getByText("Plus"));
    expect(screen.getByText("Contenu repliable")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Menu" }));
    const action = await screen.findByRole("menuitem", { name: "Action" });
    expect(action).toBeVisible();
    await user.click(action);
    await user.click(screen.getByText("Info"));
    expect(await screen.findByText("Information")).toBeVisible();
    await user.click(screen.getByRole("combobox", { name: "Choix" }));
    expect(await screen.findByRole("option", { name: "Alpha" })).toBeVisible();
    fireEvent.click(screen.getByText("Ouvrir panneau"));
    expect(screen.getByRole("heading", { name: "Panneau" })).toBeVisible();
    fireEvent.click(screen.getByText("Ouvrir dialogue"));
    expect(screen.getByRole("heading", { name: "Dialogue" })).toBeVisible();
  });

  it("gère les contrôles et changements d’onglet", async () => {
    const user = userEvent.setup();
    render(<InteractiveFixture />);
    fireEvent.click(screen.getByRole("checkbox", { name: "Autoriser" }));
    expect(screen.getByRole("checkbox", { name: "Autoriser" })).toBeChecked();
    fireEvent.click(screen.getByRole("radio", { name: "Option B" }));
    expect(screen.getByRole("radio", { name: "Option B" })).toBeChecked();
    const tabB = screen.getByRole("tab", { name: "B" });
    fireEvent.mouseDown(tabB, { button: 0 });
    fireEvent.click(tabB);
    await waitFor(() => expect(screen.getByRole("tabpanel")).toHaveTextContent("Onglet B"));
    const gauche = screen.getByRole("radio", { name: "Gauche" });
    fireEvent.click(gauche);
    expect(gauche).toHaveAttribute("data-state", "on");
  });
});
