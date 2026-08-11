export interface AppConfig {
  pageTitle: string;
  pageDescription: string;
  companyName: string;

  supportsChatInput: boolean;
  supportsVideoInput: boolean;
  supportsScreenShare: boolean;
  isPreConnectBufferEnabled: boolean;

  logo: string;
  startButtonText: string;
  accent?: string;
  logoDark?: string;
  accentDark?: string;

  audioVisualizerType?: 'bar' | 'wave' | 'grid' | 'radial' | 'aura';
  audioVisualizerColor?: `#${string}`;
  audioVisualizerColorDark?: `#${string}`;
  audioVisualizerColorShift?: number;
  audioVisualizerBarCount?: number;
  audioVisualizerGridRowCount?: number;
  audioVisualizerGridColumnCount?: number;
  audioVisualizerRadialBarCount?: number;
  audioVisualizerRadialRadius?: number;
  audioVisualizerWaveLineWidth?: number;

  // agent dispatch configuration
  agentName?: string;

  // LiveKit Cloud Sandbox configuration
  sandboxId?: string;
}

export const APP_CONFIG_DEFAULTS: AppConfig = {
  companyName: 'Saathi Swasthya',
  pageTitle: 'Saathi Swasthya - AI Health Navigator',
  pageDescription: 'A multilingual Voice-First Health Navigation and Triage Assistant for Bharat.',

  supportsChatInput: true,
  supportsVideoInput: true,
  supportsScreenShare: true,
  isPreConnectBufferEnabled: true,

  logo: '/saathi-logo.svg',
  accent: '#0d9488', // Calming Teal 600
  logoDark: '/saathi-logo.svg',
  accentDark: '#2dd4bf', // Teal 400
  startButtonText: 'Speak with Saathi',

  // Audio visualization - Aura (shader-based aurora effect)
  audioVisualizerType: 'aura',
  audioVisualizerColor: '#0d9488', // Teal 600
  audioVisualizerColorDark: '#2dd4bf', // Teal 400
  audioVisualizerColorShift: 0.3,

  // agent dispatch configuration
  agentName: process.env.AGENT_NAME ?? undefined,

  // LiveKit Cloud Sandbox configuration
  sandboxId: undefined,
};
