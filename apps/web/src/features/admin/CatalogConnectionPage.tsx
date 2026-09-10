import { useEffect, useState, type FormEvent } from 'react'
import { apiRequest, ApiError, type AuthView } from '../../shared/api'
import { Link } from '../../shell/router'
import { CatalogNav, CatalogPanel, catalogError, connectionStatus, has,
  type ChangeReceipt, type ConnectionView } from './catalog-shared'

type Form={account_ref:string;project_ref:string;environment:'development'|'test';max_concurrency:string;rate_limit:string;rate_window_seconds:string;spend_cap_minor:string;timeout_seconds:string;allow_fallbacks:boolean;reason:string}
const blank:Form={account_ref:'',project_ref:'',environment:'test',max_concurrency:'1',rate_limit:'1',rate_window_seconds:'60',spend_cap_minor:'0',timeout_seconds:'180',allow_fallbacks:false,reason:''}
const op=()=>crypto.randomUUID()

export function CatalogConnectionPage({auth,connectionId}:{auth:AuthView;connectionId:string}){
  const [view,setView]=useState<ConnectionView|null>(null),[missing,setMissing]=useState(false),[form,setForm]=useState<Form>(blank)
  const [busy,setBusy]=useState(false),[error,setError]=useState(''),[receipt,setReceipt]=useState<ChangeReceipt|null>(null),[operation,setOperation]=useState(op)
  async function load(signal?:AbortSignal){try{const value=await apiRequest<ConnectionView>('/api/v1/admin/catalog/connections/'+connectionId,{signal});if(signal?.aborted)return;setView(value);setMissing(false);if(value.content)setForm(f=>({...f,account_ref:value.content!.account_ref,project_ref:value.content!.project_ref||'',environment:value.content!.environment,max_concurrency:String(value.content!.max_concurrency),rate_limit:String(value.content!.rate_limit),rate_window_seconds:String(value.content!.rate_window_seconds),spend_cap_minor:String(value.content!.spend_cap_minor),timeout_seconds:String(value.content!.timeout_seconds),allow_fallbacks:value.content!.allow_fallbacks}))}catch(r){if(signal?.aborted)return;if(r instanceof ApiError&&r.status===404){setView(null);setMissing(true);return}throw r}}
  useEffect(()=>{const c=new AbortController();void load(c.signal).catch(r=>setError(catalogError(r)));return()=>c.abort()},[connectionId])
  function change<K extends keyof Form>(key:K,value:Form[K]){setForm(f=>({...f,[key]:value}));setReceipt(null);setOperation(op())}
  async function save(e:FormEvent){e.preventDefault();if(busy||!has(auth,'connections.write'))return;setBusy(true);setError('');try{const r=await apiRequest<ChangeReceipt>(`/api/v1/admin/catalog/connections/${connectionId}/draft`,{method:'POST',csrf:auth.csrf_token,data:{operation_id:operation,expected_version:view?.version??0,reason:form.reason,account_ref:form.account_ref,project_ref:form.project_ref||null,environment:form.environment,max_concurrency:Number(form.max_concurrency),rate_limit:Number(form.rate_limit),rate_window_seconds:Number(form.rate_window_seconds),spend_cap_minor:Number(form.spend_cap_minor),currency:'USD',timeout_seconds:Number(form.timeout_seconds),allow_fallbacks:form.allow_fallbacks}});setReceipt(r);setOperation(op());await load()}catch(r){setError(catalogError(r))}finally{setBusy(false)}}
  return <section className="admin-page catalog-page"><header className="page-heading"><p className="eyebrow">CATALOG-001 · A-11</p><h1>Подключение</h1><p>{connectionId} · metadata отдельно от credential и runtime activation.</p></header><CatalogNav auth={auth}/>
    {error&&<p role="alert" className="field-error">{error} <button disabled={busy} onClick={()=>{setError('');void load().catch(r=>setError(catalogError(r)))}}>Обновить</button></p>}
    <CatalogPanel><div className="catalog-heading"><div><h2>{connectionId}</h2><p>{missing?'Новый connection: сохранённой версии ещё нет.':view?connectionStatus(view):'Загрузка…'}</p></div><span className="catalog-badge danger">Runtime disabled</span></div>
      <dl className="summary-list"><div><dt>Provider</dt><dd>openrouter</dd></div><div><dt>Adapter endpoint</dt><dd>{view?.content?.endpoint||'https://openrouter.ai/api/v1/images'}</dd></div><div><dt>Head version</dt><dd>{view?.version??0}</dd></div></dl>
      <p>Endpoint фиксирован серверным adapter-кодом. Поля произвольного URL на этой странице нет.</p></CatalogPanel>
    {has(auth,'connections.write')?<CatalogPanel><h2>Черновик подключения</h2><form className="admin-form catalog-form" onSubmit={save}>
      <label>Provider account reference<input value={form.account_ref} onChange={e=>change('account_ref',e.target.value)} pattern="[A-Za-z0-9_.:-]+" maxLength={120} required/></label>
      <label>Project reference, если есть<input value={form.project_ref} onChange={e=>change('project_ref',e.target.value)} pattern="[A-Za-z0-9_.:-]*" maxLength={120}/></label>
      <label>Environment<select value={form.environment} onChange={e=>change('environment',e.target.value as Form['environment'])}><option value="test">test</option><option value="development">development</option></select></label>
      <div className="catalog-grid"><label>Max concurrency<input type="number" min="0" max="64" step="1" value={form.max_concurrency} onChange={e=>change('max_concurrency',e.target.value)} required/></label>
        <label>Rate limit<input type="number" min="0" max="1000000" step="1" value={form.rate_limit} onChange={e=>change('rate_limit',e.target.value)} required/></label>
        <label>Rate window, сек<input type="number" min="1" max="86400" step="1" value={form.rate_window_seconds} onChange={e=>change('rate_window_seconds',e.target.value)} required/></label>
        <label>Spend cap, minor USD<input type="number" min="0" max="1000000000" step="1" value={form.spend_cap_minor} onChange={e=>change('spend_cap_minor',e.target.value)} required/></label>
        <label>Timeout, сек<input type="number" min="30" max="600" step="1" value={form.timeout_seconds} onChange={e=>change('timeout_seconds',e.target.value)} required/></label></div>
      <label className="catalog-inline"><input type="checkbox" checked={form.allow_fallbacks} onChange={e=>change('allow_fallbacks',e.target.checked)}/>Разрешить fallbacks в metadata</label>
      <label>Основание изменения<textarea value={form.reason} onChange={e=>change('reason',e.target.value)} maxLength={500} required/></label>
      <button className="primary" disabled={busy}>{busy?'Сохраняем…':'Сохранить новую draft revision'}</button></form></CatalogPanel>:<CatalogPanel><p>Редактирование требует `connections.write`.</p></CatalogPanel>}
    {has(auth,'secrets.bind')&&has(auth,'connections.read')&&view&&<CatalogPanel><h2>Credential binding</h2><p>Raw API key здесь не отображается и не вводится. Управление — отдельный write-only metadata flow.</p><Link className="secondary" href={'/admin/credentials/'+connectionId}>Открыть привязку секрета</Link></CatalogPanel>}
    <CatalogPanel><h2>Публикация и proof</h2><p>Connection metadata публикуется только по proof конкретной модели. Выполните offline proof в карточке capability. Даже после публикации runtime остаётся <strong>disabled</strong>.</p><Link href="/admin/models">Перейти к моделям</Link></CatalogPanel>
    {receipt&&<div className="admin-receipt" role="status"><strong>{receipt.action}</strong> · версия {receipt.result_version} · операция {receipt.operation_id}</div>}
    <p><Link href="/admin/providers">← К провайдерам</Link></p></section>
}
