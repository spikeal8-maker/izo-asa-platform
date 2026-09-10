import { useEffect, useState, type FormEvent } from 'react'
import { apiRequest, ApiError, type AuthView } from '../../shared/api'
import { Link } from '../../shell/router'
import { CatalogNav, CatalogPanel, catalogError, has, type ChangeReceipt, type ConnectionView, type CredentialView } from './catalog-shared'

type Source='env'|'secret_file'|'secret_manager'
const op=()=>crypto.randomUUID()
const refFor=(source:Source)=>source==='env'?'IZO_OPENROUTER_API_KEY':source==='secret_file'?'openrouter/primary':'vault/izo/openrouter/primary'

export function CatalogCredentialPage({auth,connectionId}:{auth:AuthView;connectionId:string}){
  const [connection,setConnection]=useState<ConnectionView|null>(null),[credential,setCredential]=useState<CredentialView|null>(null)
  const [source,setSource]=useState<Source>('env'),[secretRef,setSecretRef]=useState(refFor('env'))
  const [bindPassword,setBindPassword]=useState(''),[bindReason,setBindReason]=useState('')
  const [revokePassword,setRevokePassword]=useState(''),[revokeReason,setRevokeReason]=useState('')
  const [busy,setBusy]=useState(''),[error,setError]=useState(''),[receipt,setReceipt]=useState<ChangeReceipt|null>(null)
  const [bindOp,setBindOp]=useState(op),[revokeOp,setRevokeOp]=useState(op)
  const allowed=has(auth,'connections.read')&&has(auth,'connections.write')&&has(auth,'secrets.bind')
  async function load(signal?:AbortSignal){const c=await apiRequest<ConnectionView>('/api/v1/admin/catalog/connections/'+connectionId,{signal});if(signal?.aborted)return;setConnection(c);try{const v=await apiRequest<CredentialView>(`/api/v1/admin/catalog/connections/${connectionId}/credential`,{signal});if(!signal?.aborted)setCredential(v)}catch(r){if(r instanceof ApiError&&r.status===404){setCredential(null);return}throw r}}
  useEffect(()=>{if(!allowed)return;const c=new AbortController();void load(c.signal).catch(r=>setError(catalogError(r)));return()=>c.abort()},[connectionId,allowed])
  function mutate(){setReceipt(null);setBindOp(op())}
  async function bind(e:FormEvent){e.preventDefault();if(!allowed||!connection||busy)return;setBusy('bind');setError('');setReceipt(null);try{const v=await apiRequest<CredentialView>(`/api/v1/admin/catalog/connections/${connectionId}/credentials`,{method:'POST',csrf:auth.csrf_token,data:{operation_id:bindOp,expected_version:connection.version,reason:bindReason,source_type:source,secret_ref:secretRef,environment:connection.content?.environment??'test',account_ref:connection.content?.account_ref??'',project_ref:connection.content?.project_ref??null,current_password:bindPassword}});setCredential(v);setBindOp(op());setBindPassword('');await load()}catch(r){setError(catalogError(r));setBindPassword('')}finally{setBusy('')}}
  async function revoke(e:FormEvent){e.preventDefault();if(!allowed||!connection||!credential||busy)return;setBusy('revoke');setError('');setReceipt(null);try{const v=await apiRequest<ChangeReceipt>(`/api/v1/admin/catalog/connections/${connectionId}/credentials/revoke`,{method:'POST',csrf:auth.csrf_token,data:{operation_id:revokeOp,expected_version:connection.version,reason:revokeReason,current_password:revokePassword}});setReceipt(v);setRevokeOp(op());setRevokePassword('');await load()}catch(r){setError(catalogError(r));setRevokePassword('')}finally{setBusy('')}}
  if(!allowed)return <section className="admin-page catalog-page"><header className="page-heading"><p className="eyebrow">CATALOG-001 · A-12 / AD-04</p><h1>Привязка секрета</h1></header><CatalogNav auth={auth}/><p role="alert">Нужны отдельные `connections.read`, `connections.write` и `secrets.bind`.</p></section>
  return <section className="admin-page catalog-page"><header className="page-heading"><p className="eyebrow">CATALOG-001 · A-12 / AD-04</p><h1>Привязка секрета</h1><p>{connectionId} · только logical reference и fingerprint.</p></header><CatalogNav auth={auth}/>
    {error&&<p role="alert" className="field-error">{error} <button disabled={!!busy} onClick={()=>{setError('');void load().catch(r=>setError(catalogError(r)))}}>Обновить</button></p>}
    <CatalogPanel><h2>Текущая metadata</h2>{!connection&&!error&&<p role="status">Загружаем…</p>}
      {connection&&<dl className="summary-list"><div><dt>Connection version</dt><dd>{connection.version}</dd></div><div><dt>Environment</dt><dd>{connection.content?.environment||'—'}</dd></div><div><dt>Account</dt><dd>{connection.content?.account_ref||'—'}</dd></div><div><dt>Project</dt><dd>{connection.content?.project_ref||'—'}</dd></div></dl>}
      {credential?<dl className="summary-list"><div><dt>Binding version</dt><dd>{credential.version}</dd></div><div><dt>Source</dt><dd>{credential.source_type}</dd></div><div><dt>Reference fingerprint</dt><dd data-testid="credential-fingerprint">{credential.reference_fingerprint.slice(0,16)}…</dd></div><div><dt>State</dt><dd>{credential.state}</dd></div></dl>:connection&&<p>Действующей привязки нет.</p>}
      <p className="catalog-warning"><strong>Значение API-ключа не вводится в эту форму.</strong> `secret_ref` — разрешённое логическое имя источника. Runtime resolver и live activation пока отсутствуют.</p></CatalogPanel>
    {connection&&<CatalogPanel><h2>{credential?'Ротация metadata':'Новая привязка metadata'}</h2><form className="admin-form catalog-form" onSubmit={bind}>
      <label>Источник<select value={source} onChange={e=>{const next=e.target.value as Source;setSource(next);setSecretRef(refFor(next));mutate()}}><option value="env">env</option><option value="secret_file">secret_file</option><option value="secret_manager">secret_manager</option></select></label>
      <label>Logical secret reference<input value={secretRef} onChange={e=>{setSecretRef(e.target.value);mutate()}} maxLength={200} required/></label>
      <small>Допустимы только allowlisted формы: `IZO_OPENROUTER_API_KEY`, `openrouter/name` или `vault/izo/openrouter/name`.</small>
      <label>Основание привязки<textarea value={bindReason} onChange={e=>{setBindReason(e.target.value);mutate()}} maxLength={500} required/></label>
      <label>Текущий пароль для привязки<input type="password" autoComplete="current-password" value={bindPassword} onChange={e=>setBindPassword(e.target.value)} required/></label>
      <button className="primary" disabled={!!busy}>{busy==='bind'?'Проверяем и сохраняем…':credential?'Привязать новую версию':'Создать привязку'}</button></form></CatalogPanel>}
    {connection&&credential&&<CatalogPanel><h2>Отозвать текущую привязку</h2><p>Новые submissions не должны использовать revoked credential. Это не удаляет историю.</p><form className="admin-form" onSubmit={revoke}>
      <label>Основание отзыва<input value={revokeReason} onChange={e=>{setRevokeReason(e.target.value);setRevokeOp(op())}} maxLength={500} required/></label>
      <label>Текущий пароль для отзыва<input type="password" autoComplete="current-password" value={revokePassword} onChange={e=>setRevokePassword(e.target.value)} required/></label>
      <button className="danger-button" disabled={!!busy}>{busy==='revoke'?'Отзываем…':'Отозвать binding'}</button></form></CatalogPanel>}
    {receipt&&<div className="admin-receipt" role="status"><strong>{receipt.action}</strong> · версия {receipt.result_version}</div>}
    <p><Link href="/admin/credentials">← К привязкам</Link> · <Link href={'/admin/providers/openrouter/connections/'+connectionId}>Подключение</Link></p></section>
}
