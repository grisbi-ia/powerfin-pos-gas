/** Shared types for dashboard components. */

export type Period = 'daily' | 'monthly' | 'annual';

export interface ChipItem {
  value: string;
  label: string;
  sublabel?: string;
  isToday?: boolean;
  isPast?: boolean;
}
