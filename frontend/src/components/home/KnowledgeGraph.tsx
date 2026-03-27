'use client'

import React, { useEffect, useRef } from 'react'

interface Node {
  x: number
  y: number
  vx: number
  vy: number
  baseRadius: number
  baseAlpha: number
  index: number
  isAgent: boolean
}

// Convert CSS variable hex to RGB format recognizable by canvas
function hexToRgb(hex: string): string {
  // Try to match shorthand or full hex
  const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex.trim()) ||
                 /^#?([a-f\d])([a-f\d])([a-f\d])$/i.exec(hex.trim());
                 
  if (result) {
    if (result[0].length === 4) { // shorthand
       return `${parseInt(result[1]+result[1], 16)}, ${parseInt(result[2]+result[2], 16)}, ${parseInt(result[3]+result[3], 16)}`
    }
    return `${parseInt(result[1], 16)}, ${parseInt(result[2], 16)}, ${parseInt(result[3], 16)}`
  }
  return '255, 255, 255' // fallback to white
}

export default function KnowledgeGraph() {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    // Media query to stop animation for users who prefer reduced motion
    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    
    // Read colors from Tailwind CSS variables
    const computedStyle = getComputedStyle(document.documentElement)
    // Extracting hex and converting to rgb components for rgba() usage
    let lineRgb = hexToRgb(computedStyle.getPropertyValue('--border') || '#e5e7eb')
    let nodeRgb = hexToRgb(computedStyle.getPropertyValue('--foreground') || '#09090b')

    let animationFrameId: number
    const nodes: Node[] = []
    const CONNECTION_DISTANCE = 140

    // Initialize nodes
    const initNodes = () => {
      nodes.length = 0
      
      const createNode = (index: number, isAgent: boolean, minR: number, maxR: number, alpha: number) => {
        const baseRadius = Math.random() * (maxR - minR) + minR
        nodes.push({
          x: Math.random() * window.innerWidth,
          y: Math.random() * window.innerHeight,
          vx: (Math.random() - 0.5) * 0.12 * baseRadius,
          vy: (Math.random() - 0.5) * 0.12 * baseRadius,
          baseRadius,
          baseAlpha: alpha,
          index,
          isAgent
        })
      }

      // 7 Agent nodes
      for (let i = 0; i < 7; i++) createNode(i, true, 3.5, 5, 0.28)
      // 10 Mid-tier nodes
      for (let i = 0; i < 10; i++) createNode(i + 7, false, 2, 3, 0.18)
      // 25 Ambient nodes
      for (let i = 0; i < 25; i++) createNode(i + 17, false, 1, 1.8, 0.10)
    }

    // Set canvas size
    const resizeCanvas = () => {
      canvas.width = window.innerWidth
      canvas.height = window.innerHeight
      // Re-read colors in case theme switched (light/dark)
      const updatedStyle = getComputedStyle(document.documentElement)
      lineRgb = hexToRgb(updatedStyle.getPropertyValue('--border') || '#e5e7eb')
      nodeRgb = hexToRgb(updatedStyle.getPropertyValue('--foreground') || '#09090b')
    }

    window.addEventListener('resize', resizeCanvas)

    // Main render loop
    let frameCount = 0
    const render = () => {
      frameCount++
      ctx.clearRect(0, 0, canvas.width, canvas.height)

      // Only update positions if reduced motion is not preferred
      if (!prefersReducedMotion) {
        nodes.forEach(node => {
          node.x += node.vx
          node.y += node.vy

          // Wrap around screen edges
          if (node.x < 0) node.x = canvas.width
          if (node.x > canvas.width) node.x = 0
          if (node.y < 0) node.y = canvas.height
          if (node.y > canvas.height) node.y = 0
        })
      }

      // Draw edges and calculate connections
      ctx.lineWidth = 0.4
      const connected: number[][] = Array.from({ length: nodes.length }, () => [])

      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const dx = nodes[i].x - nodes[j].x
          const dy = nodes[i].y - nodes[j].y
          const distance = Math.hypot(dx, dy)

          if (distance < CONNECTION_DISTANCE) {
            connected[i].push(j)

            const opacity = (1 - distance / CONNECTION_DISTANCE) * 0.07
            ctx.beginPath()
            ctx.strokeStyle = `rgba(${nodeRgb}, ${opacity})`
            ctx.moveTo(nodes[i].x, nodes[i].y)
            ctx.lineTo(nodes[j].x, nodes[j].y)
            ctx.stroke()
          }
        }
      }

      // Draw subtle triangle meshes
      ctx.fillStyle = `rgba(${nodeRgb}, 0.032)`
      for (let i = 0; i < nodes.length; i++) {
        const neighbors = connected[i]
        for (let jIdx = 0; jIdx < neighbors.length; jIdx++) {
          const j = neighbors[jIdx]
          for (let kIdx = jIdx + 1; kIdx < neighbors.length; kIdx++) {
            const k = neighbors[kIdx]
            
            if (connected[j].includes(k)) {
              ctx.beginPath()
              ctx.moveTo(nodes[i].x, nodes[i].y)
              ctx.lineTo(nodes[j].x, nodes[j].y)
              ctx.lineTo(nodes[k].x, nodes[k].y)
              ctx.closePath()
              ctx.fill()
            }
          }
        }
      }

      // Draw nodes
      nodes.forEach(node => {
        const r = node.isAgent 
          ? node.baseRadius + Math.sin(Date.now() / 1400 + node.index * 0.4) * 0.8 
          : node.baseRadius

        ctx.beginPath()
        ctx.arc(node.x, node.y, r, 0, Math.PI * 2)
        ctx.fillStyle = `rgba(${nodeRgb}, ${node.baseAlpha})`
        ctx.fill()
      })

      animationFrameId = requestAnimationFrame(render)
    }

    // Initial setup and start loop
    initNodes()
    resizeCanvas()
    render()

    return () => {
      cancelAnimationFrame(animationFrameId)
      window.removeEventListener('resize', resizeCanvas)
    }
  }, [])

  return (
    <canvas
      ref={canvasRef}
      className="fixed inset-0 pointer-events-none -z-10"
      aria-hidden="true"
    />
  )
}