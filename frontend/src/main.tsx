import {lazy,Suspense,useEffect,useState} from 'react';
import {createRoot} from 'react-dom/client';
import {BrowserRouter, Navigate, Route, Routes} from 'react-router-dom';
import Home from './Home';
import type {Theme} from './WorkspaceShell';
import {inspectionLink} from './inspectionApi';
import './portal.css';

const WorkspaceShell = lazy(() => import('./WorkspaceShell'));

function WorkspaceStart() {
  let id='demo';
  try {id=localStorage.getItem('aamu-last-inspection')??id;} catch {/* Browser storage is optional. */}
  return <Navigate replace to={inspectionLink('inspect',id)}/>;
}

function App() {
  const [theme,setTheme]=useState<Theme>(()=>{
    try {const value=localStorage.getItem('solar-theme');return value==='light'||value==='dark'?value:'system';}
    catch{return 'system';}
  });
  useEffect(()=>{
    const media=matchMedia('(prefers-color-scheme: dark)');
    const apply=()=>{document.documentElement.dataset.theme=theme==='system'?(media.matches?'dark':'light'):theme;};
    apply();
    media.addEventListener('change',apply);
    try {localStorage.setItem('solar-theme',theme);} catch {/* Browser storage is optional. */}
    return ()=>media.removeEventListener('change',apply);
  },[theme]);
  return <Suspense fallback={<p className="empty-state" role="status">Loading workspace…</p>}><Routes>
    <Route path="/" element={<Home destination="/workspace"/>}/>
    <Route path="/workspace" element={<WorkspaceStart/>}/>
    <Route path="/workspace/upload" element={<WorkspaceShell theme={theme} onTheme={setTheme} screen="upload"/>}/>
    <Route path="/workspace/inspect" element={<WorkspaceShell theme={theme} onTheme={setTheme} screen="inspect"/>}/>
    <Route path="/workspace/findings" element={<WorkspaceShell theme={theme} onTheme={setTheme} screen="findings"/>}/>
    <Route path="*" element={<main className="empty-state"><h1>Page not found</h1><a className="button primary" href="/">Project homepage</a></main>}/>
  </Routes></Suspense>;
}

createRoot(document.getElementById('root')!).render(<BrowserRouter><App/></BrowserRouter>);
