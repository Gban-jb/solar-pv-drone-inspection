import {useEffect, useRef, useState} from 'react';
import {Pause, Play} from 'lucide-react';
import type {mountSolarHero} from './solarHeroScene';

export function SolarHero() {
  const stage = useRef<HTMLDivElement>(null);
  const controller = useRef<ReturnType<typeof mountSolarHero>>();
  const [ready, setReady] = useState(false);
  const [paused, setPaused] = useState(false);

  useEffect(() => {
    const host = stage.current;
    if (!host) return;
    let cancelled = false;
    void import('./solarHeroScene').then(({mountSolarHero: mount}) => {
      if (!cancelled) controller.current = mount(host, setReady);
    }).catch(() => {
      if (!cancelled) setReady(false);
    });
    return () => {
      cancelled = true;
      controller.current?.dispose();
      controller.current = undefined;
    };
  }, []);

  function toggleMotion() {
    controller.current?.setPaused(!paused);
    setPaused(!paused);
  }

  return <figure className="solar-hero">
    <div className="solar-hero-visual">
      <div className="solar-hero-halo" aria-hidden="true"/>
      <div className="solar-hero-contact" aria-hidden="true"/>
      <img className="solar-hero-poster"
        src={import.meta.env.BASE_URL + 'models/solar-array-still.webp'}
        alt="" width="697" height="580" fetchPriority="high"/>
      <div className="solar-hero-canvas" ref={stage} data-ready={ready} aria-hidden="true"/>
    </div>
    <figcaption className="solar-hero-label">
      <span>Illustrative drone scan</span>
      {ready && <button type="button" className="hero-motion-button"
        onClick={toggleMotion} aria-label={paused ? 'Play drone animation' : 'Pause drone animation'}
        title={paused ? 'Play drone animation' : 'Pause drone animation'}>
        {paused ? <Play size={13}/> : <Pause size={13}/>}
      </button>}
    </figcaption>
  </figure>;
}
