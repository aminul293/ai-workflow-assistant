'use client';
import {useRef,useState} from 'react';
import {apiErrorMessage,validateDraft,validateInquiry} from '../lib/preview-inputs.mjs';

export function FictionalInquiryForm({onCreated}:{onCreated:()=>Promise<void>}) {
  const [sender,setSender]=useState('demo@sample.test');
  const [subject,setSubject]=useState('');
  const [body,setBody]=useState('');
  const [ack,setAck]=useState(false);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState('');
  const [notice,setNotice]=useState('');
  // Keep the same identifier on retry: a lost response must not create a duplicate.
  const sourceId=useRef('');
  const submitting=useRef(false);
  async function submit(event:React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if(submitting.current)return;
    const input={sender,subject,body,synthetic_ack:ack};
    const invalid=validateInquiry(input);
    setNotice('');setError(invalid);
    if(invalid)return;
    submitting.current=true;setBusy(true);
    try {
      if(!sourceId.current)sourceId.current='manual-'+crypto.randomUUID();
      const response=await fetch('/api/proxy/api/inbox/fictional',{
        method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({...input,source_id:sourceId.current})
      });
      if(!response.ok)throw new Error(apiErrorMessage(await response.json()));
      // Consume the response before resetting the form to expose malformed responses.
      const saved=await response.json();
      if(typeof saved.id!=='string')throw new Error('Could not confirm saving. Retry with the same text.');
      sourceId.current='';setSubject('');setBody('');setAck(false);
      setNotice('Fictional inquiry saved. Find it below and select Process.');
      await onCreated();
    } catch(e) {
      setError(e instanceof Error?e.message:'Save failed. Retry with the same text.');
    } finally {submitting.current=false;setBusy(false);}
  }
  return <section className="panel inquiry-panel" aria-labelledby="new-inquiry-title">
    <h2 id="new-inquiry-title">Create a fictional inquiry</h2>
    <p>Try a different request. Do not enter real names, contact details, customer messages or company information.</p>
    <form onSubmit={submit} className="inquiry-form" aria-label="Create fictional inquiry">
      <label htmlFor="fictional-sender">Fictional sender (.test address)</label>
      <input id="fictional-sender" value={sender} onChange={e=>setSender(e.target.value)} maxLength={255} required disabled={busy} autoComplete="off" inputMode="email" autoCapitalize="none" spellCheck={false}/>
      <label htmlFor="fictional-subject">Subject</label>
      <input id="fictional-subject" value={subject} onChange={e=>setSubject(e.target.value)} maxLength={255} required disabled={busy} autoComplete="off"/>
      <label htmlFor="fictional-body">Inquiry text</label>
      <textarea id="fictional-body" value={body} onChange={e=>setBody(e.target.value)} maxLength={10000} required disabled={busy} rows={5} aria-describedby="inquiry-limit"/>
      <small id="inquiry-limit">{body.length.toLocaleString()} / 10,000 characters</small>
      <label className="acknowledgement"><input type="checkbox" checked={ack} onChange={e=>setAck(e.target.checked)} required disabled={busy}/>I confirm this inquiry is fictional and contains no real personal or company data.</label>
      <button className="primary" type="submit" disabled={busy}>{busy?'Saving...':'Add fictional inquiry'}</button>
      {error&&<p role="alert">{error}</p>}
      {notice&&<p className="form-success" role="status">{notice}</p>}
    </form>
  </section>;
}

type Approval={id:string;draft:string;decision:string};
type EditorProps={approval:Approval;title:string;value:string;busy:boolean;onChange:(text:string)=>void;onDecision:(decision:'approved'|'rejected')=>Promise<void>};
export function ApprovalEditor({approval,title,value,busy,onChange,onDecision}:EditorProps) {
  const pending=approval.decision==='pending';
  const changed=value!==approval.draft;
  const invalid=validateDraft(value);
  return <article className="record approval-editor" aria-label={title}>
    <div className="approval-copy"><span className="tag">{approval.decision}</span><h3>{title}</h3>
      {pending?<><label htmlFor={'draft-'+approval.id}>Response draft</label>
        <textarea id={'draft-'+approval.id} value={value} onChange={e=>onChange(e.target.value)} maxLength={2000} rows={7} disabled={busy} aria-invalid={Boolean(invalid)} aria-describedby={'draft-help-'+approval.id}/>
        <small id={'draft-help-'+approval.id}>{value.length} / 2,000 characters. {invalid||'Edits are saved when you approve; reloading discards unsaved edits.'}</small>
        {changed&&<p className="edit-state">Unsaved edits</p>}</>:<p className="draft">{approval.draft}</p>}
    </div>
    {pending&&<div className="actions">
      {changed&&<button type="button" disabled={busy} onClick={()=>onChange(approval.draft)}>Discard edits</button>}
      <button type="button" disabled={busy} onClick={()=>void onDecision('rejected')}>Reject</button>
      <button className="primary" type="button" disabled={busy||Boolean(invalid)} onClick={()=>void onDecision('approved')}>Approve</button>
    </div>}
  </article>;
}
