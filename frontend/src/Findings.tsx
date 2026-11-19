import {useState} from 'react';
import {Link} from 'react-router-dom';
import {ArrowUpRight, Download, FileSearch, Search} from 'lucide-react';
import {
  apiPath,basename,categories,describeTemperature,formatLabel,imageUrl,inspectionLink,sources,statuses,Workspace,
} from './inspectionApi';

export default function Findings({data}:{data:Workspace}) {
  const {inspection,findings,pair_issues:issues}=data;
  const [search,setSearch]=useState('');
  const [status,setStatus]=useState('');
  const [category,setCategory]=useState('');
  const [schema,setSchema]=useState('0.3');
  const [onlyCandidates,setOnlyCandidates]=useState(false);
  const term=search.trim().toLowerCase();
  const rows=findings.filter(row=>
    (!status||status===row.finding_status)&&(!category||category===row.observation_category)&&(!onlyCandidates||row.candidate)
    &&[row.asset_id,row.rgb_image_path,row.thermal_image_path,row.observation_note,categories[row.observation_category]].some(value=>value?.toLowerCase().includes(term)));
  const {id}=inspection;
  const candidates=findings.filter(row=>row.candidate).length;
  const reviewed=findings.filter(row=>['reviewed','resolved'].includes(row.finding_status)).length;
  const query=new URLSearchParams({schema});
  if(rows.length!==findings.length) for(const row of rows) query.append('ids',row.record_id);
  return <>
    <div className="page-heading"><div><p className="eyebrow">INSPECTION WORKSPACE</p><h1>Findings</h1><p>Review observations, open their evidence, and export records.</p></div></div>
    <div className="metric-grid" aria-label="Inspection totals">
      <div className="card metric"><span>Observations</span><strong>{findings.length}</strong></div>
      <div className="card metric"><span>Suspected hotspots</span><strong>{candidates}</strong></div>
      <div className="card metric"><span>Reviewed or resolved</span><strong>{reviewed}</strong></div>
    </div>
    <section className="card section-card finding-card">
      <div className="card-heading"><div><h2>Observation records</h2><p>{rows.length} of {findings.length} observations · {sources[inspection.provenance]}</p></div>
        {!!findings.length&&<div className="download-group">
          <label className="field compact">Export version<select value={schema} onChange={event=>setSchema(event.target.value)}><option value="0.3">0.3 · Current</option><option value="0.2">0.2 · Compatibility</option></select></label>
          {!!rows.length&&<><a className="button" href={apiPath(id,'/export/json?')+query}><Download size={16}/> JSON</a>
            <a className="button primary" href={apiPath(id,'/export/csv?')+query}><Download size={16}/> CSV</a></>}
        </div>}</div>
      {!!findings.length&&<><div className="filters">
        <label className="search-label"><Search size={17}/><input type="search" aria-label="Search observations" value={search} onChange={event=>setSearch(event.target.value)} placeholder="Search panel, image, or note"/></label>
        <label className="field">Category<select value={category} onChange={event=>setCategory(event.target.value)}><option value="">All categories</option>{Object.entries(categories).map(([value,label])=><option key={value} value={value}>{label}</option>)}</select></label>
        <label className="field">Review status<select value={status} onChange={event=>setStatus(event.target.value)}><option value="">All statuses</option>{Object.entries(statuses).map(([value,label])=><option key={value} value={value}>{label}</option>)}</select></label>
        <label className="check"><input type="checkbox" checked={onlyCandidates} onChange={event=>setOnlyCandidates(event.target.checked)}/> Hotspots only</label>
      </div><p className="export-scope">Downloads include the {rows.length===findings.length?'full inspection':'filtered results'}.</p></>}
      {!rows.length?<div className="empty-state inset"><FileSearch size={30}/><h3>{findings.length?'No matching observations':'No observations yet'}</h3>
        <p>{findings.length?'Adjust your filters to see more records.':'Open an image, mark a panel, and save an observation.'}</p>
        {findings.length?<button className="button" onClick={()=>{setSearch('');setCategory('');setStatus('');setOnlyCandidates(false);}}>Clear filters</button>:<Link className="button primary" to={inspectionLink('inspect',id)}>Open viewer</Link>}</div>
      :<ul className="finding-list">{rows.map(row=>{
        const path=row.rgb_image_path||row.thermal_image_path;
        const evidence=inspectionLink('inspect',id,path,row.annotation_id,row.pair_id);
        return <li key={row.record_id} className="finding-row">
          <Link className="finding-preview" to={evidence} aria-label={'Open image for '+row.asset_id}>
            <img src={imageUrl(id,path,'thumb')} alt="" loading="lazy"/></Link>
          <div className="finding-name"><Link to={evidence}><strong>{row.asset_id||'Unassigned region'}</strong></Link>
            <span>{basename(path)}</span>{row.observation_note&&<p>{row.observation_note}</p>}</div>
          <div className="finding-category"><strong>{row.candidate?'Suspected hotspot':categories[row.observation_category]??formatLabel(row.observation_category)}</strong>
            <span>{row.data_quality_flags.includes('synthetic_data')?'Synthetic evidence':sources[inspection.provenance]}</span></div>
          <div className="finding-value"><strong className={row.candidate?'warm-text':''}>{describeTemperature(row.delta_t_c,true)}</strong><span>Temperature difference</span></div>
          <div className="finding-status"><span className={row.finding_status==='needs_verification'?'tag warning':'tag'}>{statuses[row.finding_status]??row.finding_status}</span></div>
          <Link className="icon-button" to={evidence} title="Open evidence" aria-label={'Open evidence for '+row.asset_id}><ArrowUpRight size={19}/></Link>
        </li>;
      })}</ul>}
      {issues.length>0&&<details className="pair-issues"><summary>Pairs requiring attention ({issues.length})</summary>
        <ul>{issues.map(issue=><li key={issue.pair_id}>{formatLabel(issue.pair_id)} · {issue.reason}</li>)}</ul></details>}
    </section>
  </>;
}
