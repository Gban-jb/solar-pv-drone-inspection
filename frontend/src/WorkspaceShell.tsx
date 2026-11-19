import {lazy,useCallback,useEffect,useState} from 'react';
import {Link, NavLink, useLocation, useNavigate, useSearchParams} from 'react-router-dom';
import {ArrowUpRight, ClipboardList, ImagePlus, Menu, Moon, ScanLine, Sun, X} from 'lucide-react';
import {Brand} from './Home';
import {api, apiPath, Inspection, inspectionLink, sources, Workspace} from './inspectionApi';
import Upload from './Upload';
const Inspect = lazy(() => import('./Inspect'));
import Findings from './Findings';

export type Theme = 'system' | 'dark' | 'light';
export type Screen = 'upload' | 'inspect' | 'findings';

const screens = [
  {name:'Upload', value:'upload', icon:ImagePlus},
  {name:'Inspect', value:'inspect', icon:ScanLine},
  {name:'Findings', value:'findings', icon:ClipboardList},
] as const;

export function useWorkspaceID() {
  const [params] = useSearchParams();
  const [saved,setSaved] = useState(() => { try {return localStorage.getItem('aamu-last-inspection') ?? 'demo';} catch {return 'demo';} });
  const id = params.get('inspection') || saved;
  const remember = useCallback((value:string) => {
    setSaved(value);
    try {localStorage.setItem('aamu-last-inspection',value);} catch { /* Browser storage is optional. */ }
  },[]);
  return {id,remember};
}

export default function WorkspaceShell({theme,onTheme,screen}: {theme:Theme;onTheme:(theme:Theme)=>void;screen:Screen}) {
  const {id,remember} = useWorkspaceID();
  const navigate = useNavigate();
  const location = useLocation();
  const [data,setData] = useState<Workspace>();
  const [inspections,setInspections] = useState<Inspection[]>([]);
  const [error,setError] = useState('');
  const [mobileNav,setMobileNav] = useState(false);
  const [refreshKey,setRefreshKey] = useState(0);
  const refresh = () => setRefreshKey(value => value + 1);

  useEffect(()=>{
    const controller = new AbortController();
    setError('');
    void api<Workspace>(apiPath(id), {signal:controller.signal}).then(value=>{
      setData(value); remember(value.inspection.id);
    }).catch((error:Error)=>{if(error.name!=='AbortError') setError(error.message);});
    void api<Inspection[]>('/api/inspections',{signal:controller.signal}).then(setInspections)
      .catch(()=>{/* The current inspection reports connection errors separately. */});
    return ()=>controller.abort();
  },[id,remember,refreshKey]);

  useEffect(()=>setMobileNav(false),[location.pathname,location.search]);
  const current = data?.inspection.id===id ? data : undefined;
  return <div className="workspace-shell">
    <a href="#workspace-main" className="skip-link">Skip to workspace</a>
    <aside className={'workspace-sidebar'+(mobileNav?' mobile-open':'')}>
      <Brand/>
      <nav aria-label="Workspaces">{screens.map(({name,value,icon:Icon})=>
        <NavLink key={value} end to={inspectionLink(value,id)}><Icon size={19}/><span>{name}</span></NavLink>)}</nav>
      <div className="sidebar-foot"><div className="project-initials">SP</div><span><strong>Sudin Pokharel</strong><small>Student 1 · AAMU</small></span></div>
    </aside>
    {mobileNav&&<button className="nav-scrim" aria-label="Close navigation" onClick={()=>setMobileNav(false)}/>}
    <div className="workspace-main">
      <header className="workspace-header">
        <button className="icon-button mobile-menu" aria-label={mobileNav?'Close navigation':'Open navigation'} aria-expanded={mobileNav} onClick={()=>setMobileNav(!mobileNav)}>{mobileNav?<X size={21}/>:<Menu size={21}/>}</button>
        <label className="inspection-switch"><span>Inspection</span><select aria-label="Active inspection" value={id} onChange={event=>navigate(inspectionLink(screen,event.target.value))}>
          {!inspections.some(item=>item.id===id)&&<option value={id}>{current?.inspection.name??'Loading inspection…'}</option>}
          {inspections.map(item=><option key={item.id} value={item.id}>{item.name}</option>)}
        </select></label>
        <div className="workspace-tools">
          {current&&<span className="source-flag">{sources[current.inspection.provenance]}</span>}
          <label className="appearance" title="Appearance">{theme==='dark'?<Moon size={17}/>:<Sun size={17}/>}<select aria-label="Appearance" value={theme} onChange={event=>onTheme(event.target.value as Theme)}>
            <option value="system">System</option><option value="light">Light</option><option value="dark">Dark</option>
          </select></label>
          <Link to="/" className="icon-button" aria-label="Project homepage" title="Project homepage"><ArrowUpRight size={18}/></Link>
        </div>
      </header>
      <main className="workspace-content" id="workspace-main">
        {error ? <div className="empty-state" role="alert"><h1>Inspection unavailable</h1><p>{error}</p>
          <button className="button primary" onClick={refresh}>Retry</button> <Link className="button" to={inspectionLink(screen,'demo')}>Open sample</Link></div>
          : !current ? <div className="empty-state" role="status">Loading inspection…</div>
          : screen==='upload' ? <Upload key={id} data={current} refresh={refresh}/>
          : screen==='findings' ? <Findings key={id} data={current}/>
          : <Inspect key={id} data={current} refresh={refresh}/>}
      </main>
    </div>
  </div>;
}
