export interface EspStatus {
  status?: string;
  ip?: string;
  feeding?: boolean;
  motor_running?: boolean;
  [k: string]: unknown;
}

export type FeederMode = 'schedule' | 'interval';

export interface FeederStatus {
  ip: string;
  port: number;
  mode: FeederMode;
  times: string[];
  interval: number;
  duration: number;
  running: boolean;
  next: string;
  last: string;
  esp: EspStatus | null;
}

export interface ConfigPayload {
  ip: string;
  port: number;
  mode: FeederMode;
  times: string;
  interval: number;
  duration: number;
}
