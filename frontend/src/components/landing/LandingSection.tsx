'use client'

import { ReactNode } from 'react'
import { motion, HTMLMotionProps, Variants } from 'framer-motion'

interface LandingComponentProps extends HTMLMotionProps<"div"> {
  children: ReactNode
  className?: string
}

const transitionSpring = {
  type: "spring" as const,
  stiffness: 70,
  damping: 15,
  mass: 1
}

const variants: Variants = {
  hidden: { opacity: 0, y: 30 },
  visible: { 
    opacity: 1, 
    y: 0,
    transition: transitionSpring
  }
}

export function LandingSection({ children, className = '', ...props }: LandingComponentProps) {
  return (
    <motion.section
      className={className}
      initial="hidden"
      whileInView="visible"
      viewport={{ once: false, amount: 0.2, margin: "-50px" }}
      variants={{
        visible: {
          transition: {
            staggerChildren: 0.15,
          }
        }
      }}
      {...(props as any)}
    >
      {children}
    </motion.section>
  )
}

export function LandingSectionHeadline({ children, className = '', ...props }: LandingComponentProps) {
  return (
    <motion.div variants={variants} className={className} {...props}>
      {children}
    </motion.div>
  )
}

export function LandingSectionSubtext({ children, className = '', ...props }: LandingComponentProps) {
  return (
    <motion.div variants={variants} className={className} {...props}>
      {children}
    </motion.div>
  )
}

export function LandingSectionCTA({ children, className = '', ...props }: LandingComponentProps) {
  return (
    <motion.div variants={variants} className={className} {...props}>
      {children}
    </motion.div>
  )
}
