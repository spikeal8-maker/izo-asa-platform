import { Icon } from '../../shared/ui/Icon'
import { Link } from '../../shell/router'

export function EmptyResult() {
  return <section className="result-panel">
    <div className="panel-heading"><h2>Результат</h2></div>
    <div className="server-result-empty"><Icon name="image" /><h3>Здесь появится готовая работа</h3>
      <p>После подтверждения результат сохранится в вашей галерее, откуда его можно открыть и скачать.</p>
      <Link className="secondary" href="/gallery">Открыть галерею</Link>
    </div>
  </section>
}
