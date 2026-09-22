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
async function G(p:Z){await p.unroute('**/api/v1/auth/me');const s=await W(p);s.account.display_name='Александр';s.balance=123;s.capabilities=['fal.flux2.klein.4b']}
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
for(const [s,x,color] of [['izo','ИЗО','rgb(138, 90, 0)'],['asa','АСА','rgb(110, 69, 193)']] as const){const z=Q(h,`.brand-${s}`);await Promise.all([X(z,x),e(z).toHaveCSS('color',color)])}
await A(Q(h,'.brand-favicon'),'src','/favicon.svg');await V(L(h,N.l),L(v,'Лента'),L(v,'Галерея'));await Promise.all([
C(h.getByRole('link',{name:/Регистрация|Создать аккаунт/}),0),C(v.getByRole('link'),2),C(Q(t,'.token-caption'),0),C(Q(h,'.guest-theme'),0)])
await e(t).not.toContainText('—');await e(h).not.toContainText('ASA Auto');await Y(page)
await G(page);await page.reload();h=H(page);t=D(page,'global-token-group');await Promise.all([C(L(h,N.l),0),T(D(t,'token-daily'),'0/0'),T(D(t,'token-main'),'123'),C(Q(page,'.chat-sidebar-bottom'),1),X(Q(page,'.chat-profile-name'),'Александр')])
await B(h,N.p).click();let m=page.getByRole('menu');await M(m);await Promise.all([C(Q(m,'.social-link[href]'),2),C(Q(m,'.social-link[aria-disabled="true"]'),2)]);await R(m,'Тёмная').click()
await Promise.all([A(Q(page,'html'),'data-theme','dark'),e(Q(page,'html')).toHaveCSS('--color-brand','#9d78ea')])
if(info.project.name!=='laptop')return
const avatar=B(h,N.p);await page.keyboard.press('Escape');await C(Q(page,'.profile-menu'),0);await e(avatar).toBeFocused()
const model=Q(page,'.chat-model-selector');await model.click();await Q(page,'.chat-model-menu').press('Escape');await C(Q(page,'.chat-model-menu'),0);await e(model).toBeFocused()
const bottom=Q(page,'.chat-sidebar-bottom');await V(bottom);await B(bottom,'Профиль в боковой панели').click();await M(Q(page,'.chat-profile-menu'))
await B(bottom,'Профиль в боковой панели').click();await B(P(page),N.c).click();m=page.getByRole('menu',{name:N.o});const image=Q(m,'.chat-model-category').filter({hasText:'Изображения'})
await Q(image,'summary').click();const flux=R(image,N.x);await V(flux);await flux.click();await T(B(P(page),N.c),N.x)
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
await F(page);let c=P(page);await Promise.all([X(page.getByRole('heading',{level:1}),'Чем я могу помочь?'),V(E(c,N.m)),C(Q(page,'.chat-toolbar .chat-model-selector'),0),C(Q(page,'.chat-new-mobile'),0)])
const plus=c.getByRole('button',{name:N.a,exact:true});await e(plus).toBeEnabled();await plus.click();let m=page.getByRole('menu',{name:N.t})
await V(...['Добавить файл',N.i,'Создать видео','Создать звук','Создать 3D',N.w].map(x=>m.getByRole('menuitem',{name:x,exact:true})));await m.getByRole('menuitem',{name:N.i,exact:true}).click()
await V(B(c,`Убрать инструмент: ${N.i}`));await plus.click();const img=I(page.getByRole('menu',{name:N.t}),N.i);await A(img,'aria-pressed','true');await img.click();const model=B(c,N.c);await T(model,'Авто');await model.click()
m=page.getByRole('menu',{name:N.o});await Promise.all([A(R(m,'Авто'),'aria-checked','true'),C(Q(m,'.chat-model-category'),5)]);await V(...['Текст','Изображения','Видео','Звук','3D'].map(x=>Q(m,'summary').filter({hasText:x})))
await Q(page,'.chat-toolbar').click({position:{x:200,y:10}});await C(page.getByRole('menu',{name:N.o}),0);await plus.click();await I(page.getByRole('menu',{name:N.t}),N.w).click();await V(B(c,`Убрать инструмент: ${N.w}`))
const mic=B(c,'Микрофон');await e(mic).toBeEnabled();await C(Q(mic,'[data-icon="mic"]'),1);await E(c,N.m).fill('Проверка');await B(c,N.s).click();await T(page.getByRole('status'),'пока не подключён к серверу')
await F(page);c=P(page);await c.getByRole('button',{name:N.a,exact:true}).click();const q=page.waitForEvent('filechooser');await I(page.getByRole('menu',{name:N.t}),'Добавить файл').click();const f=await q
await f.setFiles({name:'reference.txt',mimeType:'text/plain',buffer:Buffer.from('reference')});await T(Q(c,'.attachment-chip'),'reference.txt');await B(c,'Удалить вложение').click();await C(Q(c,'.attachment-chip'),0)
})
test('m',async({page},i)=>{
test.skip(i.project.name!=='laptop');await page.addInitScript(()=>{class A{frequencyBinCount=64;getByteFrequencyData(t:Uint8Array){t.fill(170)}}class S{connect(){}disconnect(){}}
class X{state='running';createAnalyser(){return new A()}createMediaStreamSource(){return new S()}async resume(){}async close(){this.state='closed'}}
Object.defineProperty(window,'AudioContext',{configurable:true,value:X});Object.defineProperty(navigator,'mediaDevices',{configurable:true,value:{getUserMedia:async()=>({getTracks:()=>[{stop(){},addEventListener(){}}]})}})})
await F(page);const c=P(page);await B(c,'Микрофон').click();await V(c.getByRole('status',{name:'Микрофон активен'}));await C(Q(c,'.chat-voice-waveform > span'),48);await page.waitForTimeout(80)
const x=await Q(c,'.chat-voice-waveform > span').evaluateAll(es=>es.map(e=>(e as HTMLElement).style.transform));e(x.some(v=>v&&v!=='scaleY(0.08)')).toBe(true);await B(c,'Остановить микрофон').click();await C(Q(c,'.chat-voice-waveform'),0);await V(E(c,N.m))
})
test('s',async({page})=>{
await F(page);const s=S(page),c=P(page);await C(s,1);await O(page);await C(B(s,N.f),1);await B(s,N.q).click();await V(E(s,N.b),s.getByText('Чаты',{exact:true}));await C(Q(s,'[data-icon="panel"]'),1)
await page.goto('/image');await C(S(page),0);await F(page);for(const [i,x] of ['Первый проект','Второй проект'].entries()){await E(c,N.m).fill(x);await B(c,N.s).click();await O(page);if(i===0)await B(s,N.f).click()}
await V(B(s,'Первый проект'),B(s,'Второй проект'));await B(s,N.q).click();await C(s.getByText('История',{exact:true}),0);const q=E(s,N.b);await V(q);await q.fill('Первый');await V(B(s,'Первый проект'));await C(B(s,'Второй проект'),0)
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
