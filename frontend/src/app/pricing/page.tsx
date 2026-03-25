'use client'

import { Navbar } from '@/components/layout/Navbar'
import { Footer } from '@/components/layout/Footer'
import { Pricing } from '@/components/home/Pricing'

export default function PricingPage() {
  return (
    <>
      <Navbar />
      <main className="pt-20 pb-20">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-12">
          <div className="text-center space-y-4 mb-12">
            <h1
              className="text-4xl md:text-5xl lg:text-6xl font-light"
              style={{ fontFamily: "var(--font-display)" }}
            >
              Simple, Transparent Pricing
            </h1>
            <p className="mx-auto max-w-2xl text-lg text-muted-foreground">
              Scale your research needs with plans designed for everyone
            </p>
          </div>
        </div>
        <Pricing />
      </main>
      <Footer />
    </>
  )
}
