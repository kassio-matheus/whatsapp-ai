import { Geist_Mono, Inter } from "next/font/google"

import "@workspace/ui/globals.css"
import { NuqsAdapter } from "nuqs/adapters/next/app"
import { ThemeProvider } from "@/components/theme-provider"
import { cn } from "@workspace/ui/lib/utils"

const inter = Inter({ subsets: ["latin"], variable: "--font-sans" })

const fontMono = Geist_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
})

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={cn(
        "antialiased",
        fontMono.variable,
        "font-sans",
        inter.variable
      )}
    >
      <body suppressHydrationWarning>
        <ThemeProvider>
          <NuqsAdapter
            defaultOptions={{
              history: "replace",
              scroll: false,
              clearOnDefault: true,
            }}
          >
            {children}
          </NuqsAdapter>
        </ThemeProvider>
      </body>
    </html>
  )
}
