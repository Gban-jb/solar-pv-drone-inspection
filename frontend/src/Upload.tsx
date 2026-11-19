import {useRef,useState,type FormEvent} from 'react';
import {Link,useNavigate} from 'react-router-dom';
import {ArrowRight, FileImage, FileText, FolderPlus, Layers, UploadCloud} from 'lucide-react';
import {api,apiPath,basename,FileRole,formatLabel,imageUrl,Inspection,inspectionLink,jsonRequest,roles,Source,Workspace} from './inspectionApi';

type UploadResult = {name:string;status:string;message?:string;details?:string;missing_fields?:string[]};
const fileTypes:Record<FileRole,string> = {
  rgb:'.jpg,.jpeg,.png,.tiff,.tif,.webp', thermal:'.jpg,.jpeg,.png,.tiff,.tif,.webp',
  temperature_grids:'.json', scada:'.csv',
};

export default function Upload({data,refresh}: {data:Workspace;refresh:()=>void}) {
  const {inspection,files,pairs,temperature_sources:grids} = data;
  const {id,read_only:readOnly} = inspection;
  const navigate=useNavigate();
  const input=useRef<HTMLInputElement>(null);
  const [role,setRole]=useState<FileRole>('rgb');
  const [drag,setDrag]=useState(false);
  const [progress,setProgress]=useState('');
  const [results,setResults]=useState<UploadResult[]>([]);
  const [showAll,setShowAll]=useState(false);
  const [search,setSearch]=useState('');
  const [newName,setNewName]=useState('');
  const [sample,setSample]=useState('empty');
  const [source,setSource]=useState<Source>('field_unverified');
  const [citation,setCitation]=useState('');
  const [creating,setCreating]=useState(false);
  const [error,setError]=useState('');
  const [rgb,setRgb]=useState('');
  const [thermal,setThermal]=useState('');
  const [temp,setTemp]=useState('');
  const [aligned,setAligned]=useState(false);
  const [pairNotice,setPairNotice]=useState('');
  const [savingPair,setSavingPair]=useState(false);
  const [pairError,setPairError]=useState(false);

  async function create(event?:FormEvent, copy=false) {
    event?.preventDefault();
    setCreating(true);setError('');
    try {
      const item = await api<Inspection>('/api/inspections',jsonRequest('POST',{name:copy?'Thermal sample working copy':newName,sample:copy?'thermal':sample,provenance:source,source:citation}));
      navigate(inspectionLink(copy?'inspect':'upload',item.id));
    } catch (err) {setError((err as Error).message);} finally {setCreating(false);}
  }

  async function send(incoming:FileList|null) {
    if (!incoming?.length || progress || readOnly) return;
    const queue=Array.from(incoming);
    setResults([]);
    for (let index=0;index<queue.length;index++) {
      const file=queue[index];
      setProgress(`Importing ${index+1} of ${queue.length} · ${file.name}`);
      const form=new FormData();form.append('file',file);
      try {
        const result=await api<UploadResult>(apiPath(id,'/files/'+role),{method:'POST',body:form});
        setResults(previous=>[...previous,result]);
      } catch (err) {
        const error=err as Error & {cause?:string};
        setResults(previous=>[...previous,{name:file.name,status:'error',message:error.message,details:error.cause}]);
      }
    }
    setProgress('');refresh();
  }

  async function pair(event:FormEvent) {
    event.preventDefault();setPairNotice('');setSavingPair(true);setPairError(false);
    try {
      await api(apiPath(id,'/pairs'),jsonRequest('POST',{rgb_path:rgb,thermal_path:thermal,temperature_path:temp,alignment_reviewed:aligned}));
      setPairNotice('Image pair saved.');setRgb('');setThermal('');setTemp('');setAligned(false);refresh();
    } catch (err) {setPairError(true);setPairNotice((err as Error).message);} finally {setSavingPair(false);}
  }

  const readable=files.filter(file=>file.status!=='error');
  const images=readable.filter(file=>file.kind!=='scada');
  const matching=files.filter(file=>file.path.toLowerCase().includes(search.trim().toLowerCase()));
  const pickedRgb=images.find(file=>file.path===rgb);
  const pickedThermal=images.find(file=>file.path===thermal);
  const sameSize=!!(pickedRgb&&pickedThermal&&pickedRgb.width===pickedThermal.width&&pickedRgb.height===pickedThermal.height);
  const matchingTime=pickedRgb?.capture_time_raw;
  const timeMatches=matchingTime?images.filter(file=>file.kind==='thermal'&&file.capture_time_raw===matchingTime):[];
  const suggested=timeMatches.length===1&&timeMatches[0].path!==thermal?timeMatches[0]:undefined;
  return <>
    <div className="page-heading"><div><p className="eyebrow">INSPECTION WORKSPACE</p><h1>Upload</h1><p>Bring files together and review what is ready to inspect.</p></div>
      {images.length>0&&<Link to={inspectionLink('inspect',id)} className="button primary">Open viewer <ArrowRight size={17}/></Link>}</div>
    <div className="upload-layout">
      <section className="card section-card">
        <div className="card-heading"><div><h2>Import files</h2><p>Choose the type of files you want to add.</p></div></div>
        {readOnly?<div className="empty-state inset"><Layers size={30}/><h3>Explore the sample</h3><p>Make an editable copy to practice importing and pairing files.</p>
          <button className="button primary" disabled={creating} onClick={()=>void create(undefined,true)}>Make working copy</button></div>
          : <><label className="field compact">File type<select value={role} onChange={event=>setRole(event.target.value as FileRole)} disabled={!!progress}>{Object.entries(roles).map(([value,label])=><option key={value} value={value}>{label}</option>)}</select></label>
          <div className={'dropzone'+(drag?' dragging':'')} onDragOver={event=>{event.preventDefault();setDrag(true);}}
            onDragLeave={event=>{if (!event.currentTarget.contains(event.relatedTarget as Node|null)) setDrag(false);}}
            onDrop={event=>{event.preventDefault();setDrag(false);void send(event.dataTransfer.files);}}>
            <span className="drop-icon"><UploadCloud size={29}/></span><strong>Drop {roles[role].toLowerCase()} here</strong>
            <span>Up to 160 MB per file</span><button className="button primary" disabled={!!progress} onClick={()=>input.current?.click()}>Browse files</button>
            <input ref={input} type="file" multiple accept={fileTypes[role]} aria-label="Choose inspection files" hidden onChange={event=>{void send(event.currentTarget.files);event.currentTarget.value='';}}/>
          </div></>}
        {progress&&<p className="notice" role="status">{progress}</p>}
        {results.length>0&&<ul className="upload-results" aria-live="polite">{results.map((result,index)=>
          <li key={result.name+index}><strong>{result.name}</strong><span className={result.status==='error'?'tag warning':'tag'}>{result.status==='ok'?'Ready':result.status==='warning'?'Imported with warnings':result.status==='duplicate'?'Duplicate':'Could not import'}</span>
          {result.message&&<p>{result.message}</p>}{result.missing_fields?.length?<p>Missing {result.missing_fields.map(formatLabel).join(', ')}</p>:null}
          {result.details&&<details><summary>Technical details</summary><p>{result.details}</p></details>}</li>)}</ul>}
      </section>
      <section className="card section-card"><div className="card-heading"><div><h2>New inspection</h2><p>Start with your own files or a prepared sample.</p></div><FolderPlus size={21}/></div>
        <form className="form-stack" onSubmit={event=>void create(event)}>
          <label className="field">Inspection name<input required maxLength={100} value={newName} onChange={event=>setNewName(event.target.value)} placeholder="e.g. North array flight"/></label>
          <label className="field">Starting files<select value={sample} onChange={event=>setSample(event.target.value)}><option value="empty">Empty inspection</option><option value="thermal">Thermal sample · 4 image pairs</option><option value="import">Import sample · 10 images and CSV</option><option value="annotation">Annotation sample · 20 panel boxes</option></select></label>
          {sample==='empty'&&<label className="field">Data source<select value={source} onChange={event=>setSource(event.target.value as Source)}><option value="field_unverified">Unverified field data</option><option value="public_research">Public research</option><option value="synthetic">Synthetic sample</option></select></label>}
          {sample==='empty'&&<label className="field">Source reference {source!=='public_research'&&'(optional)'}<input maxLength={500} required={source==='public_research'} value={citation} onChange={event=>setCitation(event.target.value)} placeholder="Flight notes or source URL"/></label>}
          <button className="button" disabled={creating}>{creating?'Creating…':'Create inspection'}</button>
          {error&&<p className="notice error" role="alert">{error}</p>}
        </form>
      </section>
    </div>
    <section className="card section-card collection">
      <div className="card-heading"><div><h2>File collection</h2><p>{images.length} images ready · {readable.length-images.length} meter files · {grids.length} temperature sources · {files.length-readable.length} unreadable</p></div>
        <input className="search" type="search" aria-label="Search files" placeholder="Search files" value={search} onChange={event=>setSearch(event.target.value)}/></div>
      {!matching.length&&!grids.length?<p className="empty-state inset">{search?'No matching files.':'Files appear here after import.'}</p>
        :<div className="file-grid">{(showAll?matching:matching.slice(0,10)).map(file=><article className="file-card" key={file.path}>
          {file.status!=='error'&&file.kind!=='scada'?<Link to={inspectionLink('inspect',id,file.path)} className="file-preview"><img alt={'Open '+basename(file.path)} loading="lazy" src={imageUrl(id,file.path,'thumb')}/></Link>
            : <div className="file-preview file-icon">{file.kind==='scada'?<FileText size={27}/>:<FileImage size={27}/>}</div>}
          <div className="file-body"><strong title={basename(file.path)}>{basename(file.path)}</strong><small>{roles[file.kind]} · {file.status==='error'?'Unreadable':file.width?`${file.width} × ${file.height}`:`${file.row_count ?? 0} rows`}</small>
            <details><summary>{file.error?'File error':'File details'}</summary>
              {file.error?<p>{file.error}</p>:<>
                {file.format&&<p>Format {file.format}</p>}
                {file.camera_model&&<p>Camera {file.camera_model}</p>}
                {file.capture_time_raw&&<p>Capture time {file.capture_time_raw}</p>}
                {file.missing_fields.length>0&&<p>Missing {file.missing_fields.map(formatLabel).join(', ')}</p>}
              </>}
            </details></div>
          </article>)}</div>}
      {matching.length>10&&<button className="button" onClick={()=>setShowAll(!showAll)}>{showAll?'Show fewer files':`Show all ${matching.length} files`}</button>}
      {grids.length>0&&<details><summary>Temperature sources ({grids.length})</summary><ul>{grids.map(grid=><li key={grid}>{basename(grid)}</li>)}</ul></details>}
    </section>
    <section className="card section-card collection"><div className="card-heading"><div><h2>Image pairs</h2><p>Link captures of the same scene. Review spatial alignment before sharing panel boxes between them.</p></div></div>
      {!readOnly&&<form className="pair-form" onSubmit={event=>void pair(event)}>
        <label className="field">RGB image<select required value={rgb} onChange={event=>{setRgb(event.target.value);setAligned(false);}}><option value="">Select RGB</option>{images.filter(file=>file.kind==='rgb').map(file=><option key={file.path} value={file.path}>{basename(file.path)}</option>)}</select></label>
        <label className="field">Thermal image<select required value={thermal} onChange={event=>{setThermal(event.target.value);setAligned(false);}}><option value="">Select thermal</option>{images.filter(file=>file.kind==='thermal').map(file=><option key={file.path} value={file.path}>{basename(file.path)}</option>)}</select></label>
        <label className="field">Temperature source<select value={temp} onChange={event=>setTemp(event.target.value)}><option value="">Display only</option>{grids.map(grid=><option key={grid} value={grid}>{basename(grid)}</option>)}</select></label>
        {suggested&&<p className="pair-note">One thermal image has the same recorded capture time. <button className="button small" type="button" onClick={()=>{setThermal(suggested.path);setAligned(false);}}>Preview suggested match</button></p>}
        {(pickedRgb||pickedThermal)&&<div className="pair-previews">{[pickedRgb,pickedThermal].map((file,index)=>file
          ?<figure key={file.path}><img src={imageUrl(id,file.path,'thumb')} alt={index===0?'RGB image for alignment review':'Thermal image for alignment review'}/><figcaption>{index===0?'RGB':'Thermal'} · {file.width} × {file.height}</figcaption></figure>
          :<div className="pair-placeholder" key={index}>Select a {index===0?'RGB':'thermal'} image</div>)}</div>}
        {pickedRgb&&pickedThermal&&!sameSize&&<p className="pair-note">Image dimensions differ. You can save the pair for separate views.</p>}
        <label className="check"><input type="checkbox" checked={aligned} disabled={!sameSize} onChange={event=>setAligned(event.target.checked)}/> I verified that both images share the same pixel geometry.</label>
        <button className="button" disabled={savingPair||!rgb||!thermal}>{savingPair?'Saving…':'Save image pair'}</button>
        {pairNotice&&<p className={'notice'+(pairError?' error':'')} role={pairError?'alert':'status'}>{pairNotice}</p>}
      </form>}
      {!pairs.length?<p className="muted">No image pairs yet. You can inspect individual images.</p>:<ul className="pair-list">{pairs.map(pair=><li key={pair.pair_id}><Link to={inspectionLink('inspect',id,pair.rgb_path,undefined,pair.pair_id)}>{basename(pair.rgb_path)} <ArrowRight size={14}/></Link><span>{pair.alignment_reviewed?'Alignment reviewed':'Separate views'} · {pair.basis==='display_only'?'Display only':formatLabel(pair.basis)}</span></li>)}</ul>}
    </section>
  </>;
}
