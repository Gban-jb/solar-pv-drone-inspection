import {useState} from 'react';
import {Link} from 'react-router-dom';
import {ArrowDown, ArrowUpRight, Boxes, Crosshair, Download, UploadCloud} from 'lucide-react';
import {SolarHero} from './SolarHero';

const steps = [
  {title:'Import flight imagery', copy:'Bring RGB and thermal captures together and check which files are ready to inspect.', icon:UploadCloud},
  {title:'Mark panels', copy:'Draw a panel or row boundary and give it an ID you can find again.', icon:Boxes},
  {title:'Compare temperatures', copy:'Compare a warm region with its neighbors when the source contains temperature data.', icon:Crosshair},
  {title:'Share the evidence', copy:'Save what you found and export it with its source, review status, and notes.', icon:Download},
];

export function Brand() {
  return <Link to="/" className="brand"><img className="brand-symbol" src={import.meta.env.BASE_URL + 'brand/solar-mark.png'} width="128" height="128" alt=""/>
    <span><strong>Solar PV Inspection</strong><small>Alabama A&amp;M University</small></span></Link>;
}

export default function Home({destination}: {destination: string}) {
  const [thermal,setThermal]=useState(false);
  return <div className="site">
    <header className="site-header"><div className="site-width">
      <Brand/><nav aria-label="Project"><a href="#workflow">Workflow</a><a href="#research">Research</a>
      <Link to={destination} className="button primary">Open workspace <ArrowUpRight size={16}/></Link></nav>
    </div></header>
    <main>
      <section className="hero" aria-labelledby="hero-title"><div className="site-width hero-grid">
        <div className="hero-copy"><p className="eyebrow"><span/> AAMU · SOLAR PV RESEARCH</p>
          <h1 id="hero-title">A closer look<br/>at solar panels.</h1>
          <p className="hero-description">Use drone images to spot unusual heat, trace it to a panel, and record the evidence for inspection.</p>
          <div className="hero-actions"><Link to={destination} className="button primary">Open Inspection Dashboard <ArrowUpRight size={19}/></Link>
          <a href="#workflow" className="hero-link">See how it works <ArrowDown size={15}/></a></div>
        </div>
        <SolarHero/>
      </div></section>
      <section className="site-width workflow-section" id="workflow">
        <div className="section-intro"><p className="eyebrow">THE INSPECTION WORKFLOW</p><h2>From flight to finding.</h2></div>
        <div className="steps">{steps.map(({title,copy,icon:Icon})=><article key={title}><Icon size={24}/><h3>{title}</h3><p>{copy}</p></article>)}</div>
      </section>
      <section className="research-section" id="research"><div className="site-width research-grid">
        <div><p className="eyebrow">RESEARCH PROTOTYPE</p><h2>One scene.<br/>Two ways to look.</h2>
          <p>Visible imagery shows where to look. A supported thermal source shows how a panel’s temperature compares with its neighbors. Together they give the reviewer evidence to follow up on.</p>
          <div className="hero-actions"><Link to="/workspace/inspect?inspection=demo" className="button primary">Explore the sample <ArrowUpRight size={16}/></Link></div>
        </div>
        <figure className="research-preview"><div className="preview-switch"><div className="segmented">
          <button onClick={()=>setThermal(false)} aria-pressed={!thermal}>RGB</button>
          <button onClick={()=>setThermal(true)} aria-pressed={thermal}>Thermal</button></div>
          <span>Synthetic example</span></div>
          <div className="sample-image">
            <img src="/research/sample-rgb.png" alt="Synthetic RGB view of three solar panels" className={thermal?'hidden-image':''} loading="lazy"/>
            <img src="/research/sample-thermal.png" alt="Synthetic thermal preview of the same three panels" className={thermal?'':'hidden-image'} loading="lazy"/>
          </div>
        </figure>
      </div></section>
    </main>
    <footer className="site-footer"><div className="site-width"><Brand/><p>Sudin Pokharel · Student 1<br/>Supervised by Dr. Raziq Yaqub</p><a href="/research/credits.txt">Asset credits <ArrowUpRight size={14}/></a></div></footer>
  </div>;
}
