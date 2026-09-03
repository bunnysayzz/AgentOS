import React from 'react'

export interface IconProps {
  className?: string
  size?: number
  strokeWidth?: number
  style?: React.CSSProperties
}

/**
 * One geometric system for every glyph in the app:
 *   - 24×24 viewBox, stroke = currentColor, fill = none
 *   - round caps/joins, optical stroke tuning per glyph (1.75 body / 2.0 tiny)
 *   - every icon is aria-hidden and scales from its parent
 */
function icon(displayName: string, node: React.ReactNode, sw = 1.75) {
  const Cmp = ({ className, size = 18, strokeWidth, style }: IconProps) => (
    <svg
      className={className}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth ?? sw}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      style={style}
    >
      {node}
    </svg>
  )
  Cmp.displayName = displayName
  return Cmp
}

/** Small filled accents (dots, keyholes…) — inherit color, no outline. */
const dot = (cx: number, cy: number, r: number) => (
  <circle cx={cx} cy={cy} r={r} fill="currentColor" stroke="none" />
)

// ─── Navigation ───────────────────────────────────────────────────────

export const DashboardIcon = icon('DashboardIcon', (
  <>
    <rect x="3" y="3" width="7" height="9" rx="1.5" />
    <rect x="14" y="3" width="7" height="5" rx="1.5" />
    <rect x="14" y="12" width="7" height="9" rx="1.5" />
    <rect x="3" y="16" width="7" height="5" rx="1.5" />
  </>
))

export const UsersIcon = icon('UsersIcon', (
  <>
    <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
    <circle cx="9" cy="7" r="4" />
    <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
    <path d="M16 3.13a4 4 0 0 1 0 7.75" />
  </>
))

export const BotIcon = icon('BotIcon', (
  <>
    <rect x="3.5" y="6" width="17" height="13" rx="3" />
    <circle cx="8.75" cy="11.5" r="0.75" fill="currentColor" />
    <circle cx="15.25" cy="11.5" r="0.75" fill="currentColor" />
    <path d="M8 3.5l4 2.25L16 3.5" />
    <path d="M12 19v2" />
    <path d="M5.5 19l-1.5 2.5" />
    <path d="M18.5 19l1.5 2.5" />
  </>
), 1.6)

export const WorkflowIcon = icon('WorkflowIcon', (
  <>
    <rect x="2.5" y="2.5" width="5.5" height="5.5" rx="1.5" />
    <rect x="16" y="2.5" width="5.5" height="5.5" rx="1.5" />
    <rect x="9.25" y="16" width="5.5" height="5.5" rx="1.5" />
    <path d="M5.25 8v2.25A1.75 1.75 0 0 0 7 12h10a1.75 1.75 0 0 0 1.75-1.75V8" />
    <path d="M12 12v4" />
  </>
))

export const BrainIcon = icon('BrainIcon', (
  <>
    <path d="M12 4.5A5.5 5.5 0 0 0 7 5.6a4.5 4.5 0 0 0-1 8.9A4.8 4.8 0 0 0 7.6 19a4.6 4.6 0 0 0 4.4 1.6V4.5Z" />
    <path d="M12 4.5A5.5 5.5 0 0 1 17 5.6a4.5 4.5 0 0 1 1 8.9 4.8 4.8 0 0 1-.6 4.5 4.6 4.6 0 0 1-4.4 1.6V4.5Z" />
    <path d="M9 12.5h.01" />
    <path d="M12 14.5h.01" />
    <path d="M15 12.5h.01" />
  </>
), 1.7)

export const WrenchIcon = icon('WrenchIcon', (
  <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z" />
))

export const CpuIcon = icon('CpuIcon', (
  <>
    <rect x="5" y="5" width="14" height="14" rx="2" />
    <rect x="9.5" y="9.5" width="5" height="5" rx="1" />
    <path d="M9 2.5V5" />
    <path d="M15 2.5V5" />
    <path d="M9 19v2.5" />
    <path d="M15 19v2.5" />
    <path d="M2.5 9H5" />
    <path d="M2.5 15H5" />
    <path d="M19 9h2.5" />
    <path d="M19 15h2.5" />
  </>
), 1.6)

export const FileTextIcon = icon('FileTextIcon', (
  <>
    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
    <path d="M14 2v6h6" />
    <path d="M8 13h8" />
    <path d="M8 17h8" />
    <path d="M8 9h2" />
  </>
))

export const KeyIcon = icon('KeyIcon', (
  <>
    <circle cx="8" cy="15" r="4.5" />
    <path d="M21 3l-9.3 9.3" />
    <path d="M15.5 6.5L18 9" />
  </>
))

export const ArchiveIcon = icon('ArchiveIcon', (
  <>
    <rect x="2" y="3" width="20" height="5" rx="1.5" />
    <path d="M4.5 8v11a2 2 0 0 0 2 2h11a2 2 0 0 0 2-2V8" />
    <path d="M10 12.5h4" />
  </>
))

export const GitBranchIcon = icon('GitBranchIcon', (
  <>
    <path d="M6 3v12" />
    <circle cx="18" cy="6" r="3" />
    <circle cx="6" cy="18" r="3" />
    <path d="M18 9a8 8 0 0 1-8 8" />
  </>
))

export const ActivityIcon = icon('ActivityIcon', (
  <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
))

export const LogOutIcon = icon('LogOutIcon', (
  <>
    <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
    <path d="M16 17l5-5-5-5" />
    <path d="M21 12H9" />
  </>
))

// ─── Chevrons & arrows ────────────────────────────────────────────────

export const ChevronLeftIcon = icon('ChevronLeftIcon', (
  <path d="M15 18l-6-6 6-6" />
), 2)

export const ChevronRightIcon = icon('ChevronRightIcon', (
  <path d="M9 18l6-6-6-6" />
), 2)

export const ChevronDownIcon = icon('ChevronDownIcon', (
  <path d="M6 9l6 6 6-6" />
), 2)

export const ChevronUpIcon = icon('ChevronUpIcon', (
  <path d="M18 15l-6-6-6 6" />
), 2)

export const ArrowLeftIcon = icon('ArrowLeftIcon', (
  <>
    <path d="M19 12H5" />
    <path d="M12 19l-7-7 7-7" />
  </>
))

export const ArrowRightIcon = icon('ArrowRightIcon', (
  <>
    <path d="M5 12h14" />
    <path d="M12 5l7 7-7 7" />
  </>
))

export const ArrowUpRightIcon = icon('ArrowUpRightIcon', (
  <>
    <path d="M7 17L17 7" />
    <path d="M7 7h10v10" />
  </>
))

export const XIcon = icon('XIcon', (
  <>
    <path d="M18 6L6 18" />
    <path d="M6 6l12 12" />
  </>
), 2)

// ─── Auth ─────────────────────────────────────────────────────────────

export const GoogleIcon = ({ className, size = 18 }: IconProps) => (
  <svg className={className} width={size} height={size} viewBox="0 0 24 24" aria-hidden="true">
    <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
    <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
    <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z" />
    <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z" />
  </svg>
)

export const CameraIcon = icon('CameraIcon', (
  <>
    <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z" />
    <circle cx="12" cy="13" r="4" />
  </>
))

export const LogInIcon = icon('LogInIcon', (
  <>
    <path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4" />
    <path d="M10 17l5-5-5-5" />
    <path d="M15 12H3" />
  </>
))

export const MailIcon = icon('MailIcon', (
  <>
    <rect x="2" y="4" width="20" height="16" rx="2" />
    <path d="M2 7l10 6L22 7" />
  </>
))

export const LockIcon = icon('LockIcon', (
  <>
    <rect x="5" y="11" width="14" height="10" rx="2" />
    <path d="M8 11V7a4 4 0 0 1 8 0v4" />
    {dot(12, 15.5, 1)}
  </>
))

export const EyeIcon = icon('EyeIcon', (
  <>
    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
    <circle cx="12" cy="12" r="3" />
  </>
))

export const EyeOffIcon = icon('EyeOffIcon', (
  <>
    <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94" />
    <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19" />
    <path d="M1 1l22 22" />
    <path d="M14.12 14.12a3 3 0 1 1-4.24-4.24" />
  </>
))

export const UserIcon = icon('UserIcon', (
  <>
    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
    <circle cx="12" cy="7" r="4" />
  </>
))

export const UserPlusIcon = icon('UserPlusIcon', (
  <>
    <path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
    <circle cx="8.5" cy="7" r="4" />
    <path d="M20 8v6" />
    <path d="M23 11h-6" />
  </>
))

export const UserMinusIcon = icon('UserMinusIcon', (
  <>
    <path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
    <circle cx="8.5" cy="7" r="4" />
    <path d="M23 11h-6" />
  </>
))

export const UserCogIcon = icon('UserCogIcon', (
  <>
    <circle cx="18" cy="15" r="3" />
    <circle cx="9" cy="7" r="4" />
    <path d="M10 15H6a4 4 0 0 0-4 4v1" />
    <path d="M21.7 13.4l-.9.25" />
    <path d="M15.97 16.7l-.46.78" />
    <path d="M18 11.1V12" />
    <path d="M18 18v.9" />
    <path d="M14.2 15.3l-.46-.78" />
    <path d="M21.2 17.6l-.9-.25" />
  </>
), 1.4)

// ─── Actions ──────────────────────────────────────────────────────────

export const PlusIcon = icon('PlusIcon', (
  <>
    <path d="M12 5v14" />
    <path d="M5 12h14" />
  </>
), 2)

export const PlayIcon = icon('PlayIcon', (
  <path d="M8.5 5.14v13.72a1 1 0 0 0 1.53.85l11.19-6.86a1 1 0 0 0 0-1.7L10.03 4.29a1 1 0 0 0-1.53.85z" fill="currentColor" stroke="none" />
), 0)

export const PauseIcon = icon('PauseIcon', (
  <>
    <rect x="6" y="4.5" width="4" height="15" rx="1.5" fill="currentColor" stroke="none" />
    <rect x="14" y="4.5" width="4" height="15" rx="1.5" fill="currentColor" stroke="none" />
  </>
), 0)

export const StopIcon = icon('StopIcon', (
  <rect x="5" y="5" width="14" height="14" rx="3" fill="currentColor" stroke="none" />
), 0)

export const CheckIcon = icon('CheckIcon', (
  <path d="M20 6L9 17l-5-5" />
), 2)

export const SearchIcon = icon('SearchIcon', (
  <>
    <circle cx="11" cy="11" r="7" />
    <path d="M21 21l-4.35-4.35" />
  </>
))

// ─── Common UI ────────────────────────────────────────────────────────

export const MenuIcon = icon('MenuIcon', (
  <>
    <path d="M4 6h16" />
    <path d="M4 12h16" />
    <path d="M4 18h16" />
  </>
), 2)

export const SettingsIcon = icon('SettingsIcon', (
  <>
    <circle cx="12" cy="12" r="3" />
    <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
  </>
), 1.4)

export const GlobeIcon = icon('GlobeIcon', (
  <>
    <circle cx="12" cy="12" r="10" />
    <path d="M2 12h20" />
    <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
  </>
))

export const ServerIcon = icon('ServerIcon', (
  <>
    <rect x="2" y="2" width="20" height="8" rx="2" />
    <rect x="2" y="14" width="20" height="8" rx="2" />
    <path d="M6 6h.01" />
    <path d="M6 18h.01" />
  </>
), 1.7)

export const MessageSquareIcon = icon('MessageSquareIcon', (
  <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
))

export const TrashIcon = icon('TrashIcon', (
  <>
    <path d="M3 6h18" />
    <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
    <path d="M10 11v6" />
    <path d="M14 11v6" />
  </>
))

export const Trash2Icon = TrashIcon

export const LayersIcon = icon('LayersIcon', (
  <>
    <path d="M12 2L2 7l10 5 10-5-10-5z" />
    <path d="M2 17l10 5 10-5" />
    <path d="M2 12l10 5 10-5" />
  </>
))

export const WebhookIcon = icon('WebhookIcon', (
  <>
    <path d="M18 16.98h1a2 2 0 0 0 1.74-2.99l-4-7a2 2 0 0 0-3.48 0l-4 7A2 2 0 0 0 10 16.98h1" />
    <path d="M10 9.01V9" />
    <path d="M14 9.01V9" />
    <path d="M12 16v3" />
  </>
), 1.6)

export const WalletIcon = icon('WalletIcon', (
  <>
    <path d="M21 12V7H5a2 2 0 0 1 0-4h14v4" />
    <path d="M3 5v14a2 2 0 0 0 2 2h16v-5" />
    <path d="M18 12a2 2 0 0 0 0 4h4v-4h-4z" />
  </>
))

export const TrendingUpIcon = icon('TrendingUpIcon', (
  <>
    <path d="M23 6L13.5 15.5 8.5 10.5 1 18" />
    <path d="M17 6h6v6" />
  </>
))

export const TrendingDownIcon = icon('TrendingDownIcon', (
  <>
    <path d="M23 18L13.5 8.5 8.5 13.5 1 6" />
    <path d="M17 18h6v-6" />
  </>
))

export const TrophyIcon = icon('TrophyIcon', (
  <>
    <path d="M6 9H4.5a2.5 2.5 0 0 1 0-5H6" />
    <path d="M18 9h1.5a2.5 2.5 0 0 0 0-5H18" />
    <path d="M4 22h16" />
    <path d="M10 14.66V17c0 .55-.47.98-.97 1.21C7.85 18.75 7 20.24 7 22" />
    <path d="M14 14.66V17c0 .55.47.98.97 1.21C16.15 18.75 17 20.24 17 22" />
    <path d="M18 2H6v7a6 6 0 0 0 12 0V2Z" />
  </>
), 1.5)

export const BellIcon = icon('BellIcon', (
  <>
    <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
    <path d="M13.73 21a2 2 0 0 1-3.46 0" />
  </>
))

export const ShieldIcon = icon('ShieldIcon', (
  <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
))

export const ShieldCheckIcon = icon('ShieldCheckIcon', (
  <>
    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
    <path d="M9 11.5l2 2 4-4" />
  </>
))

export const DollarSignIcon = icon('DollarSignIcon', (
  <>
    <path d="M12 1v22" />
    <path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" />
  </>
))

export const PhoneIcon = icon('PhoneIcon', (
  <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z" />
))

export const SendIcon = icon('SendIcon', (
  <>
    <path d="M22 2L11 13" />
    <path d="M22 2l-7 20-4-9-9-4 20-7z" />
  </>
))

export const DatabaseIcon = icon('DatabaseIcon', (
  <>
    <ellipse cx="12" cy="5" rx="9" ry="3" />
    <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3" />
    <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5" />
  </>
))

// ─── Telemetry / data ─────────────────────────────────────────────────

export const ListOrderedIcon = icon('ListOrderedIcon', (
  <>
    <path d="M10 6h11" />
    <path d="M10 12h11" />
    <path d="M10 18h11" />
    <path d="M4 6h1v4" />
    <path d="M4 10h2" />
    <path d="M6 18H4c0-1 2-2 2-3s-1-1.5-2-1" />
  </>
))

export const BarChart3Icon = icon('BarChart3Icon', (
  <>
    <path d="M3 20h18" />
    <path d="M7 20v-6" />
    <path d="M12 20V7" />
    <path d="M17 20v-4" />
  </>
))

export const AlertTriangleIcon = icon('AlertTriangleIcon', (
  <>
    <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
    <path d="M12 9v4" />
    <path d="M12 17h.01" />
  </>
))

export const ClockIcon = icon('ClockIcon', (
  <>
    <circle cx="12" cy="12" r="10" />
    <path d="M12 6v6l4 2" />
  </>
))

export const HistoryIcon = icon('HistoryIcon', (
  <>
    <path d="M3 12a9 9 0 1 0 3-6.7L3 8" />
    <path d="M3 3v5h5" />
    <path d="M12 7v5l4 2" />
  </>
))

export const RotateCcwIcon = icon('RotateCcwIcon', (
  <>
    <path d="M1 4v6h6" />
    <path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10" />
  </>
))

export const RefreshCwIcon = icon('RefreshCwIcon', (
  <>
    <path d="M23 4v6h-6" />
    <path d="M1 20v-6h6" />
    <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10" />
    <path d="M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
  </>
))

// ─── Prompt / code ────────────────────────────────────────────────────

export const CodeIcon = icon('CodeIcon', (
  <>
    <path d="M16 18l6-6-6-6" />
    <path d="M8 6L2 12l6 6" />
  </>
))

// ─── Files & media ────────────────────────────────────────────────────

export const ImageIcon = icon('ImageIcon', (
  <>
    <rect x="3" y="3" width="18" height="18" rx="2" />
    <circle cx="8.5" cy="8.5" r="1.5" />
    <path d="M21 15l-5-5L5 21" />
  </>
))

export const FileIcon = icon('FileIcon', (
  <>
    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
    <path d="M14 2v6h6" />
  </>
))

export const FolderIcon = icon('FolderIcon', (
  <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
))

export const DownloadIcon = icon('DownloadIcon', (
  <>
    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
    <path d="M7 10l5 5 5-5" />
    <path d="M12 15V3" />
  </>
))

export const UploadIcon = icon('UploadIcon', (
  <>
    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
    <path d="M17 8l-5-5-5 5" />
    <path d="M12 3v12" />
  </>
))

export const CopyIcon = icon('CopyIcon', (
  <>
    <rect x="9" y="9" width="13" height="13" rx="2" />
    <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
  </>
))

export const SaveIcon = icon('SaveIcon', (
  <>
    <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z" />
    <path d="M17 21v-8H7v8" />
    <path d="M7 3v5h8" />
  </>
))

// ─── Theme ────────────────────────────────────────────────────────────

export const SunIcon = icon('SunIcon', (
  <>
    <circle cx="12" cy="12" r="4" />
    <path d="M12 2v2" />
    <path d="M12 20v2" />
    <path d="M4.93 4.93l1.41 1.41" />
    <path d="M17.66 17.66l1.41 1.41" />
    <path d="M2 12h2" />
    <path d="M20 12h2" />
    <path d="M6.34 17.66l-1.41 1.41" />
    <path d="M19.07 4.93l-1.41 1.41" />
  </>
))

export const MoonIcon = icon('MoonIcon', (
  <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
))

// ─── Status & feedback ────────────────────────────────────────────────

export const CheckCircleIcon = icon('CheckCircleIcon', (
  <>
    <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
    <path d="M22 4L12 14.01 9 11.01" />
  </>
))

export const XCircleIcon = icon('XCircleIcon', (
  <>
    <circle cx="12" cy="12" r="10" />
    <path d="M15 9l-6 6" />
    <path d="M9 9l6 6" />
  </>
))

export const AlertCircleIcon = icon('AlertCircleIcon', (
  <>
    <circle cx="12" cy="12" r="10" />
    <path d="M12 8v4" />
    <path d="M12 16h.01" />
  </>
))

export const InfoIcon = icon('InfoIcon', (
  <>
    <circle cx="12" cy="12" r="10" />
    <path d="M12 16v-4" />
    <path d="M12 8h.01" />
  </>
))

export const HelpCircleIcon = icon('HelpCircleIcon', (
  <>
    <circle cx="12" cy="12" r="10" />
    <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" />
    <path d="M12 17h.01" />
  </>
))

// ─── Getting started / hero ───────────────────────────────────────────

export const SparklesIcon = icon('SparklesIcon', (
  <>
    <path d="M12 3l1.9 5.7a2 2 0 0 0 1.3 1.3L21 12l-5.8 1.9a2 2 0 0 0-1.3 1.3L12 21l-1.9-5.8a2 2 0 0 0-1.3-1.3L3 12l5.8-1.9a2 2 0 0 0 1.3-1.3z" />
    <path d="M19 3v4" />
    <path d="M21 5h-4" />
    <path d="M5 17v3" />
    <path d="M6.5 18.5h-3" />
  </>
), 1.5)

export const RocketIcon = icon('RocketIcon', (
  <>
    <path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09z" />
    <path d="M12 15l-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 0 1-4 2z" />
    <path d="M9 12H4s.55-3.03 2-4c1.62-1.08 5 0 5 0" />
    <path d="M12 15v5s3.03-.55 4-2c1.08-1.62 0-5 0-5" />
  </>
), 1.4)

// ─── New: editing & more ──────────────────────────────────────────────

export const EditIcon = icon('EditIcon', (
  <>
    <path d="M12 20h9" />
    <path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z" />
  </>
))

export const MoreHorizontalIcon = icon('MoreHorizontalIcon', (
  <>
    {dot(5, 12, 1)}
    {dot(12, 12, 1)}
    {dot(19, 12, 1)}
  </>
), 0)

export const MoreVerticalIcon = icon('MoreVerticalIcon', (
  <>
    {dot(12, 5, 1)}
    {dot(12, 12, 1)}
    {dot(12, 19, 1)}
  </>
), 0)

export const FilterIcon = icon('FilterIcon', (
  <path d="M22 3H2l8 9.46V19l4 2v-8.54L22 3z" />
))

export const SlidersIcon = icon('SlidersIcon', (
  <>
    <path d="M4 21v-7" />
    <path d="M4 10V3" />
    <path d="M12 21v-9" />
    <path d="M12 8V3" />
    <path d="M20 21v-5" />
    <path d="M20 12V3" />
    <path d="M1 14h6" />
    <path d="M9 8h6" />
    <path d="M17 16h6" />
  </>
))

export const BoxIcon = icon('BoxIcon', (
  <>
    <path d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z" />
    <path d="M3.27 6.96L12 12.01l8.73-5.05" />
    <path d="M12 22.08V12" />
  </>
))

export const GaugeIcon = icon('GaugeIcon', (
  <>
    <path d="M12 14l4-4" />
    <path d="M3.34 19a10 10 0 1 1 17.32 0" />
  </>
))

export const ExternalLinkIcon = icon('ExternalLinkIcon', (
  <>
    <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
    <path d="M15 3h6v6" />
    <path d="M10 14L21 3" />
  </>
))

export const CalendarIcon = icon('CalendarIcon', (
  <>
    <rect x="3" y="4" width="18" height="18" rx="2" />
    <path d="M16 2v4" />
    <path d="M8 2v4" />
    <path d="M3 10h18" />
  </>
))

export const LinkIcon = icon('LinkIcon', (
  <>
    <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
    <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
  </>
))

export const LayoutGridIcon = icon('LayoutGridIcon', (
  <>
    <rect x="3" y="3" width="7.5" height="7.5" rx="1.5" />
    <rect x="13.5" y="3" width="7.5" height="7.5" rx="1.5" />
    <rect x="3" y="13.5" width="7.5" height="7.5" rx="1.5" />
    <rect x="13.5" y="13.5" width="7.5" height="7.5" rx="1.5" />
  </>
))

export const HashIcon = icon('HashIcon', (
  <>
    <path d="M4 9h16" />
    <path d="M4 15h16" />
    <path d="M10 3L8 21" />
    <path d="M16 3l-2 18" />
  </>
))

export const CompassIcon = icon('CompassIcon', (
  <>
    <circle cx="12" cy="12" r="10" />
    <path d="M16.24 7.76l-2.12 6.36-6.36 2.12 2.12-6.36 6.36-2.12z" />
  </>
))

export const BookmarkIcon = icon('BookmarkIcon', (
  <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z" />
))

export const CommandIcon = icon('CommandIcon', (
  <path d="M18 3a3 3 0 0 0-3 3v12a3 3 0 0 0 3 3 3 3 0 0 0 3-3 3 3 0 0 0-3-3H6a3 3 0 0 0-3 3 3 3 0 0 0 3 3 3 3 0 0 0 3-3V6a3 3 0 0 0-3-3 3 3 0 0 0-3 3 3 3 0 0 0 3 3h12a3 3 0 0 0 3-3 3 3 0 0 0-3-3z" />
), 1.5)

export const StarIcon = icon('StarIcon', (
  <path d="M12 2l3.09 6.26L22 9.27l-5 4.87L18.18 21 12 17.77 5.82 21 7 14.14 2 9.27l6.91-1.01L12 2z" />
), 1.5)

export const WindIcon = icon('WindIcon', (
  <>
    <path d="M17.7 7.7a2.5 2.5 0 1 1 1.8 4.3H2" />
    <path d="M9.6 4.6A2 2 0 1 1 11 8H2" />
    <path d="M12.6 19.4A2 2 0 1 0 14 16H2" />
  </>
))

export const ZapIcon = icon('ZapIcon', (
  <path d="M13 2L3 14h7l-1 8 10-12h-7l1-8z" />
), 1.5)

export const RouteIcon = icon('RouteIcon', (
  <>
    <circle cx="6" cy="19" r="3" />
    <path d="M9 19h8.5a3.5 3.5 0 0 0 0-7h-11a3.5 3.5 0 0 1 0-7H15" />
    <circle cx="18" cy="5" r="3" />
  </>
))

export const CloudIcon = icon('CloudIcon', (
  <path d="M17.5 19H9a7 7 0 1 1 6.71-9h1.79a4.5 4.5 0 1 1 0 9z" />
))

export const SmileIcon = icon('SmileIcon', (
  <>
    <circle cx="12" cy="12" r="10" />
    <path d="M8 14.5s1.5 2 4 2 4-2 4-2" />
    <path d="M9 9h.01" />
    <path d="M15 9h.01" />
  </>
))

export const AsteriskIcon = icon('AsteriskIcon', (
  <>
    <path d="M12 3v18" />
    <path d="M4.2 7.5l15.6 9" />
    <path d="M19.8 7.5L4.2 16.5" />
  </>
))

export const AtomIcon = icon('AtomIcon', (
  <>
    <circle cx="12" cy="12" r="1" fill="currentColor" />
    <path d="M20.2 20.2c2.04-2.03.02-7.36-4.5-11.9-4.54-4.52-9.87-6.54-11.9-4.5-2.04 2.03-.02 7.36 4.5 11.9 4.54 4.52 9.87 6.54 11.9 4.5Z" />
    <path d="M15.7 15.7c4.52-4.54 6.54-9.87 4.5-11.9-2.03-2.04-7.36-.02-11.9 4.5-4.52 4.54-6.54 9.87-4.5 11.9 2.03 2.04 7.36.02 11.9-4.5Z" />
  </>
), 1.4)

export const PercentIcon = icon('PercentIcon', (
  <>
    <path d="M19 5L5 19" />
    <circle cx="6.5" cy="6.5" r="2.5" />
    <circle cx="17.5" cy="17.5" r="2.5" />
  </>
))

export const Menu2Icon = icon('Menu2Icon', (
  <>
    <path d="M4 6h16" />
    <path d="M4 12h10" />
    <path d="M4 18h16" />
  </>
), 2)

export const PanelLeftIcon = icon('PanelLeftIcon', (
  <>
    <rect x="3" y="3" width="18" height="18" rx="2" />
    <path d="M9 3v18" />
  </>
))

// ─── Logo — neural "A" sigil with violet gradient (brand mark) ────────

export const LogoIcon = ({ className, size = 28 }: IconProps) => {
  const uid = React.useId().replace(/[^a-zA-Z0-9]/g, '')
  const ring = `logo-ring-${uid}`
  const glyph = `logo-glyph-${uid}`
  return (
    <svg className={className} width={size} height={size} viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <defs>
        <linearGradient id={ring} x1="3" y1="3" x2="21" y2="21">
          <stop stopColor="#a78bfa" />
          <stop offset="1" stopColor="#7c3aed" />
        </linearGradient>
        <linearGradient id={glyph} x1="7" y1="6.5" x2="17" y2="16.5">
          <stop stopColor="#a78bfa" />
          <stop offset="1" stopColor="#7c3aed" />
        </linearGradient>
      </defs>
      <ellipse cx="12" cy="12" rx="9" ry="3.4" opacity="0.45" transform="rotate(-22 12 12)" stroke={`url(#${ring})`} strokeWidth="1.2" />
      <path d="M7 16.5 12 6.5l5 10" stroke={glyph ? `url(#${glyph})` : undefined} strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M9.2 13h5.6" opacity="0.85" stroke={`url(#${glyph})`} strokeWidth="1.4" strokeLinecap="round" />
      <circle cx="12" cy="6.2" r="1.5" fill="#a78bfa" />
      <circle cx="12" cy="6.2" r="3" opacity="0.35" fill="#a78bfa" />
      <circle cx="20.2" cy="9" r="0.9" fill="#a78bfa" />
      <circle cx="3.8" cy="15" r="0.9" fill="#a78bfa" />
    </svg>
  )
}

// ─── Dynamic icon lookup ──────────────────────────────────────────────

interface DynamicIconProps extends IconProps {
  name: string
}

const iconMap: Record<string, React.FC<IconProps>> = {
  dashboard: DashboardIcon,
  users: UsersIcon,
  bot: BotIcon,
  workflow: WorkflowIcon,
  brain: BrainIcon,
  wrench: WrenchIcon,
  cpu: CpuIcon,
  filetext: FileTextIcon,
  key: KeyIcon,
  archive: ArchiveIcon,
  gitbranch: GitBranchIcon,
  activity: ActivityIcon,
  logout: LogOutIcon,
  chevronleft: ChevronLeftIcon,
  chevronright: ChevronRightIcon,
  chevronup: ChevronUpIcon,
  chevrondown: ChevronDownIcon,
  arrowleft: ArrowLeftIcon,
  arrowright: ArrowRightIcon,
  arrowupright: ArrowUpRightIcon,
  x: XIcon,
  login: LogInIcon,
  mail: MailIcon,
  lock: LockIcon,
  eye: EyeIcon,
  eyeoff: EyeOffIcon,
  user: UserIcon,
  userplus: UserPlusIcon,
  userminus: UserMinusIcon,
  usercog: UserCogIcon,
  plus: PlusIcon,
  play: PlayIcon,
  pause: PauseIcon,
  stop: StopIcon,
  check: CheckIcon,
  search: SearchIcon,
  menu: MenuIcon,
  menu2: Menu2Icon,
  settings: SettingsIcon,
  globe: GlobeIcon,
  server: ServerIcon,
  messagesquare: MessageSquareIcon,
  trash: TrashIcon,
  trash2: TrashIcon,
  layers: LayersIcon,
  webhook: WebhookIcon,
  wallet: WalletIcon,
  trendingup: TrendingUpIcon,
  trendingdown: TrendingDownIcon,
  trophy: TrophyIcon,
  bell: BellIcon,
  shield: ShieldIcon,
  shieldcheck: ShieldCheckIcon,
  dollarsign: DollarSignIcon,
  phone: PhoneIcon,
  send: SendIcon,
  database: DatabaseIcon,
  listordered: ListOrderedIcon,
  barchart3: BarChart3Icon,
  alerttriangle: AlertTriangleIcon,
  clock: ClockIcon,
  history: HistoryIcon,
  rotateccw: RotateCcwIcon,
  refreshcw: RefreshCwIcon,
  code: CodeIcon,
  image: ImageIcon,
  file: FileIcon,
  folder: FolderIcon,
  download: DownloadIcon,
  upload: UploadIcon,
  copy: CopyIcon,
  save: SaveIcon,
  logo: LogoIcon,
  sun: SunIcon,
  moon: MoonIcon,
  checkcircle: CheckCircleIcon,
  xcircle: XCircleIcon,
  alertcircle: AlertCircleIcon,
  info: InfoIcon,
  helpcircle: HelpCircleIcon,
  sparkles: SparklesIcon,
  rocket: RocketIcon,
  edit: EditIcon,
  morehorizontal: MoreHorizontalIcon,
  morevertical: MoreVerticalIcon,
  filter: FilterIcon,
  sliders: SlidersIcon,
  box: BoxIcon,
  gauge: GaugeIcon,
  externallink: ExternalLinkIcon,
  calendar: CalendarIcon,
  link: LinkIcon,
  layoutgrid: LayoutGridIcon,
  hash: HashIcon,
  compass: CompassIcon,
  bookmark: BookmarkIcon,
  command: CommandIcon,
  star: StarIcon,
  wind: WindIcon,
  zap: ZapIcon,
  route: RouteIcon,
  cloud: CloudIcon,
  smile: SmileIcon,
  asterisk: AsteriskIcon,
  atom: AtomIcon,
  percent: PercentIcon,
  panelleft: PanelLeftIcon,
}

export const Icon = ({ name, className, size = 18, strokeWidth, style }: DynamicIconProps) => {
  const IconComponent = iconMap[name.toLowerCase().replace(/[\s-]/g, '')]
  if (!IconComponent) return null
  return <IconComponent className={className} size={size} strokeWidth={strokeWidth} style={style} />
}

export default Icon
