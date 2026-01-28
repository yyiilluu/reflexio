"use client"

import { useEffect } from "react"
import { useRouter } from "next/navigation"
import { useAuth } from "@/lib/auth-context"
import { LandingNav } from "@/components/landing/LandingNav"
import { Hero } from "@/components/landing/Hero"
import { Features } from "@/components/landing/Features"
import { HowItWorks } from "@/components/landing/HowItWorks"
import { ValuePropositions } from "@/components/landing/ValuePropositions"
import { CTA } from "@/components/landing/CTA"
import { Footer } from "@/components/landing/Footer"

export default function LandingPage() {
  const { isAuthenticated, isSelfHost } = useAuth()
  const router = useRouter()

  useEffect(() => {
    // Redirect authenticated users or self-host mode to dashboard
    if (isAuthenticated || isSelfHost) {
      router.push("/dashboard")
    }
  }, [isAuthenticated, isSelfHost, router])

  // Show nothing while redirecting
  if (isAuthenticated || isSelfHost) {
    return null
  }

  return (
    <div className="min-h-screen bg-background">
      <LandingNav />
      <main>
        <Hero />
        <Features />
        <HowItWorks />
        <ValuePropositions />
        <CTA />
      </main>
      <Footer />
    </div>
  )
}
