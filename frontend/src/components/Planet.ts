export interface PlanetConfig {
  id: string;
  name: string;
  service: string;
  baseColor: string;
  accentColor: string;
  orbitRadius: number; // Distances from Sun in pixels (scale factor applied in rendering)
  orbitSpeed: number; // Angular speed coefficient
  size: number; // Radius of the planet circle in pixels
  rotationSpeed: number; // Speed of surface/pattern rotation
}

export const PLANET_MAP: Record<string, PlanetConfig> = {
  earth: {
    id: 'earth',
    name: 'Earth',
    service: 'General conversation',
    baseColor: '#2b8a3e', // Lush Green
    accentColor: '#1971c2', // Deep Blue
    orbitRadius: 160,
    orbitSpeed: 0.008,
    size: 20,
    rotationSpeed: 0.005,
  },
  mars: {
    id: 'mars',
    name: 'Mars',
    service: 'Productivity monitor',
    baseColor: '#e03131', // Crimson Red
    accentColor: '#fd7e14', // Fiery Orange
    orbitRadius: 230,
    orbitSpeed: 0.012,
    size: 15,
    rotationSpeed: 0.008,
  },
  europa: {
    id: 'europa',
    name: 'Europa',
    service: 'GitHub search',
    baseColor: '#1098ad', // Icy Turquoise
    accentColor: '#e7f5ff', // Frost White
    orbitRadius: 310,
    orbitSpeed: 0.009,
    size: 12,
    rotationSpeed: 0.003,
  },
  saturn: {
    id: 'saturn',
    name: 'Saturn',
    service: 'Google Calendar',
    baseColor: '#e9c46a', // Sand Gold
    accentColor: '#f4a261', // Soft Beige
    orbitRadius: 400,
    orbitSpeed: 0.004,
    size: 24,
    rotationSpeed: 0.002,
  },
  jupiter: {
    id: 'jupiter',
    name: 'Jupiter',
    service: 'Gemini fallback',
    baseColor: '#d946ef', // Rich Purple (Gemini vibe mixed with imposing scale)
    accentColor: '#e67700', // Terracotta Orange bands
    orbitRadius: 500,
    orbitSpeed: 0.002,
    size: 38,
    rotationSpeed: 0.001,
  },
};
