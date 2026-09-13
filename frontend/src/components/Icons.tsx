/** Harici ikon paketi kullanmamak icin projeye gomulu SVG ikonlar. */

type Props = { className?: string };

const base = "h-5 w-5";

export function PawIcon({ className = base }: Props) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className={className} aria-hidden="true">
      <ellipse cx="8" cy="7" rx="2.1" ry="2.8" />
      <ellipse cx="16" cy="7" rx="2.1" ry="2.8" />
      <ellipse cx="4.4" cy="12.4" rx="1.9" ry="2.4" />
      <ellipse cx="19.6" cy="12.4" rx="1.9" ry="2.4" />
      <path d="M12 12.6c2.9 0 5.6 2.4 5.6 4.9 0 1.9-1.5 3-3.4 3-1 0-1.6-.4-2.2-.4s-1.2.4-2.2.4c-1.9 0-3.4-1.1-3.4-3 0-2.5 2.7-4.9 5.6-4.9Z" />
    </svg>
  );
}

export function SendIcon({ className = base }: Props) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
      strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true">
      <path d="M22 2 11 13" />
      <path d="M22 2 15 22l-4-9-9-4 20-7Z" />
    </svg>
  );
}

export function AlertIcon({ className = base }: Props) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
      strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true">
      <path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z" />
      <path d="M12 9v4" />
      <path d="M12 17h.01" />
    </svg>
  );
}

export function InfoIcon({ className = base }: Props) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
      strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true">
      <circle cx="12" cy="12" r="10" />
      <path d="M12 16v-4" />
      <path d="M12 8h.01" />
    </svg>
  );
}

export function ChevronIcon({ className = base }: Props) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
      strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true">
      <path d="m6 9 6 6 6-6" />
    </svg>
  );
}

export function SparkIcon({ className = base }: Props) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className={className} aria-hidden="true">
      <path d="M12 2.5 13.9 9l6.6 1.9-6.6 1.9L12 19.4 10.1 12.8 3.5 10.9 10.1 9 12 2.5Z" />
      <path d="M19 15.5l.8 2.7 2.7.8-2.7.8-.8 2.7-.8-2.7-2.7-.8 2.7-.8.8-2.7Z" opacity=".7" />
    </svg>
  );
}

export function ChartIcon({ className = base }: Props) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
      strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true">
      <path d="M3 3v16a2 2 0 0 0 2 2h16" />
      <rect x="7" y="12" width="3" height="6" rx="1" fill="currentColor" stroke="none" />
      <rect x="12.5" y="8" width="3" height="10" rx="1" fill="currentColor" stroke="none" />
      <rect x="18" y="4.5" width="3" height="13.5" rx="1" fill="currentColor" stroke="none" />
    </svg>
  );
}

export function CatIcon({ className = base }: Props) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"
      strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true">
      <path d="M4 4.5 7 8.8a7.6 7.6 0 0 1 10 0L20 4.5V15a7 7 0 0 1-16 0V4.5Z" />
      <path d="M9 12.5h.01M15 12.5h.01" />
      <path d="M12 15.5v1.2M10.4 17.6h3.2" />
    </svg>
  );
}

export function DogIcon({ className = base }: Props) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"
      strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true">
      <path d="M5.5 4.2c1.8-.6 3 .6 3.4 2.2a7.4 7.4 0 0 1 6.2 0c.4-1.6 1.6-2.8 3.4-2.2 1.4.5 1.6 2.4 1.2 4.3A7.3 7.3 0 0 1 20 11a8 8 0 0 1-16 0c0-.9.2-1.7.5-2.5-.4-1.9-.2-3.8 1-4.3Z" />
      <path d="M9.5 11h.01M14.5 11h.01" />
      <path d="M12 13.6v1.1M10.4 15.8h3.2" />
    </svg>
  );
}

export function DatabaseIcon({ className = base }: Props) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
      strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true">
      <ellipse cx="12" cy="5.5" rx="8" ry="3.2" />
      <path d="M4 5.5v13c0 1.8 3.6 3.2 8 3.2s8-1.4 8-3.2v-13" />
      <path d="M4 12c0 1.8 3.6 3.2 8 3.2s8-1.4 8-3.2" />
    </svg>
  );
}
