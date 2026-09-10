import { useEffect, useState } from 'react'
import { apiRequest, type AuthView } from '../../shared/api'
import { Link } from '../../shell/router'
import { CatalogModelPage } from './CatalogModelPage'
import { CatalogConnectionPage } from './CatalogConnectionPage'
import { CatalogCredentialPage } from './CatalogCredentialPage'
import { CatalogNav, CatalogPanel, catalogError, connectionStatus, has, statusLabel,
  type CapabilityList, type ConnectionList, type ProviderList } from './catalog-shared'
import './catalog.css'

export function isCatalogPath(path: string) {
  return path === '/admin/models' || path.startsWith('/admin/models/')
    || path === '/admin/providers' || path.startsWith('/admin/providers/')
    || path === '/admin/credentials' || path.startsWith('/admin/credentials/')
}

function go(path: string) {
  window.history.pushState(null, '', path)
  window.dispatchEvent(new Event('izo:navigate'))
  window.scrollTo({ top: 0 })
}

function Models({ auth }: { auth: AuthView }) {
  const [data, setData] = useState<CapabilityList | null>(null)
  const [error, setError] = useState('')
  const [id, setId] = useState('')
  useEffect(() => {
    const controller = new AbortController()
    apiRequest<CapabilityList>('/api/v1/admin/catalog/models', { signal: controller.signal })
      .then(setData).catch(reason => { if (!controller.signal.aborted) setError(catalogError(reason)) })
    return () => controller.abort()
  }, [])
  return <><header className="page-heading"><p className="eyebrow">CATALOG-001 · A-08</p><h1>Модели</h1>
    <p>Версии capability и цены платформы. Публикация metadata не включает внешний AI.</p></header>
    <CatalogNav auth={auth} />{error && <p role="alert" className="field-error">{error}</p>}
    <CatalogPanel><div className="catalog-heading"><div><h2>Каталог capability</h2><p>Новые записи по умолчанию не доступны runtime.</p></div>
      {has(auth, 'catalog.write') && has(auth, 'pricing.write') && <form className="catalog-create" onSubmit={event => {
        event.preventDefault(); const value=id.trim().toLowerCase(); if (/^[a-z0-9][a-z0-9._-]{0,79}$/.test(value)) go('/admin/models/'+value)
      }}><label>Новый capability ID<input value={id} onChange={e=>setId(e.target.value)} placeholder="openrouter.image.v1" pattern="[a-z0-9][a-z0-9._-]{0,79}" required /></label>
        <button>Открыть черновик</button></form>}</div>
      {!data && !error && <p role="status">Загружаем каталог…</p>}
      {data && !data.items.length && <p>В каталоге пока нет моделей.</p>}
      {data && data.items.length>0 && <div className="catalog-cards">{data.items.map(item => <Link className="catalog-card" href={'/admin/models/'+item.capability_id} key={item.capability_id}>
        <strong>{item.content?.name || item.capability_id}</strong><span>{item.capability_id}</span>
        <span className="catalog-badge">{statusLabel(item)}</span><small>Версия {item.version} · live: нет</small></Link>)}</div>}
    </CatalogPanel></>
}

function Providers({ auth }: { auth: AuthView }) {
  const [providers, setProviders] = useState<ProviderList | null>(null)
  const [connections, setConnections] = useState<ConnectionList | null>(null)
  const [error, setError] = useState('')
  const [id, setId] = useState('')
  useEffect(() => {
    const controller = new AbortController()
    Promise.all([
      apiRequest<ProviderList>('/api/v1/admin/catalog/providers', { signal: controller.signal }),
      apiRequest<ConnectionList>('/api/v1/admin/catalog/connections', { signal: controller.signal }),
    ]).then(([p,c])=>{setProviders(p);setConnections(c)}).catch(reason=>{if(!controller.signal.aborted)setError(catalogError(reason))})
    return ()=>controller.abort()
  }, [])
  return <><header className="page-heading"><p className="eyebrow">CATALOG-001 · A-10</p><h1>Провайдеры</h1>
    <p>Разрешённые adapter и connection metadata. Endpoint задаётся кодом адаптера, а не полем браузера.</p></header>
    <CatalogNav auth={auth} />{error && <p role="alert" className="field-error">{error}</p>}
    {providers?.items.map(provider => <CatalogPanel key={provider.provider_id}><div className="catalog-heading"><div><h2>{provider.provider_id}</h2>
      <p>{provider.adapter_id}</p></div><span className="catalog-badge danger">Live выключен</span></div>
      <dl className="summary-list"><div><dt>Endpoint</dt><dd>{provider.endpoint}</dd></div><div><dt>Live enabled</dt><dd>{provider.live_enabled?'Да':'Нет'}</dd></div></dl></CatalogPanel>)}
    <CatalogPanel><div className="catalog-heading"><div><h2>Подключения</h2><p>Draft/published metadata; runtime остаётся disabled.</p></div>
      {has(auth,'connections.write') && <form className="catalog-create" onSubmit={event=>{event.preventDefault();const value=id.trim().toLowerCase();if(/^[a-z0-9][a-z0-9_.:-]{0,79}$/.test(value))go('/admin/providers/openrouter/connections/'+value)}}>
        <label>Новый connection ID<input value={id} onChange={e=>setId(e.target.value)} placeholder="openrouter-primary" pattern="[a-z0-9][a-z0-9_.:-]{0,79}" required /></label><button>Открыть черновик</button></form>}</div>
      {!connections && !error && <p role="status">Загружаем подключения…</p>}
      {connections && !connections.items.length && <p>Подключений пока нет.</p>}
      {connections && <div className="catalog-cards">{connections.items.map(item=><Link className="catalog-card" href={'/admin/providers/openrouter/connections/'+item.connection_id} key={item.connection_id}>
        <strong>{item.connection_id}</strong><span>{item.content?.account_ref || 'metadata не задана'}</span><span className="catalog-badge">{connectionStatus(item)}</span><small>Версия {item.version}</small></Link>)}</div>}
    </CatalogPanel></>
}

function Credentials({ auth }: { auth: AuthView }) {
  const [connections,setConnections]=useState<ConnectionList|null>(null)
  const [error,setError]=useState('')
  useEffect(()=>{const c=new AbortController();apiRequest<ConnectionList>('/api/v1/admin/catalog/connections',{signal:c.signal}).then(setConnections).catch(r=>{if(!c.signal.aborted)setError(catalogError(r))});return()=>c.abort()},[])
  return <><header className="page-heading"><p className="eyebrow">CATALOG-001 · A-12</p><h1>Привязки секретов</h1>
    <p>Здесь хранятся только ссылки и fingerprint. Значение API-ключа браузер не принимает и сервер не возвращает.</p></header><CatalogNav auth={auth}/>
    {error&&<p role="alert" className="field-error">{error}</p>}<CatalogPanel><h2>Подключения</h2>
      {!connections&&!error&&<p role="status">Загружаем подключения…</p>}
      {connections&&!connections.items.length&&<p>Сначала создайте connection metadata.</p>}
      {connections&&<div className="catalog-cards">{connections.items.map(item=><Link className="catalog-card" href={'/admin/credentials/'+item.connection_id} key={item.connection_id}>
        <strong>{item.connection_id}</strong><span>{item.content?.account_ref || 'нет draft metadata'}</span><small>Управлять write-only привязкой</small></Link>)}</div>}
    </CatalogPanel></>
}

export function CatalogPage({path}:{path:string}) {
  const [auth,setAuth]=useState<AuthView|null>(null),[error,setError]=useState('')
  useEffect(()=>{const c=new AbortController();apiRequest<AuthView>('/api/v1/auth/me',{signal:c.signal}).then(setAuth).catch(r=>{if(!c.signal.aborted)setError(catalogError(r))});return()=>c.abort()},[path])
  if(error)return <section className="admin-page"><header className="page-heading"><h1>Администрирование каталога</h1></header><p role="alert" className="field-error">{error}</p></section>
  if(!auth)return <section className="admin-page"><p role="status">Проверяем серверную сессию…</p></section>
  const model=/^\/admin\/models\/([a-z0-9._-]+)$/.exec(path)
  const connection=/^\/admin\/providers\/openrouter\/connections\/([a-z0-9_.:-]+)$/.exec(path)
  const credential=/^\/admin\/credentials\/([a-z0-9_.:-]+)$/.exec(path)
  if(model)return <CatalogModelPage auth={auth} capabilityId={model[1]}/>
  if(connection)return <CatalogConnectionPage auth={auth} connectionId={connection[1]}/>
  if(credential)return <CatalogCredentialPage auth={auth} connectionId={credential[1]}/>
  if(path==='/admin/models')return <Models auth={auth}/>
  if(path==='/admin/providers')return <Providers auth={auth}/>
  if(path==='/admin/credentials')return has(auth,'secrets.bind')&&has(auth,'connections.read')?<Credentials auth={auth}/>:<section className="admin-page"><CatalogNav auth={auth}/><p role="alert">Нет полномочия на metadata привязок.</p></section>
  return <section className="admin-page"><p role="alert">Этот экран каталога не реализован.</p></section>
}
