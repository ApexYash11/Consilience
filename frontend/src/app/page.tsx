'use client'

import { Navbar } from '@/components/layout/Navbar'
import { Footer } from '@/components/layout/Footer'
import { Hero } from '@/components/home/Hero'
import { Features } from '@/components/home/Features'
import { Pricing } from '@/components/home/Pricing'
import KnowledgeGraph from '@/components/home/KnowledgeGraph'

export default function Home() {
  return (
    <>
      <Navbar />
      <main className="pt-16">
        <KnowledgeGraph />
        <Hero />
        <Features />
        <Pricing />
      </main>
      <Footer />
    </>
  )
}
