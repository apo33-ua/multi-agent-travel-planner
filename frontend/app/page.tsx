"use client";

import * as React from "react";
import { Plane, Cloud, Hotel, Compass } from "lucide-react";

import { TravelForm } from "@/components/travel-form";
import { TravelResult } from "@/components/travel-result";
import type { PlanResponse } from "@/lib/api";

export default function HomePage() {
  const [result, setResult] = React.useState<PlanResponse | null>(null);

  return (
    <main className="relative w-full">
      <div className="absolute inset-x-0 top-0 -z-10 h-[480px] bg-gradient-to-br from-sky-100 via-indigo-50 to-rose-50 dark:from-sky-950/40 dark:via-indigo-950/30 dark:to-rose-950/20" />
      <div className="absolute inset-x-0 top-0 -z-10 h-[480px] bg-[radial-gradient(60%_60%_at_50%_0%,rgba(56,189,248,0.18),transparent_70%)]" />

      <div className="mx-auto max-w-4xl px-4 sm:px-6 py-10 sm:py-16">
        {!result ? (
          <>
            <header className="text-center mb-10 sm:mb-14">
              <div className="inline-flex items-center gap-2 rounded-full border border-border/60 bg-card/70 backdrop-blur px-4 py-1.5 mb-6 text-xs font-medium text-muted-foreground shadow-sm">
                <Compass className="h-3.5 w-3.5 text-primary" />
                Sistema multiagente con LangGraph
              </div>
              <h1 className="text-4xl sm:text-5xl font-bold tracking-tight bg-gradient-to-br from-foreground to-foreground/70 bg-clip-text text-transparent">
                Planifica tu próximo viaje con IA
              </h1>
              <p className="mt-4 text-base sm:text-lg text-muted-foreground max-w-2xl mx-auto leading-relaxed">
                Indica el destino, las fechas y tu presupuesto. El sistema coordina agentes especializados en
                vuelos, hoteles, clima y cultura para devolverte un itinerario completo en segundos.
              </p>

              <div className="mt-8 flex flex-wrap items-center justify-center gap-2 text-xs text-muted-foreground">
                <FeaturePill icon={<Plane className="h-3.5 w-3.5" />} label="Vuelos reales" />
                <FeaturePill icon={<Hotel className="h-3.5 w-3.5" />} label="Hoteles" />
                <FeaturePill icon={<Cloud className="h-3.5 w-3.5" />} label="Previsión meteorológica" />
                <FeaturePill icon={<Compass className="h-3.5 w-3.5" />} label="Itinerario cultural" />
              </div>
            </header>

            <TravelForm onResult={setResult} />

            <p className="text-center text-xs text-muted-foreground mt-8">
              Las consultas se procesan a través de un grafo de orquestación multiagente coordinado por LangGraph.
              <br className="hidden sm:inline" />
              Vuelos y hoteles vía SerpApi · Clima vía OpenWeather · LLM Google Gemini
            </p>
          </>
        ) : (
          <TravelResult result={result} onReset={() => setResult(null)} />
        )}
      </div>
    </main>
  );
}

function FeaturePill({ icon, label }: { icon: React.ReactNode; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-border/50 bg-card/60 backdrop-blur px-3 py-1">
      {icon}
      {label}
    </span>
  );
}
