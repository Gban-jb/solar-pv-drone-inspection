import {useEffect,useRef,useState,type FormEvent} from 'react';
import {Link,useNavigate,useSearchParams} from 'react-router-dom';
import {ArrowLeft,ArrowRight,ArrowUpRight,Download,ImageIcon,MousePointer2,SquareDashed,Thermometer} from 'lucide-react';
import ImageViewer,{Mark} from './ImageViewer';
import {
  Annotation,api,apiPath,basename,Box,boxOf,canMeasure,categories,describeTemperature,
  formatLabel,imageUrl,Inspection,inspectionLink,jsonRequest,Measurements,Pair,statuses,Workspace,
} from './inspectionApi';

type View = 'rgb'|'thermal'|'compare';
type Tool = 'select'|'draw'|'region'|'reference';
type Pending = {box:Box;id:string};
const parseBox=(value:string):Box|undefined=>value?value.split(',').map(Number) as Box:undefined;

function BoundsFields({value,onChange,label}: {value:Box;onChange:(box:Box)=>void;label:string}) {
  return <fieldset className="bounds-fields"><legend>{label} (%)</legend><div>{['Left','Top','Right','Bottom'].map((side,index)=>
    <label className="field" key={side}>{side}<input type="number" step="any" min="0" max="100"
      value={Number((value[index]*100).toFixed(2))}
      onChange={event=>{const next=[...value] as Box;next[index]=Number(event.target.value)/100;onChange(next);}}/></label>)}</div></fieldset>;
}

export default function Inspect({data,refresh}:{data:Workspace;refresh:()=>void}) {
  const [params,setParams]=useSearchParams();
  const navigate=useNavigate();
  const {inspection,files,pairs,annotations,findings}=data;
  const {id,read_only:readOnly}=inspection;
  const images=files.filter(file=>file.kind!=='scada'&&file.status!=='error');
  const requested=params.get('image');
  const pairParam=params.get('pair');
  const requestedPair=pairs.find(item=>item.pair_id===pairParam&&(!requested||[item.rgb_path,item.thermal_path].includes(requested)));
  const active=images.find(file=>file.path===requested)??images.find(file=>file.path===requestedPair?.rgb_path)
    ??images.find(file=>file.path===pairs[0]?.rgb_path)??images[0];
  const pair=requestedPair??pairs.find(item=>item.rgb_path===active?.path||item.thermal_path===active?.path);
  const rgb=images.find(file=>file.path===(pair?.rgb_path??(active?.kind==='rgb'?active.path:undefined)));
  const thermal=images.find(file=>file.path===(pair?.thermal_path??(active?.kind==='thermal'?active.path:undefined)));
  const labels=annotations.filter(item=>item.image_path===rgb?.path);
  const currentID=params.get('annotation')??'';
  const current=labels.find(row=>row.annotation_id===currentID);
  const currentFinding=findings.find(row=>row.annotation_id===currentID&&(!row.pair_id||row.pair_id===pair?.pair_id));
  const [mode,setMode]=useState<View>(active?.kind==='thermal'?'thermal':'rgb');
  const [tool,setTool]=useState<Tool>('select');
  const [pending,setPending]=useState<Pending>();
  const [showMarks,setShowMarks]=useState(true);
  const [heat,setHeat]=useState(true);
  const [scaleOverride,setScaleOverride]=useState<[number,number]>();
  const [original,setOriginal]=useState(false);
  const [selectedRegion,setSelectedRegion]=useState<Box>();
  const [referenceRegion,setReferenceRegion]=useState<Box>();
  const [measurement,setMeasurement]=useState<Measurements>();
  const [measurementError,setMeasurementError]=useState('');
  const [message,setMessage]=useState('');
  const [error,setError]=useState('');
  const [busy,setBusy]=useState(false);
  const [confirmDelete,setConfirmDelete]=useState(false);
  const [asset,setAsset]=useState('');
  const [target,setTarget]=useState<Annotation['target_type']>('panel');
  const [confirmed,setConfirmed]=useState(false);
  const [category,setCategory]=useState('unclassified');
  const [review,setReview]=useState('draft');
  const [severity,setSeverity]=useState('unassigned');
  const [note,setNote]=useState('');
  const [regionEdited,setRegionEdited]=useState(false);
  const newAsset=useRef<HTMLInputElement>(null);
  const numeric=canMeasure(pair);
  const selectedBox=selectedRegion??(pair?.alignment_reviewed&&current?.target_type==='panel'?boxOf(current):undefined);

  useEffect(()=>{
    setTool('select');setPending(undefined);setHeat(true);setScaleOverride(undefined);setOriginal(false);setError('');setMessage('');
    setMode(active?.kind==='thermal'?'thermal':'rgb');
  },[active?.path,pair?.pair_id]);
  useEffect(()=>{
    setCategory(current?.observation_category??'unclassified');
    setReview(current?.finding_status??'draft');
    setSeverity(current?.severity??'unassigned');
    setNote(current?.observation_note??'');
    setSelectedRegion(parseBox(current?.thermal_region_bounds??''));
    setReferenceRegion(parseBox(current?.thermal_reference_bounds??''));
    setRegionEdited(false);setConfirmDelete(false);
  },[current?.annotation_id,current?.modified_at_utc,pair?.pair_id]);
  useEffect(()=>{
    if(pending?.id==='new') newAsset.current?.focus();
  },[pending?.id]);
  useEffect(()=>{
    setMeasurement(undefined);setMeasurementError('');
    if(!numeric||!pair||!selectedBox||(!currentID&&!regionEdited)) return;
    const controller=new AbortController();
    const timer=window.setTimeout(()=>{
      void api<Measurements>(apiPath(id,`/pairs/${pair.pair_id}/measure`),{
        ...jsonRequest('POST',{selected:{box:selectedBox},reference:referenceRegion?{box:referenceRegion}:null}),signal:controller.signal,
      }).then(setMeasurement).catch((error:Error)=>{if(error.name!=='AbortError')setMeasurementError(error.message);});
    },130);
    return ()=>{window.clearTimeout(timer);controller.abort();};
  },[id,pair?.pair_id,numeric,selectedRegion,referenceRegion,currentID,current?.modified_at_utc,regionEdited]);

  function open(path:string, annotation?:string, which?:Pair) {
    const url=new URL(inspectionLink('inspect',id,path,annotation,which?.pair_id),location.origin);
    setParams(url.searchParams);
  }
  function chooseMark(annotation:string) {
    if (!active || !labels.some(row=>row.annotation_id===annotation)) return;
    setPending(undefined);setTool('select');open(active.path,annotation,pair);
  }
  function chooseMode(next:View) {
    setTool('select');setMode(next);
  }
  function setDrawing(next:Tool) {
    setTool(next);
    if(next==='draw') setMode('rgb');
    if(next==='region'||next==='reference') setMode('thermal');
  }
  function edit(row:Annotation) {
    setAsset(row.asset_id);setTarget(row.target_type);setConfirmed(row.review_status==='confirmed');
    setPending({id:row.annotation_id,box:boxOf(row)});setMode('rgb');setTool('select');
  }
  async function perform(action:()=>Promise<void>) {
    setBusy(true);setError('');setMessage('');
    try {await action();} catch(err){setError((err as Error).message);} finally {setBusy(false);}
  }
  async function saveBox(event:FormEvent) {
    event.preventDefault();
    if (!pending||!rgb) return;
    await perform(async()=>{
      const saved=await api<Annotation>(apiPath(id,`/annotations/${pending.id}`),jsonRequest('PUT',{
        asset_id:asset,image_path:rgb.path,target_type:target,review_status:confirmed?'confirmed':'provisional',box:pending.box,
        modified_at_utc:pending.id==='new'?null:current?.modified_at_utc,
      }));
      setPending(undefined);setMessage('Annotation saved.');open(rgb.path,saved.annotation_id,pair);refresh();
    });
  }
  async function saveFinding(event:FormEvent) {
    event.preventDefault();
    if (!current) return;
    await perform(async()=>{
      const useRegions=!!(regionEdited&&selectedBox&&numeric);
      await api(apiPath(id,`/findings/${current.annotation_id}`),jsonRequest('PUT',{
        category,status:review,severity,note,pair_id:pair?.pair_id,modified_at_utc:current.modified_at_utc,
        regions:useRegions?{selected:{box:selectedBox},reference:referenceRegion?{box:referenceRegion}:null}:null,
      }));
      setMessage('Observation saved.');refresh();
    });
  }
  async function remove() {
    if(!current||!rgb) return;
    await perform(async()=>{
      await api(apiPath(id,`/annotations/${current.annotation_id}?`)+new URLSearchParams({modified_at_utc:current.modified_at_utc}),{method:'DELETE'});
      setConfirmDelete(false);open(rgb.path,undefined,pair);setMessage('Annotation and linked observation removed.');refresh();
    });
  }
  function drawBox(box:Box) {
    if(tool==='draw'){
      setPending({id:'new',box});setAsset('');setTarget('panel');setConfirmed(false);
    }
    if(tool==='region') {setSelectedRegion(box);setRegionEdited(true);}
    if(tool==='reference') {setReferenceRegion(box);setRegionEdited(true);}
    setTool('select');
  }
  function copy() {
    void perform(async()=>{
      const copy=await api<Inspection>('/api/inspections',jsonRequest('POST',{name:'Thermal sample working copy',sample:'thermal'}));
      navigate(inspectionLink('inspect',copy.id,active?.path,currentID,pair?.pair_id));
    });
  }

  const view=(mode==='compare'&&rgb&&thermal)?'compare':mode==='thermal'&&thermal?'thermal':rgb?'rgb':'thermal';
  const rgbMarks:Mark[]=showMarks?labels.filter(row=>row.annotation_id!==pending?.id).map(row=>({
    id:row.annotation_id,box:boxOf(row),label:row.asset_id,active:row.annotation_id===currentID,
    candidate:findings.some(item=>item.annotation_id===row.annotation_id&&item.pair_id===pair?.pair_id&&item.candidate),
  })):[];
  const thermalMarks:Mark[]=(pair?.alignment_reviewed&&showMarks?rgbMarks:[]).filter(mark=>mark.id!==currentID||!selectedRegion);
  if(showMarks&&selectedRegion) thermalMarks.push({id:currentID,box:selectedRegion,label:'Selected region',active:true,color:'#fff0ce'});
  if(showMarks&&referenceRegion) thermalMarks.push({id:'reference',box:referenceRegion,label:'Reference',color:'#7fe6f0'});
  const heatAvailable=!!(numeric&&pair?.limits&&pair.alignment_reviewed&&labels.some(row=>row.target_type==='panel'&&row.review_status==='confirmed'));
  const heatLimits=scaleOverride??pair?.limits;
  const heatScaleValid=!!heatLimits&&heatLimits[0]>=-273.15&&heatLimits[1]<=2000&&heatLimits[0]<heatLimits[1];
  const heatParams=new URLSearchParams({v:labels.map(row=>row.modified_at_utc).join(',')});
  if(heatScaleValid&&scaleOverride) {heatParams.set('low',String(scaleOverride[0]));heatParams.set('high',String(scaleOverride[1]));}
  const rgbIndex=images.findIndex(item=>item.path===active?.path);
  const reviewMessage=pair?.error || (numeric?pair?.basis==='synthetic_numeric_demo'?'Synthetic temperature measurements.':'Validated temperature source.':
    pair?.basis==='unverified_numeric'?'Calibration is unverified. Temperatures are unavailable.':'Visual preview only. Temperatures are unavailable.');
  return <>
    <div className="page-heading"><div><p className="eyebrow">INSPECTION WORKSPACE</p><h1>Inspect</h1><p>Mark panels and compare the evidence from each image.</p></div>
      {readOnly?<button className="button primary" onClick={copy} disabled={busy}>Make working copy <ArrowUpRight size={16}/></button>
        :<Link className="button" to={inspectionLink('findings',id)}>View findings <ArrowRight size={16}/></Link>}</div>
    {!active?<div className="empty-state card"><ImageIcon size={33}/><h2>No images to inspect</h2><p>Add RGB or thermal files to open the viewer.</p>
      <Link className="button primary" to={inspectionLink('upload',id)}>Upload files <ArrowRight size={16}/></Link></div>
    :<div className="inspect-layout">
      <section className="card viewer-card" aria-label="Inspection image viewer">
        <div className="image-navigation">
          <label className="image-select"><span>Source image</span><select aria-label="Source image" value={active.path} onChange={event=>open(event.target.value)}>{images.map(file=><option key={file.path} value={file.path}>{basename(file.path)} · {file.kind==='rgb'?'RGB':'Thermal'}</option>)}</select></label>
          <div className="image-pagination"><button className="icon-button" aria-label="Previous image" disabled={rgbIndex<=0} onClick={()=>open(images[rgbIndex-1].path)}><ArrowLeft size={17}/></button>
            <span>{rgbIndex+1} / {images.length}</span><button className="icon-button" aria-label="Next image" disabled={rgbIndex>=images.length-1} onClick={()=>open(images[rgbIndex+1].path)}><ArrowRight size={17}/></button></div>
        </div>
        <div className="viewer-toolbar">
          <div className="segmented" aria-label="Image layer"><button aria-pressed={view==='rgb'} disabled={!rgb} onClick={()=>chooseMode('rgb')}>RGB</button>
            <button aria-pressed={view==='thermal'} disabled={!thermal} onClick={()=>chooseMode('thermal')}>Thermal</button>
            <button aria-pressed={view==='compare'} disabled={!rgb||!thermal} onClick={()=>chooseMode('compare')}>Compare</button></div>
          <div className="viewer-options"><label className="check"><input type="checkbox" checked={showMarks} onChange={event=>setShowMarks(event.target.checked)}/> Marks</label>
            {view!=='rgb'&&heatAvailable&&<label className="check"><input type="checkbox" checked={heat} onChange={event=>setHeat(event.target.checked)}/> Heat colors</label>}
            <label className="check"><input type="checkbox" checked={original} onChange={event=>setOriginal(event.target.checked)}/> Full resolution</label></div>
        </div>
        <div className={'viewer-grid '+(view==='compare'?'two-views':'')}>
          {rgb&&view!=='thermal'&&<ImageViewer key={'rgb:'+rgb.path} alt="RGB image" src={imageUrl(id,rgb.path,original?'original':'viewer')} width={rgb.width??1} height={rgb.height??1}
            marks={rgbMarks} onSelect={chooseMark} draw={tool==='draw'} onDraw={drawBox}
            editable={pending?.box} onEdit={box=>setPending(previous=>previous?{...previous,box}:undefined)}/>}
          {thermal&&view!=='rgb'&&<ImageViewer key={'thermal:'+thermal.path} alt="Thermal image"
            src={heat&&heatAvailable&&pair?apiPath(id,`/pairs/${pair.pair_id}/heat?`)+heatParams:imageUrl(id,thermal.path,original?'original':'viewer')}
            width={thermal.width??1} height={thermal.height??1} marks={thermalMarks} onSelect={pair?.alignment_reviewed?chooseMark:undefined}
            draw={tool==='region'||tool==='reference'} onDraw={drawBox}/>}
        </div>
        {view!=='rgb'&&heat&&heatAvailable&&pair?.limits&&heatLimits&&<>
          <div className="temperature-key"><span>{heatScaleValid?heatLimits[0]:pair.limits[0]} °C</span><i/><span>{heatScaleValid?heatLimits[1]:pair.limits[1]} °C</span></div>
          <details className="scale-controls"><summary>Adjust display scale</summary><div className="double-fields">
            <label className="field">Cool (°C)<input type="number" step="any" value={heatLimits[0]} onChange={event=>setScaleOverride([Number(event.target.value),heatLimits[1]])}/></label>
            <label className="field">Hot (°C)<input type="number" step="any" value={heatLimits[1]} onChange={event=>setScaleOverride([heatLimits[0],Number(event.target.value)])}/></label></div>
            {!heatScaleValid&&<p className="notice warning" role="status">Set a valid increasing range. The preview uses the default range until then.</p>}
            <button className="button small" onClick={()=>setScaleOverride(undefined)}>Reset scale</button>
          </details></>}
        <div className="viewer-footer"><div className="viewer-actions">
          <button className="button small" aria-pressed={tool==='select'} onClick={()=>setDrawing('select')}><MousePointer2 size={15}/> Select</button>
          {!readOnly&&rgb&&<button className="button small" aria-pressed={tool==='draw'} onClick={()=>{setPending(undefined);setDrawing('draw');}}><SquareDashed size={16}/> Draw box</button>}
          {!readOnly&&rgb&&tool==='draw'&&<button className="button small" onClick={()=>{setAsset('');setTarget('panel');setConfirmed(false);setPending({id:'new',box:[.25,.25,.5,.5]});setTool('select');}}>Enter box coordinates</button>}
          {numeric&&<button className="button small" aria-pressed={tool==='region'} onClick={()=>setDrawing('region')}><Thermometer size={15}/> Measure region</button>}
          {numeric&&tool==='region'&&<button className="button small" onClick={()=>{setSelectedRegion([.25,.25,.5,.5]);setRegionEdited(true);setTool('select');}}>Enter region bounds</button>}
          {numeric&&selectedBox&&<button className="button small" aria-pressed={tool==='reference'} onClick={()=>setDrawing('reference')}>Set reference</button>}
        </div>
        <span>{tool==='select'?pair?(pair.alignment_reviewed?'Alignment reviewed':'Views are unregistered'):'Single source image':tool==='draw'?'Drag a box over the panel or row.':tool==='region'?'Drag over the region to measure.':'Drag over a comparable reference region.'}</span></div>
        {view!=='rgb'&&<p className="measurement-banner">{thermal&&reviewMessage}</p>}
      </section>
      <aside className="card detail-card">
        <div className="card-heading"><div><h2>{pending?'Panel or row box':current?current.asset_id:'Inspection details'}</h2><p>{pending?'Set the ID and check the bounds.':current?'Selected annotation':'Select a panel or draw a box.'}</p></div>
          {currentFinding?.candidate&&<span className="tag warning">Suspected hotspot</span>}</div>
        {labels.length>0&&<label className="field">Panel or row<select value={currentID} onChange={event=>{if(event.target.value)chooseMark(event.target.value);else open(active.path,undefined,pair);}}>
          <option value="">Choose an annotation</option>{labels.map(row=><option key={row.annotation_id} value={row.annotation_id}>{row.asset_id||row.annotation_id}{findings.some(item=>item.annotation_id===row.annotation_id&&item.pair_id===pair?.pair_id&&item.candidate)?' · Hotspot candidate':''}</option>)}</select></label>}
        {pending&&<form className="form-stack detail-section" onSubmit={event=>void saveBox(event)}>
          <label className="field">Panel or row ID<input ref={newAsset} required maxLength={80} value={asset} onChange={event=>setAsset(event.target.value)}/></label>
          <label className="field">Annotation type<select value={target} onChange={event=>setTarget(event.target.value as Annotation['target_type'])}><option value="panel">Panel</option><option value="row">Row</option><option value="region">Region</option></select></label>
          <BoundsFields label="Box bounds" value={pending.box} onChange={box=>setPending({...pending,box})}/>
          <label className="check"><input type="checkbox" checked={confirmed} onChange={event=>setConfirmed(event.target.checked)}/> Box confirmed</label>
          <div className="button-row"><button className="button primary" disabled={busy}>Save annotation</button><button type="button" className="button" onClick={()=>setPending(undefined)}>Cancel</button></div>
        </form>}
        {!pending&&current&&<div className="detail-section">
          <dl className="facts"><dt>Geometry</dt><dd>{current.review_status==='confirmed'?'Confirmed':'Provisional'}</dd>
            <dt>Linked asset</dt><dd>{current.linked_asset_id?current.linked_asset_id+' · '+formatLabel(current.mapping_status):'Unmapped'}</dd>
            {currentFinding&&<><dt>Panel median</dt><dd>{describeTemperature(currentFinding.median_temperature_c)}</dd><dt>Nearby reference</dt><dd>{describeTemperature(currentFinding.reference_temperature_c)}</dd>
              <dt>Temperature difference</dt><dd className={currentFinding.candidate?'warm-text':''}>{describeTemperature(currentFinding.delta_t_c,true)}</dd></>}</dl>
          {currentFinding?.data_quality_flags.includes('box_not_confirmed')&&<p className="detail-hint">Confirm this panel box to include it in automatic temperature comparisons.</p>}
          {!readOnly&&<div className="button-row"><button className="button small" onClick={()=>edit(current)}>Edit box</button>
            <button className="button small destructive" onClick={()=>setConfirmDelete(true)}>Remove</button></div>}
          {confirmDelete&&<div role="group" aria-label="Confirm removal" className="notice warning"><p>Remove this box and its saved observation?</p><div className="button-row">
            <button className="button destructive" disabled={busy} onClick={()=>void remove()}>Remove annotation</button><button className="button" onClick={()=>setConfirmDelete(false)}>Cancel</button></div></div>}
        </div>}
        {numeric&&(selectedBox||measurementError)&&<details className="detail-section" open><summary>Region measurements</summary>
          {selectedBox&&<BoundsFields label="Selected region" value={selectedBox} onChange={box=>{setSelectedRegion(box);setRegionEdited(true);}}/>}
          {referenceRegion?<><BoundsFields label="Reference region" value={referenceRegion} onChange={box=>{setReferenceRegion(box);setRegionEdited(true);}}/>
            <button className="button small" onClick={()=>{setReferenceRegion(undefined);setRegionEdited(true);}}>Remove comparison</button></>
            :selectedBox&&<button className="button small" onClick={()=>{setReferenceRegion([.05,.1,.2,.35]);setRegionEdited(true);}}>Enter reference bounds</button>}
          {measurementError&&<p className="notice warning" role="status">{measurementError}</p>}
          {measurement&&<dl className="facts region-facts">{(['minimum','maximum','mean','median'] as const).map(key=><div key={key}><dt>{key}</dt><dd>{measurement.selected[key].toFixed(2)} °{measurement.selected.unit}</dd></div>)}
            <div><dt>Valid / excluded</dt><dd>{measurement.selected.sample_count} / {measurement.selected.excluded_count}</dd></div>
            <div><dt>Region difference</dt><dd>{measurement.delta===null?'No reference':measurement.delta.toFixed(2)+' °'+measurement.selected.unit}</dd></div></dl>}
        </details>}
        {!pending&&current&&<form className="form-stack detail-section" onSubmit={event=>void saveFinding(event)}>
          <h3>Observation</h3>
          <label className="field">Category<select disabled={readOnly} value={category} onChange={event=>setCategory(event.target.value)}>{Object.entries(categories).map(([value,label])=><option key={value} value={value}>{label}</option>)}</select></label>
          <div className="double-fields"><label className="field">Review status<select disabled={readOnly} value={review} onChange={event=>setReview(event.target.value)}>{Object.entries(statuses).map(([value,label])=><option key={value} value={value}>{label}</option>)}</select></label>
          <label className="field">Severity<select disabled={readOnly} value={severity} onChange={event=>setSeverity(event.target.value)}>{['unassigned','low','medium','high'].map(value=><option key={value}>{value}</option>)}</select></label></div>
          <label className="field">Reviewer note<textarea disabled={readOnly} maxLength={4000} value={note} onChange={event=>setNote(event.target.value)} placeholder="Record what you see and any follow-up." rows={3}/></label>
          {!readOnly&&<button className="button primary" disabled={busy||(regionEdited&&!!measurementError)}>Save observation</button>}
        </form>}
        {error&&<p className="notice error" role="alert">{error}</p>}{message&&<p className="notice" role="status">{message}</p>}
        <div className="detail-section detail-links">
          {annotations.length>0&&<a href={apiPath(id,'/export/labels')} className="button small"><Download size={15}/> Label CSV</a>}
          <Link to={inspectionLink('upload',id)}>Manage files <ArrowUpRight size={14}/></Link>
        </div>
      </aside>
    </div>}
  </>;
}
