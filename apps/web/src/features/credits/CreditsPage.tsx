import { useEffect, useState } from 'react'
import type { components } from '../../shared/api.generated'
import { apiRequest, ApiError } from '../../shared/api'
import { Link } from '../../shell/router'
import '../../shared/ui/records.css'

type Credits = components['schemas']['Overview']
const names: Record<string,string> = {grant:'Начисление',reserve:'Резерв',settle:'Списание',release:'Освобождение резерва'}

export function CreditsPage() {
  const [data,setData]=useState<Credits|null>(null)
  const [error,setError]=useState('')
  const [version,setVersion]=useState(0)
  const [busy,setBusy]=useState(false)
  const [before,setBefore]=useState<number|null>(null)
  useEffect(()=>{
    const controller=new AbortController()
    setBusy(true);setError('');setData(null)
    apiRequest<Credits>('/api/v1/credits'+(before?'?before='+before:''),{signal:controller.signal})
      .then(value=>{if(!controller.signal.aborted)setData(value)})
      .catch(reason=>{if(!controller.signal.aborted)setError(reason instanceof ApiError&&reason.status===401
        ?'Войдите, чтобы увидеть свой баланс.':'Серверный баланс недоступен. Демо-значение не подставляется.')})
      .finally(()=>{if(!controller.signal.aborted)setBusy(false)})
    return()=>controller.abort()
  },[before,version])
  return <section className="credits-page"><header className="page-heading"><p className="eyebrow">МОЙ СЕРВЕРНЫЙ СЧЁТ</p>
    <h1>Баллы</h1><p>Серверный журнал. Студия резервирует эти баллы при подтверждении задания; окончательное списание выполняет сервер.</p></header>
    <p><Link href="/account">Аккаунт</Link> · <Link href="/login">Вход</Link></p>
    {busy&&<p role="status">Получаем баланс…</p>}{error&&<p className="field-error" role="alert">{error}
      <button disabled={busy} onClick={()=>setVersion(v=>v+1)}>Повторить</button></p>}
    {data&&<div className="admin-panel"><dl className="summary-list">
      <div><dt>Доступно</dt><dd data-testid="own-available">{data.balance.available}</dd></div>
      <div><dt>В резерве</dt><dd>{data.balance.reserved}</dd></div><div><dt>Остаток до резервов</dt><dd>{data.balance.balance}</dd></div></dl>
      <h2>История операций</h2><ul className="admin-history">{data.entries.map(item=><li key={item.entry_id}>
        <div><strong>{names[item.kind]??item.kind}</strong><p>{new Date(item.created_at*1000).toLocaleString('ru-RU')} · {item.reason}</p></div>
        <span>{item.balance_delta>0?'+':''}{item.balance_delta}{item.reserved_delta!==0?' · резерв '+item.reserved_delta:''}</span>
      </li>)}</ul>{!data.entries.length&&<p>Начислений и списаний пока нет.</p>}
      <div className="admin-links">{before&&<button onClick={()=>setBefore(null)}>Последние операции</button>}
        {data.next_before&&<button onClick={()=>setBefore(data.next_before)}>Более ранние операции</button>}
        <button onClick={()=>setVersion(v=>v+1)}>Обновить баланс</button></div>
    </div>}
  </section>
}
