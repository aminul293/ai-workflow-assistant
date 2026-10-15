'use client';
import {useState} from 'react';
export default function Login(){
 const [username,setUsername]=useState('');const [password,setPassword]=useState('');const [error,setError]=useState('');const [busy,setBusy]=useState(false);
 async function submit(e:React.FormEvent){e.preventDefault();setBusy(true);setError('');try{
 const r=await fetch('/api/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username,password})});
 if(!r.ok){setError('Sign-in failed. Check credentials.');return;}window.location.assign('/');
 }catch{setError('Sign-in unavailable.')}finally{setBusy(false)}}
 return <main style={{maxWidth:400,margin:'12vh auto',padding:24}}><h1>AI Workflow Assistant</h1><p>Private prototype sign-in</p><form onSubmit={submit} style={{display:'grid',gap:14}}><label>Username<input autoComplete="username" value={username} onChange={e=>setUsername(e.target.value)} required /></label><label>Password<input type="password" autoComplete="current-password" value={password} onChange={e=>setPassword(e.target.value)} required /></label><button disabled={busy} type="submit">{busy?'Signing in…':'Sign in'}</button>{error&&<p role="alert">{error}</p>}</form></main>;
}