import React, { useState, useEffect } from 'react';
import { SolarSystem } from './components/SolarSystem';
import { PLANET_MAP } from './components/Planet';
import { useCamera } from './hooks/useCamera';
import { Globe, Activity, Calendar, Github, Brain, ArrowLeft } from 'lucide-react';
import { AnimatePresence, motion } from 'framer-motion';

const icons: Record<string, React.ReactNode> = {
  earth: <Globe className="w-5 h-5 text-blue-400" />,
  mars: <Activity className="w-5 h-5 text-red-400" />,
  europa: <Github className="w-5 h-5 text-cyan-400" />,
  saturn: <Calendar className="w-5 h-5 text-amber-400" />,
  jupiter: <Brain className="w-5 h-5 text-purple-400" />,
};

const planetDescriptions: Record<string, string> = {
  earth: "KIRA's core chat layer. General conversational queries, speech recognition, and everyday interactions route directly through Earth's atmosphere.",
  mars: "System performance and productivity tracker. Mars' surface weather pattern dynamically reflects work state. Game or browser distractions trigger planetary-scale storms.",
  europa: "Technical directory search and GitHub indexing. Hexagonal surface grids fracture and rise as icy pillars of repository data representing query results.",
  saturn: "Schedule planner and Google Calendar synchronizer. Individual ring segments partition hours, while calendar events manifest as glowing dust particles orbiting Saturn.",
  jupiter: "Deep reasoning and Gemini fallback engine. Serving as KIRA's most imposing and distant planet, Jupiter resolves complex instructions that exceed local model capacities.",
};

const App: React.FC = () => {
  const {
    activePlanetId,
    cameraState,
    focusOnPlanet,
    resetToOverview,
    updateCamera,
    currentX,
    currentY,
    currentScale,
  } = useCamera();

  const [time, setTime] = useState(new Date().toLocaleTimeString());

  useEffect(() => {
    const timer = setInterval(() => {
      setTime(new Date().toLocaleTimeString());
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  const activePlanet = activePlanetId ? PLANET_MAP[activePlanetId] : null;

  return (
    <div className="relative w-full h-full text-slate-100 font-sans select-none overflow-hidden">
      {/* 1. Canvas Space Scene */}
      <div className="absolute inset-0 z-0">
        <SolarSystem
          activePlanetId={activePlanetId}
          focusOnPlanet={focusOnPlanet}
          resetToOverview={resetToOverview}
          updateCamera={updateCamera}
          currentX={currentX}
          currentY={currentY}
          currentScale={currentScale}
        />
      </div>

      {/* 2. Top Header Panel */}
      <header className="absolute top-6 left-6 right-6 z-10 flex justify-between items-center pointer-events-none">
        <div className="glass-panel px-6 py-4 flex items-center gap-4 pointer-events-auto">
          <div className="relative flex h-3 w-3">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-3 w-3 bg-emerald-500"></span>
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-wide bg-gradient-to-r from-slate-100 to-slate-400 bg-clip-text text-transparent">
              KIRA
            </h1>
            <p className="text-xs text-slate-400 font-medium">Solar System UI — Phase 2</p>
          </div>
        </div>

        <div className="glass-panel px-4 py-3 text-xs font-mono text-slate-400 pointer-events-auto flex items-center gap-2">
          <span>SYSTEM TIME:</span>
          <span className="text-amber-400 font-semibold">{time}</span>
        </div>
      </header>

      {/* 3. Floating Navigation Return Controls */}
      <AnimatePresence>
        {activePlanetId && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 20 }}
            transition={{ type: 'spring', stiffness: 300, damping: 25 }}
            className="absolute left-6 top-28 z-10 pointer-events-auto"
          >
            <button
              onClick={resetToOverview}
              className="glass-panel px-5 py-3.5 flex items-center gap-3 text-sm font-semibold tracking-wide text-slate-200 hover:text-white bg-slate-900/60 border border-white/10 hover:border-white/20 hover:bg-slate-900/80 active:scale-95 transition-all"
            >
              <ArrowLeft className="w-4 h-4 text-amber-400" />
              <span>RETURN TO OVERVIEW</span>
              <span className="text-[10px] font-mono bg-white/10 px-1.5 py-0.5 rounded text-slate-400">ESC</span>
            </button>
          </motion.div>
        )}
      </AnimatePresence>

      {/* 4. Right Sidebar Widget */}
      <aside className="absolute right-6 top-28 bottom-6 w-80 z-10 flex flex-col gap-4 pointer-events-none">
        <div className="glass-panel p-5 flex flex-col gap-4 pointer-events-auto h-full overflow-y-auto">
          <AnimatePresence mode="wait">
            {!activePlanet ? (
              // Overview Sidebar
              <motion.div
                key="overview-sidebar"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 20 }}
                transition={{ duration: 0.2 }}
                className="flex flex-col gap-4 h-full"
              >
                <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-widest border-b border-white/5 pb-2">
                  System Overview
                </h2>
                <p className="text-xs text-slate-400 leading-relaxed">
                  Select a planetary system to route instructions or inspect dedicated server functions.
                </p>

                <div className="flex flex-col gap-2.5 mt-2">
                  {Object.values(PLANET_MAP).map((planet) => (
                    <button
                      key={planet.id}
                      onClick={() => focusOnPlanet(planet.id)}
                      className="flex items-center gap-3 p-3 text-left rounded-lg bg-white/[0.02] border border-white/[0.03] transition-all hover:bg-white/[0.06] hover:border-white/10 group active:scale-[0.98]"
                    >
                      <div className="p-2 rounded bg-white/[0.04] group-hover:bg-white/[0.08] transition-all">
                        {icons[planet.id]}
                      </div>
                      <div className="flex-1 min-w-0">
                        <h3 className="text-sm font-semibold text-slate-200 group-hover:text-amber-400 transition-colors">
                          {planet.name}
                        </h3>
                        <p className="text-xs text-slate-400 truncate">{planet.service}</p>
                      </div>
                    </button>
                  ))}
                </div>

                <div className="mt-auto border-t border-white/5 pt-3">
                  <div className="text-[11px] text-slate-400 leading-relaxed">
                    <span className="text-amber-400 font-semibold">Ready:</span> Click on a planet directly on the Canvas or select it from the menu to transition camera.
                  </div>
                </div>
              </motion.div>
            ) : (
              // Focused Planet Sidebar
              <motion.div
                key={`planet-sidebar-${activePlanet.id}`}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                transition={{ duration: 0.2 }}
                className="flex flex-col gap-4 h-full"
              >
                <div className="flex items-center gap-3 border-b border-white/5 pb-3">
                  <div className="p-2 rounded bg-white/[0.05]">
                    {icons[activePlanet.id]}
                  </div>
                  <div>
                    <h2 className="text-base font-bold text-slate-100 tracking-wide">
                      {activePlanet.name.toUpperCase()}
                    </h2>
                    <p className="text-[11px] text-slate-400 tracking-wider uppercase">
                      {activePlanet.service}
                    </p>
                  </div>
                </div>

                <div className="flex flex-col gap-3">
                  <div className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                    System State
                  </div>
                  <div className="text-xs text-slate-300 leading-relaxed">
                    {planetDescriptions[activePlanet.id]}
                  </div>
                </div>

                <div className="flex flex-col gap-3 mt-4">
                  <div className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                    Technical Specifications
                  </div>
                  <div className="grid grid-cols-2 gap-2 font-mono text-[10px] text-slate-400 bg-white/[0.01] p-3 rounded-lg border border-white/[0.03]">
                    <div>ORBIT SPEED:</div>
                    <div className="text-slate-200 text-right">{activePlanet.orbitSpeed} rad/f</div>
                    <div>RADIUS:</div>
                    <div className="text-slate-200 text-right">{activePlanet.orbitRadius} px</div>
                    <div>SIZE:</div>
                    <div className="text-slate-200 text-right">{activePlanet.size} px</div>
                    <div>CAMERA STATE:</div>
                    <div className="text-amber-400 text-right font-semibold">{cameraState}</div>
                  </div>
                </div>

                <div className="mt-auto border-t border-white/5 pt-3 flex flex-col gap-2">
                  <div className="text-[11px] text-slate-400 leading-relaxed">
                    Text-to-speech interaction layers are locked until Phase 3 (Voice Input pipeline integration).
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </aside>

      {/* 5. Left Instructions Panel for User */}
      <div className="absolute left-6 bottom-6 w-80 z-10 pointer-events-none">
        <div className="glass-panel p-5 flex flex-col gap-3 pointer-events-auto">
          <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-widest border-b border-white/5 pb-2">
            Local Setup
          </h2>
          <p className="text-xs text-slate-400 leading-relaxed">
            Execute these commands in the <code className="bg-white/10 px-1 py-0.5 rounded text-amber-300">frontend</code> directory to install packages and start the dev server:
          </p>
          <div className="font-mono text-xs bg-slate-950/80 p-3 rounded-lg border border-white/5 flex flex-col gap-1.5 text-emerald-400 overflow-x-auto">
            <div># Install packages</div>
            <div className="text-slate-200">npm install</div>
            <div># Run dev server</div>
            <div className="text-slate-200">npm run dev</div>
            <div># Build to production</div>
            <div className="text-slate-200">npm run build</div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default App;
