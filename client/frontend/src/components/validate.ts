import type { FeederMode } from '../api/types';

export interface ScheduleFormValues {
  ip: string;
  port: string;
  mode: FeederMode;
  times: string[] | string;
  interval: string;
  duration: string;
}

const TIME_RE = /^([01]?\d|2[0-3]):[0-5]\d$/;

function timesList(v: string[] | string): string[] {
  if (Array.isArray(v)) return v.map((s) => s.trim()).filter(Boolean);
  return v.split(',').map((s) => s.trim()).filter(Boolean);
}

export function validateSchedule(v: ScheduleFormValues): string | null {
  if (!v.ip.trim()) return 'ESP32 IP is required';
  const port = Number(v.port);
  if (!Number.isInteger(port) || port < 1 || port > 65535) return 'Port must be 1–65535';
  const duration = Number(v.duration);
  if (!Number.isFinite(duration) || duration <= 0) return 'Motor seconds must be > 0';
  if (v.mode === 'schedule') {
    const parts = timesList(v.times);
    if (parts.length === 0) return 'Add at least one feed time';
    for (const p of parts) if (!TIME_RE.test(p)) return `Bad time ${p}: use HH:MM 24h`;
  } else {
    const interval = Number(v.interval);
    if (!Number.isFinite(interval) || interval <= 0) return 'Repeat seconds must be > 0';
    if (duration >= interval) return 'Motor seconds must be shorter than repeat interval';
  }
  return null;
}
