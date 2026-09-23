import { test, expect as e, type Locator as J, type Page as Z } from '@playwright/test'
import { noOverflow as Y, workspace as W } from './workspace-fixtures'
type U=Z|J
type K=string
const V=(...x:J[])=>Promise.all(x.map(v=>e(v).toBeVisible()))
const C=(x:J,n:number)=>e(x).toHaveCount(n),X=(x:J,s:K)=>e(x).toHaveText(s)
const T=(x:J,s:K)=>e(x).toContainText(s),A=(x:J,k:K,s:K)=>e(x).toHaveAttribute(k,s)
const Q=(x:U,s:K)=>x.locator(s),D=(x:U,s:K)=>x.getByTestId(s)
const B=(x:U,s:K)=>x.getByRole('button',{name:s}),I=(x:U,s:K)=>x.getByRole('menuitem',{name:s})
const R=(x:U,s:K)=>x.getByRole('menuitemradio',{name:s}),E=(x:U,s:K)=>x.getByRole('textbox',{name:s})
const L=(x:U,s:K)=>x.getByRole('link',{name:s,exact:true})
const H=(p:Z)=>D(p,'global-header'),P=(p:Z)=>Q(p,'.chat-composer'),S=(p:Z)=>Q(p,'.chat-sidebar')
const N={l:'Войти',p:'Профиль',m:'Сообщение',a:'Добавить',s:'Отправить',t:'Инструменты',o:'Модели',
c:'Выбрать модель',n:'Открыть панель',q:'Поиск чатов',f:'Новый чат',b:'Поиск по чатам',i:'Создать изображение',
w:'Поиск в интернете',x:'FLUX.2 [klein] 4B'}
const F=(p:Z)=>p.goto('/')
async function G(p:Z){await p.unroute('**/api/v1/auth/me');const s=await W(p);s.account.display_name='Александр';s.balance=123
await p.route('**/api/v1/chat/policy',r=>r.fulfill({json:{revision:'test',default_model:'deepseek-flash',models:[{id:'deepseek-flash',label:'DeepSeek Flash'}],max_input_chars:6000,max_output_tokens:2048}}))
await p.route('**/api/v1/chat/credential',r=>r.fulfill({json:{configured:true,enabled:true,verified:true,revision:1,generation:1,provider:'deepseek'}}))
await p.route('**/api/v1/chat/threads',r=>r.fulfill({json:{threads:[]}}));return s}
async function M(m:J){await V(...['Аккаунт','Токены','Настройки','Помощь'].map(x=>I(m,x)),m.getByText('Тема',{exact:true}),R(m,'Светлая'),R(m,'Тёмная'),I(m,'Выйти'));await C(Q(m,'.social-link'),4)}
async function O(p:Z){const x=B(p,N.n);if(await x.isVisible())await x.click()}
test.beforeEach(async({page})=>page.route('**/api/v1/auth/me',r=>r.fulfill({status:401,json:{error:{code:'auth_required'}}})))
test('r',async({page})=>{
for(const path of ['/','/image','/video','/audio','/3d','/feed','/gallery']){await page.goto(path);await Promise.all([
C(H(page),1),C(page.getByRole('navigation',{name:/ИЗО АСА$/}).getByRole('link'),5),C(page.getByText('Страница не найдена',{exact:true}),0)])}
await page.goto('/studio/video');await e(page).toHaveURL(/\/video$/);await X(page.getByRole('heading',{level:1}),'Видео')
await page.goto('/help');await C(page.getByText('Начните с обычного запроса и выберите инструмент, если нужен результат другого типа.',{exact:true}),0)
await V(page.getByText('Опишите задачу обычным языком. Прямые инструменты для изображений, видео, звука и 3D доступны отдельными разделами.',{exact:true}))
await page.goto('/feed');await Promise.all([T(page.getByRole('heading',{level:1}),'Создавайте, смотрите и развивайте идеи'),C(Q(page,'.feed-card'),6)])
})
test('h',async({page},info)=>{
await F(page);let h=H(page),v=page.getByRole('navigation',{name:'Лента и Галерея'}),t=D(page,'global-token-group');await Promise.all([T(D(t,'token-daily'),'0/0'),T(D(t,'token-main'),'0'),C(Q(t,'[data-icon="sun"]'),1),C(Q(t,'[data-icon="gem"]'),1)])
for(const [n,x,color] of [['izo','ИЗО','rgb(138, 90, 0)'],['asa','АСА','rgb(110, 69, 193)']] as const){const z=Q(h,`.brand-${n}`);await Promise.all([X(z,x),e(z).toHaveCSS('color',color)])}
await A(Q(h,'.brand-favicon'),'src','/favicon.svg');await V(L(h,N.l),L(v,'Лента'),L(v,'Галерея'));await Y(page)
await G(page);await page.reload();h=H(page);t=D(page,'global-token-group');await Promise.all([C(L(h,N.l),0),T(D(t,'token-main'),'123'),C(Q(page,'.chat-sidebar-bottom'),1),X(Q(page,'.chat-profile-name'),'Александр')])
await B(h,N.p).click();let m=page.getByRole('menu');await M(m);await R(m,'Тёмная').click();await A(Q(page,'html'),'data-theme','dark')
if(info.project.name!=='laptop')return
await page.keyboard.press('Escape');const model=Q(page,'.chat-model-selector');await V(model);await T(model,'Авто');await model.click();m=page.getByRole('menu',{name:N.o});const text=Q(m,'.chat-model-category').filter({hasText:'Текст'});await Q(text,'summary').click();await V(R(text,'DeepSeek Flash'));await C(R(m,N.x),0)
})
test('d',async({page},i)=>{
test.skip(i.project.name!=='laptop');await F(page);const h=await H(page).boundingBox(),c=await Q(page,'.chat-page').boundingBox(),s=await S(page).boundingBox()
e([h?.x,h?.height!>=51,h?.height!<=53,c?.x,s?.x,s?.width]).toEqual([0,true,true,0,0,280])
await page.goto('/feed');e(await page.evaluate(()=>document.documentElement.scrollHeight>innerHeight)).toBe(true);await page.evaluate(()=>scrollTo(0,700));await page.waitForTimeout(50);e((await H(page).boundingBox())?.y).toBe(0)
await page.setViewportSize({width:320,height:568});await F(page);const z=await page.evaluate(()=>{const a=[...document.querySelectorAll('.global-brand,.explore-nav .header-route,.token-pill,.login-button,.header-avatar')]
.filter(e=>{const s=getComputedStyle(e),r=e.getBoundingClientRect();return s.display!=='none'&&s.visibility!=='hidden'&&+s.opacity!==0&&r.width>0}).map(e=>e.getBoundingClientRect()),o=(x:DOMRect,y:DOMRect)=>x.left<y.right&&x.right>y.left&&x.top<y.bottom&&x.bottom>y.top
return{collision:a.some((x,j)=>a.slice(j+1).some(y=>o(x,y))),overflow:document.documentElement.scrollWidth>innerWidth}});e(z).toEqual({collision:false,overflow:false})
})
test('8K shell',async({page},i)=>{
test.skip(i.project.name!=='eight-k');await F(page);const m=await page.evaluate(()=>{const f=(s:K)=>parseFloat(getComputedStyle(document.querySelector(s)!).fontSize),w=(s:K)=>document.querySelector(s)!.getBoundingClientRect().width
return{b:f('.global-brand'),p:f('.product-tab'),h:f('.chat-start-state h1'),s:w('.chat-sidebar'),c:w('.chat-composer-wrap'),v:innerWidth}})
e([m.b>=34,m.p>=28,m.h>=72,m.s>=600,m.c>=2100,m.c<m.v/2]).toEqual([true,true,true,true,true,true]);await page.goto('/feed');const g=Q(page,'.feed-grid')
e([await g.evaluate(x=>getComputedStyle(x).gridTemplateColumns.split(' ').length)>=8,(await g.boundingBox())!.width>4000,((await Q(page,'.feed-hero-copy').boundingBox())?.width??9999)<1000]).toEqual([true,true,true]);await Y(page)
})
test('c',async({page})=>{
await F(page);let c=P(page);await X(page.getByRole('heading',{level:1}),'Чем я могу помочь?');await e(E(c,N.m)).toBeDisabled();await e(B(c,N.a)).toBeEnabled();await e(B(c,'Микрофон')).toBeEnabled();await e(B(c,N.s)).toBeDisabled()
await G(page);await page.reload();c=P(page);await e(E(c,N.m)).toBeEnabled();await T(B(c,N.c),'Авто');await e(B(c,N.a)).toBeEnabled();await e(B(c,'Микрофон')).toBeEnabled();await E(c,N.m).fill('Проверка');await e(B(c,N.s)).toBeEnabled()
})
test('s',async({page})=>{
await G(page);const rows=[{id:'11111111-1111-4111-8111-111111111112',title:'Первый проект',created_at:1,updated_at:2},{id:'11111111-1111-4111-8111-111111111113',title:'Второй проект',created_at:1,updated_at:3}]
await page.route('**/api/v1/chat/threads',r=>r.fulfill({json:{threads:rows}}));await F(page);const s=S(page);await O(page);await V(B(s,'Первый проект'),B(s,'Второй проект'));await B(s,N.q).click();const q=E(s,N.b);await q.fill('Первый');await V(B(s,'Первый проект'));await C(B(s,'Второй проект'),0)
})
test('p',async({page},i)=>{
test.skip(!i.project.name.startsWith('phone'));await F(page);if(i.project.name==='phone'){await E(page,N.m).focus();await page.setViewportSize({width:390,height:560});await page.waitForTimeout(80)
const m=await page.evaluate(()=>{const a=document.querySelector('.app.chat-shell')!.getBoundingClientRect(),h=document.querySelector('[data-testid="global-header"]')!.getBoundingClientRect(),c=document.querySelector('.chat-composer')!.getBoundingClientRect()
return{v:visualViewport?.height??innerHeight,h:parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--chat-viewport-height')),a:a.top,t:h.top,c:c.bottom}});e([Math.abs(m.h-m.v)<=1,m.a>=0,m.t>=0,m.c<=m.v+1]).toEqual([true,true,true,true])}
const h=H(page),s=S(page);await V(B(page,N.n));const b=await s.boundingBox();e(b?b.x+b.width:1).toBeLessThanOrEqual(0)
await V(L(page.getByRole('navigation',{name:/ИЗО АСА$/}),'Изображение'));const x=(await h.boundingBox())?.height??0;e([x>=65,x<=67]).toEqual([true,true])
await G(page);await page.reload();e((await D(page,'token-main').boundingBox())?.width??0).toBeGreaterThanOrEqual(46);await Y(page)
})
for(const host of ['telegram','max'] as const)test(host,async({page})=>{
await page.addInitScript(k=>{const w=window as Window&{Telegram?:object;WebApp?:object};if(k==='telegram')w.Telegram={WebApp:{initDataUnsafe:{user:{id:1}}}};else w.WebApp={initData:'untrusted-test-input'}},host)
await page.goto('/login');await A(Q(page,'.app'),'data-platform',host);await X(page.getByRole('heading',{level:1}),N.l);await V(B(page,N.l));await C(D(page,'server-account'),0)
})
