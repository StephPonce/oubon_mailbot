import { motion } from 'framer-motion';
import { cn } from '@/lib/utils';

interface GlassPanelProps {
  children: React.ReactNode;
  className?: string;
  depth?: number;
  delay?: number;
}

export const GlassPanel = ({
  children,
  className,
  depth = 60,
  delay = 0
}: GlassPanelProps) => (
  <motion.div
    initial={{ opacity: 0, y: 80, rotateX: -20, scale: 0.95 }}
    animate={{ opacity: 1, y: 0, rotateX: 0, scale: 1 }}
    transition={{
      duration: 1.4,
      delay,
      ease: [0.16, 1, 0.3, 1]
    }}
    whileHover={{
      y: -5,
      transition: { duration: 0.3, ease: 'easeOut' }
    }}
    style={{
      transform: `translateZ(${depth}px)`,
      transformStyle: 'preserve-3d'
    }}
    className={cn("glass p-8", className)}
  >
    {children}
  </motion.div>
);
