import { useEffect, useState, type FormEvent } from 'react'
import { apiRequest, ApiError, type AuthView } from '../../shared/api'
import { Link } from '../../shell/router'
import { CatalogNav, CatalogPanel, catalogError, connectionStatus, has, resolutions, statusLabel,
  type CapabilityView, type ChangeReceipt, type ConnectionView, type ProofView, type Resolution } from './catalog-shared'

type Form = { name:string; help:string; model_id:string; connection_id:string; resolutions:Resolution[]; price_credits:string; reason:string }
const blank:Form={name:'',help:'',model_id:'',connection_id:'openrouter-primary',resolutions:['512'],price_credits:'',reason:''}
const op=()=>crypto.randomUUID()

export function CatalogModelPage({auth,capabilityId}:{auth:AuthView;capabilityId:string}) {
  const [view,setView]=useState<CapabilityView|null>(null),[missing,setMissing]=useState(false)
  const [form,setForm]=useState<Form>(blank),[proof,setProof]=useState<ProofView|null>(null)
  const [proofConnection,setProofConnection]=useState<ConnectionView|null>(null)
  const [busy,setBusy]=useState(''),[error,setError]=useState(''),[receipt,setReceipt]=useState<ChangeReceipt|null>(null)
  const [saveOp,setSaveOp]=useState(op),[proofOp,setProofOp]=useState(op),[connPubOp,setConnPubOp]=useState(op),[modelPubOp,setModelPubOp]=useState(op),[disableOp,setDisableOp]=useState(op)

  async function load(signal?:AbortSignal) {
    try {
      const value=await apiRequest<CapabilityView>('/api/v1/admin/catalog/models/'+capabilityId,{signal})
      if(signal?.aborted)return
      setView(value);setMissing(false)
      if(value.content)setForm(f=>({...f,name:value.content!.name,help:value.content!.help,model_id:value.content!.model_id,
        connection_id:value.content!.connection_id,resolutions:[...value.content!.resolutions] as Resolution[],price_credits:String(value.content!.price_credits)}))
    } catch(reason) {
      if(signal?.aborted)return
      if(reason instanceof ApiError&&reason.status===404){setView(null);setMissing(true);return}
      throw reason
    }
  }
  useEffect(()=>{const c=new AbortController();setError('');void load(c.signal).catch(r=>setError(catalogError(r)));return()=>c.abort()},[capabilityId])
  function change<K extends keyof Form>(key:K,value:Form[K]) { setForm(f=>({...f,[key]:value}));setProof(null);setReceipt(null);setSaveOp(op());setProofOp(op()) }
  const canWrite=has(auth,'catalog.write')&&has(auth,'pricing.write')
  const canProof=canWrite&&has(auth,'connections.write')
  const version=view?.version??0

  async function save(event:FormEvent) {
    event.preventDefault();if(!canWrite||busy)return;setBusy('save');setError('');setReceipt(null)
    try {
      const result=await apiRequest<ChangeReceipt>(`/api/v1/admin/catalog/models/${capabilityId}/draft`,{method:'POST',csrf:auth.csrf_token,data:{
        operation_id:saveOp,expected_version:version,reason:form.reason,name:form.name,help:form.help,adapter_id:'openrouter.images.v1',
        model_id:form.model_id,connection_id:form.connection_id,resolutions:form.resolutions,price_credits:Number(form.price_credits)}})
      setReceipt(result);setSaveOp(op());setProof(null);await load()
    } catch(r){setError(catalogError(r))}finally{setBusy('')}
  }
  async function makeProof() {
    if(!canProof||busy||!view?.draft)return;setBusy('proof');setError('');setReceipt(null)
    try {
      const connection=await apiRequest<ConnectionView>('/api/v1/admin/catalog/connections/'+form.connection_id)
      const value=await apiRequest<ProofView>(`/api/v1/admin/catalog/models/${capabilityId}/proof`,{method:'POST',csrf:auth.csrf_token,data:{
        operation_id:proofOp,expected_version:view.version,reason:form.reason,connection_id:form.connection_id,connection_version:connection.version}})
      setProof(value);setProofConnection(connection);setProofOp(op())
    } catch(r){setError(catalogError(r))}finally{setBusy('')}
  }
  async function publishConnection() {
    if(!proof||!proofConnection?.draft||busy||!has(auth,'connections.write'))return;setBusy('connection-publish');setError('')
    try {
      const r=await apiRequest<ChangeReceipt>(`/api/v1/admin/catalog/connections/${proof.connection_id}/publish`,{method:'POST',csrf:auth.csrf_token,data:{operation_id:connPubOp,expected_version:proofConnection.version,proof_id:proof.proof_id,reason:form.reason}})
      setReceipt(r);setConnPubOp(op());setProofConnection(await apiRequest<ConnectionView>('/api/v1/admin/catalog/connections/'+proof.connection_id))
    } catch(x){setError(catalogError(x))}finally{setBusy('')}
  }
  async function publishModel() {
    if(!proof||busy||!canWrite||!view?.draft)return;setBusy('model-publish');setError('')
    try {
      const r=await apiRequest<ChangeReceipt>(`/api/v1/admin/catalog/models/${capabilityId}/publish`,{method:'POST',csrf:auth.csrf_token,data:{operation_id:modelPubOp,expected_version:view.version,proof_id:proof.proof_id,reason:form.reason}})
      setReceipt(r);setModelPubOp(op());setProof(null);await load()
    } catch(x){setError(catalogError(x))}finally{setBusy('')}
  }
  async function disable() {
    if(!view?.published||busy||!has(auth,'catalog.write'))return;setBusy('disable');setError('')
    try {
      const r=await apiRequest<ChangeReceipt>(`/api/v1/admin/catalog/models/${capabilityId}/disable`,{method:'POST',csrf:auth.csrf_token,data:{operation_id:disableOp,expected_version:view.version,reason:form.reason}})
      setReceipt(r);setDisableOp(op());setProof(null);await load()
    } catch(x){setError(catalogError(x))}finally{setBusy('')}
  }

  return <section className="admin-page catalog-page"><header className="page-heading"><p className="eyebrow">CATALOG-001 · A-09 / AD-03</p>
    <h1>{view?.content?.name||form.name||capabilityId}</h1><p>{capabilityId} · внешний runtime этим экраном не включается.</p></header><CatalogNav auth={auth}/>
    {error&&<p role="alert" className="field-error">{error} <button type="button" disabled={!!busy} onClick={()=>{setError('');void load().catch(r=>setError(catalogError(r)))}}>Обновить</button></p>}
    <CatalogPanel><div className="catalog-heading"><div><h2>Состояние</h2><p>{missing?'Новая capability: сохранённой версии ещё нет.':view?statusLabel(view):'Загрузка…'}</p></div>
      <span className="catalog-badge danger">Live unavailable</span></div>
      {view&&<dl className="summary-list"><div><dt>Версия head</dt><dd>{view.version}</dd></div><div><dt>Draft hash</dt><dd>{view.draft?.content_hash||'—'}</dd></div>
        <div><dt>Published hash</dt><dd>{view.published?.content_hash||'—'}</dd></div><div><dt>Runtime</dt><dd>{view.runtime_available?'доступен':'выключен'}</dd></div></dl>}
    </CatalogPanel>
    {canWrite?<CatalogPanel><h2>Черновик модели</h2><form className="admin-form catalog-form" onSubmit={save}>
      <label>Название<input value={form.name} onChange={e=>change('name',e.target.value)} minLength={1} maxLength={120} required/></label>
      <label>Подсказка<textarea value={form.help} onChange={e=>change('help',e.target.value)} maxLength={2000}/></label>
      <label>Adapter<input value="openrouter.images.v1" readOnly/></label>
      <label>Model ID<input value={form.model_id} onChange={e=>change('model_id',e.target.value)} placeholder="provider/model" pattern="[A-Za-z0-9_.:-]{1,120}/[A-Za-z0-9_.:-]{1,160}" required/></label>
      <label>Connection ID<input value={form.connection_id} onChange={e=>change('connection_id',e.target.value)} pattern="[a-z0-9][a-z0-9_.:-]{0,79}" required/></label>
      <fieldset><legend>Разрешения</legend><div className="catalog-checks">{resolutions.map(item=><label key={item}><input type="checkbox" checked={form.resolutions.includes(item)} onChange={e=>change('resolutions',e.target.checked?[...form.resolutions,item]:form.resolutions.filter(x=>x!==item))}/>{item}</label>)}</div></fieldset>
      <label>Цена платформы, баллы<input type="number" min="0" max="1000000" step="1" value={form.price_credits} onChange={e=>change('price_credits',e.target.value)} required/></label>
      <label>Основание изменения<textarea value={form.reason} onChange={e=>change('reason',e.target.value)} maxLength={500} required/></label>
      <button className="primary" disabled={!!busy}>{busy==='save'?'Сохраняем…':'Сохранить новую draft revision'}</button></form></CatalogPanel>
      :<CatalogPanel><p>Редактирование требует `catalog.write` и отдельного `pricing.write`. Просмотр не повышает полномочия.</p></CatalogPanel>}
    {view?.draft&&<CatalogPanel className="catalog-proof"><h2>Offline contract proof</h2><p>Проверяет hashes, лимиты и credential scope. <strong>Сеть и AI не вызываются.</strong></p>
      {!canProof?<p>Для proof нужны `catalog.write`, `pricing.write` и `connections.write`.</p>:<button className="primary" disabled={!!busy||!form.reason.trim()} onClick={()=>void makeProof()}>{busy==='proof'?'Проверяем…':'Проверить контракт без сети'}</button>}
      {proof&&<div className="catalog-receipt" role="status"><strong>Proof создан</strong><dl className="summary-list"><div><dt>ID</dt><dd>{proof.proof_id}</dd></div>
        <div><dt>Network called</dt><dd>{proof.network_called?'Да':'Нет'}</dd></div><div><dt>Live ready</dt><dd>{proof.live_ready?'Да':'Нет'}</dd></div>
        <div><dt>Credential version</dt><dd>{proof.credential_version}</dd></div></dl>
        {proofConnection&&<><p>Подключение: {connectionStatus(proofConnection)}</p>
          {proofConnection.draft&&has(auth,'connections.write')&&<button disabled={!!busy} onClick={()=>void publishConnection()}>Опубликовать metadata подключения</button>}
          {(proofConnection.published&&!proofConnection.draft)&&<p>Connection metadata опубликована; runtime всё равно disabled.</p>}
          <button className="primary" disabled={!!busy||!!proofConnection.draft} onClick={()=>void publishModel()}>Опубликовать metadata модели</button></>}
      </div>}
    </CatalogPanel>}
    {view?.published&&has(auth,'catalog.write')&&<CatalogPanel><h2>Отключить для новых публикаций</h2><p>История revision не удаляется; уже принятые jobs сохраняют snapshot.</p>
      <button className="danger-button" disabled={!!busy||!form.reason.trim()} onClick={()=>void disable()}>{busy==='disable'?'Отключаем…':'Отключить published pointer'}</button></CatalogPanel>}
    {receipt&&<div className="admin-receipt" role="status"><strong>{receipt.action}</strong> · версия {receipt.result_version} · операция {receipt.operation_id}</div>}
    <p><Link href="/admin/models">← К моделям</Link></p>
  </section>
}
