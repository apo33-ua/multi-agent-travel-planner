"use client";

import * as React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  ArrowLeft,
  Cloud,
  CloudSun,
  Plane,
  Hotel,
  Sparkles,
  CalendarDays,
  Wallet,
  Cpu,
  RotateCcw,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import type { PlanResponse } from "@/lib/api";

interface TravelResultProps {
  result: PlanResponse;
  onReset: () => void;
}

function decisionLabel(decision?: string): { text: string; tone: "ok" | "warn" | "info" } {
  switch (decision) {
    case "ok":
      return { text: "Combinaciones dentro del presupuesto", tone: "ok" };
    case "solo-sugerencias-fuera-presupuesto":
      return { text: "Sin opciones dentro del presupuesto", tone: "warn" };
    case "sin-datos":
      return { text: "Sin datos suficientes", tone: "info" };
    default:
      return { text: decision || "—", tone: "info" };
  }
}

export function TravelResult({ result, onReset }: TravelResultProps) {
  const auditoria = result.presupuesto?.auditoria;
  const decision = decisionLabel(auditoria?.decision);
  const validas = result.presupuesto?.combinaciones_validas?.length ?? 0;
  const excluidas = result.presupuesto?.combinaciones_excluidas?.length ?? 0;
  const routing = result.routing;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-3">
        <Button variant="ghost" size="sm" onClick={onReset} className="gap-2">
          <ArrowLeft className="h-4 w-4" />
          Nueva búsqueda
        </Button>
        <Button variant="outline" size="sm" onClick={onReset} className="gap-2 sm:hidden">
          <RotateCcw className="h-4 w-4" />
        </Button>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <MetricCard
          icon={<CalendarDays className="h-4 w-4" />}
          label="Modo"
          value={routing.modo_planificacion ?? "—"}
        />
        <MetricCard
          icon={<Wallet className="h-4 w-4" />}
          label="Combinaciones válidas"
          value={String(validas)}
          accent={validas > 0 ? "positive" : "neutral"}
        />
        <MetricCard
          icon={<CloudSun className="h-4 w-4" />}
          label="Clima"
          value={result.clima.consultado ? "Activo" : "Omitido"}
          accent={result.clima.consultado ? "positive" : "muted"}
        />
        <MetricCard
          icon={<Cpu className="h-4 w-4" />}
          label="Modelo LLM"
          value={result.supervisor_modelo ?? "—"}
        />
      </div>

      <Card className="border-border/60 bg-card/70 backdrop-blur shadow-lg">
        <CardContent className="p-6 sm:p-8">
          <div className="flex flex-wrap items-center gap-2 mb-6">
            <Badge variant="secondary" className="gap-1">
              <Sparkles className="h-3 w-3" />
              Plan generado
            </Badge>
            <Badge variant={decision.tone === "ok" ? "default" : decision.tone === "warn" ? "destructive" : "secondary"}>
              {decision.text}
            </Badge>
            {routing.usar_vuelos_hoteles && (
              <Badge variant="outline" className="gap-1">
                <Plane className="h-3 w-3" />
                {result.vuelos.length} vuelos
              </Badge>
            )}
            {routing.usar_vuelos_hoteles && (
              <Badge variant="outline" className="gap-1">
                <Hotel className="h-3 w-3" />
                {result.hoteles.length} hoteles
              </Badge>
            )}
            {result.clima.consultado && (
              <Badge variant="outline" className="gap-1">
                <Cloud className="h-3 w-3" />
                Clima incluido
              </Badge>
            )}
          </div>

          <Separator className="mb-6" />

          <article className="prose prose-slate dark:prose-invert max-w-none prose-headings:scroll-mt-20 prose-h1:text-2xl prose-h2:text-xl prose-h3:text-lg prose-p:leading-relaxed prose-li:my-1">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {result.respuesta_markdown || "*Sin respuesta generada.*"}
            </ReactMarkdown>
          </article>
        </CardContent>
      </Card>

      {routing.motivo_ruta && (
        <p className="text-xs text-muted-foreground text-center px-4">
          <span className="font-medium">Trazabilidad del enrutador:</span> {routing.motivo_ruta}
        </p>
      )}
    </div>
  );
}

interface MetricCardProps {
  icon: React.ReactNode;
  label: string;
  value: string;
  accent?: "positive" | "neutral" | "muted";
}

function MetricCard({ icon, label, value, accent = "neutral" }: MetricCardProps) {
  const accentClass =
    accent === "positive"
      ? "text-emerald-600 dark:text-emerald-400"
      : accent === "muted"
        ? "text-muted-foreground"
        : "text-foreground";

  return (
    <Card className="border-border/60 bg-card/70 backdrop-blur">
      <CardContent className="p-4">
        <div className="flex items-center gap-2 text-xs uppercase tracking-wider text-muted-foreground mb-1">
          {icon}
          <span>{label}</span>
        </div>
        <div className={`text-base sm:text-lg font-semibold capitalize ${accentClass}`}>
          {value}
        </div>
      </CardContent>
    </Card>
  );
}
