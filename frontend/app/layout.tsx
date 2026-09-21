import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { Toaster } from "@/components/ui/sonner";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Orquestador de Viajes · Planifica tu viaje con IA",
  description:
    "Sistema multiagente que genera planes de viaje completos a partir de una petición en lenguaje natural. Vuelos, hoteles, clima y recomendaciones culturales coordinados por un grafo de orquestación.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="es"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col bg-gradient-to-b from-background via-background to-muted/30">
        {children}
        <Toaster richColors position="top-center" />
      </body>
    </html>
  );
}
