import { cn } from '@/utils/cn'
import {
  AsteriskIcon, AtomIcon, BrainIcon, BoxIcon, CloudIcon, CompassIcon, CpuIcon,
  GitBranchIcon, GlobeIcon, KeyIcon, LayersIcon, RouteIcon, SmileIcon,
  SparklesIcon, WindIcon, ZapIcon,
} from '@/components/Icons'

/**
 * A recognizable glyph per provider, rendered inside the standard gradient
 * tile. Every provider keeps its own color (providerColor) but no longer
 * shows the same generic CPU icon everywhere.
 */
const PROVIDER_GLYPHS: Record<string, React.FC<{ size?: number; className?: string }>> = {
  openai: SparklesIcon,
  openai_compatible: SparklesIcon,
  anthropic: AsteriskIcon,
  google: GlobeIcon,
  google_vertex: CloudIcon,
  groq: ZapIcon,
  groq_openai: ZapIcon,
  mistral: WindIcon,
  deepseek: BrainIcon,
  openrouter: RouteIcon,
  cerebras: CpuIcon,
  huggingface: SmileIcon,
  together_ai: LayersIcon,
  ollama: BoxIcon,
  azure: CloudIcon,
  github: GitBranchIcon,
  github_models: GitBranchIcon,
  nvidia: CpuIcon,
  nvidia_nim: CpuIcon,
  sambanova: AtomIcon,
  llmapi: ZapIcon,
  agentrouter: CompassIcon,
  custom: KeyIcon,
  default: CpuIcon,
}

export function ProviderGlyph({ provider, size = 15 }: { provider: string; size?: number }) {
  const key = (provider || '').toLowerCase()
  const Glyph = PROVIDER_GLYPHS[key] || PROVIDER_GLYPHS.default
  return <Glyph size={size} className="text-white" />
}

/** Standard colored tile + provider glyph used in lists and tables. */
export function ProviderAvatar({
  provider,
  color,
  size = 'md',
}: {
  provider: string
  color: string
  size?: 'sm' | 'md' | 'lg'
}) {
  const box =
    size === 'sm'
      ? 'w-8 h-8 rounded-lg'
      : size === 'lg'
        ? 'w-11 h-11 rounded-2xl'
        : 'w-10 h-10 rounded-xl'
  const glyph = size === 'sm' ? 14 : size === 'lg' ? 18 : 16
  return (
    <div className={cn('bg-gradient-to-br flex items-center justify-center flex-shrink-0', box, color)}>
      <ProviderGlyph provider={provider} size={glyph} />
    </div>
  )
}

/** Glyph-only helper used by the Providers page tile inside colored boxes. */
export function ProviderIcon({ icon, size = 18 }: { icon: string; size?: number }) {
  const key = (icon || '').toLowerCase()
  const Glyph = PROVIDER_GLYPHS[key] || PROVIDER_GLYPHS.default
  return <Glyph size={size} className="text-white" />
}
