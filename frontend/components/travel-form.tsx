"use client";

import * as React from "react";
import { format } from "date-fns";
import type { DateRange } from "react-day-picker";
import { Plane, MapPin, Wallet, Users, Sparkles, Loader2 } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent } from "@/components/ui/card";
import { DateRangePicker } from "@/components/date-range-picker";
import { generatePlan, type PlanResponse } from "@/lib/api";

interface TravelFormProps {
  onResult: (result: PlanResponse) => void;
}

export function TravelForm({ onResult }: TravelFormProps) {
  const [ciudad, setCiudad] = React.useState("");
  const [dateRange, setDateRange] = React.useState<DateRange | undefined>();
  const [origen, setOrigen] = React.useState("MAD");
  const [presupuesto, setPresupuesto] = React.useState("800");
  const [adultos, setAdultos] = React.useState("2");
  const [contexto, setContexto] = React.useState("");
  const [loading, setLoading] = React.useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!ciudad.trim()) {
      toast.error("Indica la ciudad de destino");
      return;
    }

    setLoading(true);
    try {
      const result = await generatePlan({
        ciudad: ciudad.trim(),
        contexto_viaje: contexto.trim(),
        fecha_inicio: dateRange?.from ? format(dateRange.from, "yyyy-MM-dd") : "",
        fecha_fin: dateRange?.to ? format(dateRange.to, "yyyy-MM-dd") : "",
        origen_iata: origen.trim().toUpperCase() || "MAD",
        presupuesto_total_eur: Number(presupuesto) || 0,
        adultos: Number(adultos) || 1,
      });
      onResult(result);
      toast.success("Plan de viaje generado");
    } catch (err) {
      const message = err instanceof Error ? err.message : "Error desconocido";
      toast.error("No se pudo generar el plan", { description: message });
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card className="border-border/60 bg-card/70 backdrop-blur shadow-xl">
      <CardContent className="p-6 sm:p-8">
        <form onSubmit={handleSubmit} className="space-y-5">
          <div className="space-y-2">
            <Label htmlFor="ciudad" className="flex items-center gap-2 text-sm font-medium">
              <MapPin className="h-4 w-4 text-primary" />
              Ciudad destino
            </Label>
            <Input
              id="ciudad"
              placeholder="Ej. Roma, París, Tokio..."
              value={ciudad}
              onChange={(e) => setCiudad(e.target.value)}
              className="h-11"
              autoComplete="off"
            />
          </div>

          <div className="space-y-2">
            <Label className="flex items-center gap-2 text-sm font-medium">
              <Plane className="h-4 w-4 text-primary" />
              Fechas del viaje
            </Label>
            <DateRangePicker value={dateRange} onChange={setDateRange} />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="space-y-2">
              <Label htmlFor="origen" className="text-sm font-medium">
                Origen (IATA)
              </Label>
              <Input
                id="origen"
                placeholder="MAD"
                value={origen}
                onChange={(e) => setOrigen(e.target.value.toUpperCase())}
                maxLength={3}
                className="h-11 uppercase"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="presupuesto" className="flex items-center gap-2 text-sm font-medium">
                <Wallet className="h-4 w-4 text-primary" />
                Presupuesto (€)
              </Label>
              <Input
                id="presupuesto"
                type="number"
                inputMode="numeric"
                min={0}
                step={50}
                value={presupuesto}
                onChange={(e) => setPresupuesto(e.target.value)}
                className="h-11"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="adultos" className="flex items-center gap-2 text-sm font-medium">
                <Users className="h-4 w-4 text-primary" />
                Viajeros
              </Label>
              <Input
                id="adultos"
                type="number"
                inputMode="numeric"
                min={1}
                max={9}
                value={adultos}
                onChange={(e) => setAdultos(e.target.value)}
                className="h-11"
              />
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="contexto" className="flex items-center gap-2 text-sm font-medium">
              <Sparkles className="h-4 w-4 text-primary" />
              ¿Qué tipo de viaje buscas?
            </Label>
            <Textarea
              id="contexto"
              placeholder="Ej. escapada cultural de fin de semana, viaje romántico, ruta gastronómica..."
              value={contexto}
              onChange={(e) => setContexto(e.target.value)}
              className="min-h-[88px] resize-none"
              maxLength={300}
            />
            <p className="text-xs text-muted-foreground">
              Describe el propósito del viaje en lenguaje natural. El sistema interpretará tu intención.
            </p>
          </div>

          <Button
            type="submit"
            disabled={loading}
            size="lg"
            className="w-full h-12 text-base font-medium"
          >
            {loading ? (
              <>
                <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                Generando plan de viaje...
              </>
            ) : (
              <>
                <Sparkles className="mr-2 h-5 w-5" />
                Generar plan de viaje
              </>
            )}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
