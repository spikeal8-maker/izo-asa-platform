import { WorkspaceGate } from '../../shared/workspace'
import { GuestTrial } from './GuestTrial'
import { Composer } from './Composer'
import './studio.css'

export function Studio() {
  return <><header className="page-heading"><p className="eyebrow">СТУДИЯ / ИЗОБРАЖЕНИЕ</p>
    <h1>Создайте изображение.</h1><p>Опишите идею, выберите режим и формат результата.</p></header>
    <WorkspaceGate unauthenticated={<GuestTrial />}>{auth => <Composer auth={auth} />}</WorkspaceGate></>
}
