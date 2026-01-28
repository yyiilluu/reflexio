"use client"

import { usePathname, useRouter } from "next/navigation"
import { useEffect } from "react"
import { useAuth } from "@/lib/auth-context"
import { ResponsiveSidebar } from "@/components/responsive-sidebar"

export function LayoutContent({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  const router = useRouter()
  const { isAuthenticated, isSelfHost } = useAuth()

  // Hide sidebar on auth-related pages and landing page
  const authPages = ["/login", "/register", "/forgot-password", "/reset-password", "/verify-email", "/resend-verification"]
  const isAuthPage = authPages.includes(pathname)
  const isLandingPage = pathname === "/"

  // Redirect to login if not authenticated and not in self-host mode
  useEffect(() => {
    // Skip auth check for auth pages, landing page, and self-host mode
    if (isAuthPage || isLandingPage || isSelfHost) {
      return
    }

    // Redirect to login if not authenticated
    if (!isAuthenticated) {
      router.push("/login")
    }
  }, [isAuthenticated, isSelfHost, isAuthPage, isLandingPage, pathname, router])

  if (isAuthPage || isLandingPage) {
    // Auth pages and landing page get full screen without sidebar
    return <>{children}</>
  }

  // Don't render protected pages until auth check is complete
  if (!isSelfHost && !isAuthenticated) {
    return null
  }

  // Regular pages get sidebar layout
  return (
    <div className="flex h-screen overflow-hidden">
      <ResponsiveSidebar />
      <main className="flex-1 overflow-y-auto bg-background pt-16 md:pt-0">
        {children}
      </main>
    </div>
  )
}
