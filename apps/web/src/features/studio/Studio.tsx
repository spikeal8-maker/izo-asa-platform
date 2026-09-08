import { useState } from 'react'
import { Dialog } from '../../shared/ui/Dialog'
import { Icon, type IconName } from '../../shared/ui/Icon'
import { Link } from '../../shell/router'
import { useDemo } from '../prototype/DemoState'
import { aspects, models } from '../prototype/demo'
import { ResultPanel } from './ResultPanel'
import { UploadBox } from './UploadBox'
import './studio.css'

const directions: { title: string; href: string; icon: IconName }[] = [
  { title: 'Изображение', href: '/image', icon: 'image' }, { title: 'Видео', href: '/studio/video', icon: 'video' },
  { title: 'Звук', href: '/studio/audio', icon: 'audio' }, { title: '3D', href: '/studio/3d', icon: 'cube' }, { title: 'Чат', href: '/studio/chat', icon: 'chat' },
]
const prompts = ['Минималистичная арка у спокойного моря, мягкий свет, тёплая палитра', 'Скульптурная форма в прохладном утреннем свете', 'Тихое пространство, отражения и геометрия']

export function Studio() {
  const { state, start, updateDraft } = useDemo()
  const [modelPicker, setModelPicker] = useState(false)
  const [confirmation, setConfirmation] = useState(false)
  const [fail, setFail] = useState(false)
  const model = models.find(m => m.id === state.draft.model) ?? models[0]
  const active = state.job?.state === 'running'
  const affordable = state.balance >= model.cost
  const canStart = !!state.draft.prompt.trim() && !active && affordable && state.works.length < 24
  return <>
    <header className="page-heading"><p className="eyebrow">СТУДИЯ / 01</p><h1>Ваша идея. <span>Новая форма.</span></h1><p>От первого слова — к тому, что хочется сохранить.</p></header>
    <div className="direction-tabs" aria-label="Направления творчества">{directions.map((d, i) => <Link key={d.href} className={`workspace-card ${i === 0 ? 'selected' : ''}`} href={d.href} aria-current={i === 0 ? 'page' : undefined}><Icon name={d.icon} />{d.title}{i > 0 && <span className="direction-soon">позже</span>}</Link>)}</div>
    <div className="studio-grid">
      <section className="composer" aria-labelledby="composer-title">
        <div className="panel-heading"><h2 id="composer-title">Что создаём?</h2><Icon name="spark" /></div>
        <label className="field-label" htmlFor="prompt">Описание</label>
        <div className="prompt-field"><textarea id="prompt" maxLength={1500} rows={5} placeholder="Опишите сюжет, настроение, свет и детали…" value={state.draft.prompt} onChange={e => updateDraft({ prompt: e.target.value })} /><span>{state.draft.prompt.length} / 1500</span></div>
        <div className="prompt-ideas"><span>Начать с примера</span>{prompts.map((p, i) => <button type="button" key={p} onClick={() => updateDraft({ prompt: p, palette: i })}>{['Архитектура', 'Предмет', 'Атмосфера'][i]} <Icon name="arrow" /></button>)}</div>
        <UploadBox />
        <div className="field-label">Модель <span className="demo-inline">демо</span></div>
        <button className="model-picker" onClick={() => setModelPicker(true)}><span className="model-mark"><Icon name="spark" /></span><span><strong>{model.title}</strong><small>{model.id === 'local-demo' ? 'Локальный исполнитель · макет' : 'Внешний провайдер · макет'}</small></span><span aria-hidden="true">⌄</span></button>
        <fieldset className="aspect-field"><legend>Формат</legend><div className="aspect-options">{aspects.map(a => <button type="button" key={a} aria-pressed={state.draft.aspect === a} className={state.draft.aspect === a ? 'selected' : ''} onClick={() => updateDraft({ aspect: a })}><span className="aspect-symbol" style={{ aspectRatio: a.replace(':', '/') }} />{a}</button>)}</div></fieldset>
        <details className="demo-options"><summary>Проверка состояний макета</summary><label><input type="checkbox" checked={fail} onChange={e => setFail(e.target.checked)} /> Показать ошибку вместо успеха</label><p>Выбранный исходник и описание не отправляются модели.</p></details>
        {!affordable && <p className="field-error" role="alert">Недостаточно демо-баллов. Просмотр сохранённых примеров остаётся доступен.</p>}
        {state.works.length >= 24 && <p className="field-error" role="alert">Достигнут лимит 24 демо-работ. Удалите пример или сбросьте макет.</p>}
        <div className="composer-submit"><button className="primary generate-button" disabled={!canStart} onClick={() => setConfirmation(true)}><Icon name="spark" />{active ? 'Демо выполняется' : 'Создать демо'}<span>{model.cost} {model.cost === 4 ? 'балла' : 'баллов'}</span></button><small><Icon name="lock" /> Без ключей, платежей и AI-запросов</small></div>
      </section>
      <ResultPanel />
    </div>
    <Dialog open={modelPicker} title="Выберите демо-модель" onClose={() => setModelPicker(false)}><p>Это варианты одного интерфейса. Настоящие провайдеры ещё не подключены.</p><div className="model-options">{models.map(m => <button className="model-option" key={m.id} disabled={!m.enabled} onClick={() => { updateDraft({ model: m.id }); setModelPicker(false) }}><strong>{m.title}</strong><span>{m.description}</span><small>{m.enabled ? `${m.cost} демо-баллов` : 'Недоступно'}</small></button>)}</div></Dialog>
    <Dialog open={confirmation} title="Запустить демонстрацию?" onClose={() => setConfirmation(false)}><p>Вы получите предустановленный векторный пример. Это проверка интерфейса, не генерация изображения по описанию.</p><dl className="summary-list"><div><dt>Модель</dt><dd>{model.title}</dd></div><div><dt>Формат</dt><dd>{state.draft.aspect}</dd></div><div><dt>Демо-резерв</dt><dd>{model.cost} баллов</dd></div><div><dt>Реальный расход</dt><dd>0 ₽ · запросов нет</dd></div></dl><button className="primary full-width" disabled={!canStart} onClick={() => { start(fail); setConfirmation(false) }}>Подтвердить демо-запуск <Icon name="arrow" /></button></Dialog>
  </>
}
