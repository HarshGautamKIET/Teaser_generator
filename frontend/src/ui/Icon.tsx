import { createElement } from "react";
import {
  ArrowLeft,
  ArrowUpDown,
  ChartNoAxesColumn,
  ChartPie,
  Check,
  ChevronRight,
  Clapperboard,
  Clock,
  Cpu,
  Download,
  Eye,
  EyeOff,
  Film,
  History,
  Layers,
  LayoutGrid,
  Link,
  LogOut,
  Mail,
  Plus,
  RefreshCw,
  RotateCcw,
  Settings,
  Sparkles,
  Target,
  Trash2,
  TriangleAlert,
  Upload,
  Users,
  Video,
  X,
} from "lucide";

/**
 * Oripio's icon set is Lucide — 2px stroke, round cap and join, monochrome,
 * inheriting currentColor (see design-system/readme.md → ICONOGRAPHY).
 *
 * Only the glyphs this app actually uses are imported, so the bundle carries
 * those rather than Lucide's full set. Registering a name here is a one-line
 * change; misspelling one at a call site is a compile error.
 */
const ICONS = {
  "arrow-left": ArrowLeft,
  "arrow-up-down": ArrowUpDown,
  "chart-no-axes-column": ChartNoAxesColumn,
  "chart-pie": ChartPie,
  check: Check,
  "chevron-right": ChevronRight,
  clapperboard: Clapperboard,
  clock: Clock,
  cpu: Cpu,
  download: Download,
  eye: Eye,
  "eye-off": EyeOff,
  film: Film,
  history: History,
  layers: Layers,
  "layout-grid": LayoutGrid,
  link: Link,
  "log-out": LogOut,
  mail: Mail,
  plus: Plus,
  "refresh-cw": RefreshCw,
  "rotate-ccw": RotateCcw,
  settings: Settings,
  sparkles: Sparkles,
  target: Target,
  "trash-2": Trash2,
  "triangle-alert": TriangleAlert,
  upload: Upload,
  users: Users,
  video: Video,
  x: X,
} as const;

export type IconName = keyof typeof ICONS;

interface Props {
  name: IconName;
  /** 16–17 in the chrome, 14–15 inside a 28px icon tile. */
  size?: number;
  strokeWidth?: number;
}

export default function Icon({ name, size = 16, strokeWidth = 2 }: Props) {
  return (
    <svg
      className="icon"
      aria-hidden="true"
      xmlns="http://www.w3.org/2000/svg"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {ICONS[name].map(([tag, attrs], index) =>
        createElement(tag, { key: index, ...attrs }),
      )}
    </svg>
  );
}
