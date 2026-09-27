import { test, expect } from '@playwright/test'

const user = { id:'22222222-2222-4222-8222-222222222222', public_code:'abcd1234abcd1234',
  display_name:'Тестовый получатель с длинным отображаемым именем', state:'active', verified:true, created_at:1000 }
const actor = { id:'11111111-1111-4111-8111-111111111111', public_code:'aaaabbbbccccdddd',
  display_name:'Тестовый оператор', state:'active', email:'test@example.invalid', email_verified:true,
  permissions:['users.read_limited','credits.read','credits.grant','audit.read'] }
const balance = (amount:number) => ({ account_id:user.id, balance:{balance:amount,available:amount,reserved:0,sequence:amount?1:0},entries:[],next_before:null })
const catalog=(permissions:string[])=>({revision:1,permissions,
  providers:[{id:'deepseek',label:'DeepSeek'},{id:'fal',label:'fal.ai'}],models:[
    {id:'deepseek-flash',provider:'deepseek',modality:'text',label:'DeepSeek Flash',published:true,enabled:true,is_default:true,publishable:true,
      price:{currency:'RUB',input_kopeks_per_million:null,output_kopeks_per_million:0,image_kopeks_per_image:null}},
    {id:'fal.flux2.klein.4b',provider:'fal',modality:'image',label:'FLUX.2 [klein] 4B',published:false,enabled:false,is_default:false,publishable:false,
      price:{currency:'RUB',input_kopeks_per_million:null,output_kopeks_per_million:null,image_kopeks_per_image:450}},
  ]})

test.beforeEach(async ({page})=>{
  await page.route('**/api/v1/foundation',r=>r.fulfill({json:{stage:'foundation',build_sha:'unreleased',capabilities:[]}}))
  await page.route('**/api/v1/auth/me',r=>r.fulfill({json:{account:actor,csrf_token:'test-csrf'}}))
  await page.route('**/api/v1/credits',r=>r.fulfill({json:{account_id:actor.id,
    balance:{balance:0,available:0,reserved:0,sequence:0},entries:[],next_before:null}}))
  await page.route('**/api/v1/admin/me',r=>r.fulfill({json:{permissions:actor.permissions,max_grant:1000,csrf_token:'test-csrf'}}))
  await page.route('**/api/v1/admin/users?*',r=>r.fulfill({json:{users:[user],next_after:null}}))
  await page.route('**/api/v1/admin/users/'+user.id,r=>r.fulfill({json:user}))
  await page.route('**/api/v1/admin/users/'+user.id+'/credits',r=>r.fulfill({json:balance(0)}))
})

test('ADMIN-001 search, real-value card shape and responsive layout',async({page},info)=>{
  await page.goto('/admin/users')
  await page.getByLabel('Имя или публичный код').fill(user.public_code)
  await page.getByRole('button',{name:'Найти пользователя'}).click()
  await page.getByRole('link',{name:'Открыть карточку'}).click()
  await expect(page.getByTestId('admin-available')).toHaveText('0')
  await expect(page.getByRole('heading',{name:user.display_name})).toBeVisible()
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true)
  await page.screenshot({path:info.outputPath('admin-card.png'),fullPage:true})
})

test('ADMIN-001 explicit confirmation sends bounded server command once',async({page})=>{
  const sent: Record<string,unknown>[]=[]
  await page.route('**/api/v1/admin/users/'+user.id+'/compensations',async route=>{
    const body=route.request().postDataJSON();sent.push(body)
    expect(route.request().headers()['x-csrf-token']).toBe('test-csrf')
    await route.fulfill({json:{account_id:user.id,case_reference:body.case_reference,entry:{
      entry_id:'33333333-3333-4333-8333-333333333333',operation_id:body.operation_id,
      sequence:1,kind:'grant',balance_delta:40,reserved_delta:0,balance_after:40,reserved_after:0,
      reservation_id:null,reason:'compensation',created_at:2000}}})
  })
  await page.goto('/admin/users/'+user.id)
  await page.getByLabel('Номер заявки').fill('MIG-123')
  await page.getByLabel('Количество баллов').fill('40')
  await page.getByRole('button',{name:'Проверить начисление'}).click()
  expect(sent).toHaveLength(0)
  const dialog=page.getByRole('dialog',{name:'Подтверждение компенсации'})
  await expect(dialog).toContainText(user.public_code)
  await dialog.getByLabel('Текущий пароль администратора').fill('synthetic-password')
  await dialog.getByRole('button',{name:'Подтвердить начисление'}).click()
  await expect(page.locator('.admin-receipt')).toContainText('Начислено 40 баллов')
  expect(sent).toHaveLength(1)
  expect(Object.keys(sent[0]).sort()).toEqual(['amount','case_reference','current_password','operation_id'])
  await expect(page.locator('input[type=password]')).toHaveCount(0)
})

test('ADMIN-001 uncertain response retries same operation and clears password',async({page})=>{
  const ids:string[]=[]
  await page.route('**/api/v1/admin/users/'+user.id+'/compensations',async route=>{
    ids.push(route.request().postDataJSON().operation_id)
    await route.fulfill({status:503,json:{error:{code:'temporary'}}})
  })
  await page.goto('/admin/users/'+user.id)
  await page.getByLabel('Номер заявки').fill('MIG-321')
  await page.getByLabel('Количество баллов').fill('40')
  await page.getByRole('button',{name:'Проверить начисление'}).click()
  const dialog=page.getByRole('dialog')
  for(let i=0;i<2;i++){
    await dialog.getByLabel('Текущий пароль администратора').fill('synthetic-password')
    await dialog.getByRole('button',{name:'Подтвердить начисление'}).click()
    await expect(dialog.getByRole('alert')).toContainText('Результат неизвестен')
    await expect(dialog.locator('input[type=password]')).toHaveValue('')
  }
  expect(ids).toHaveLength(2);expect(ids[0]).toBe(ids[1])
})

test('ADMIN-001 read-only and denied staff never show financial controls',async({page})=>{
  await page.route('**/api/v1/admin/me',r=>r.fulfill({json:{permissions:['users.read_limited'],max_grant:0,csrf_token:'test'}}))
  let financial=0
  await page.route('**/api/v1/admin/users/'+user.id+'/credits',r=>{financial++;return r.fulfill({status:403,json:{error:{code:'forbidden'}}})})
  await page.goto('/admin/users/'+user.id)
  await expect(page.getByRole('heading',{name:user.display_name})).toBeVisible()
  await expect(page.getByLabel('Номер заявки')).toHaveCount(0)
  expect(financial).toBe(0)
  await page.route('**/api/v1/admin/me',r=>r.fulfill({status:403,json:{error:{code:'forbidden'}}}))
  await page.reload()
  await expect(page.locator('.admin-page').getByRole('alert')).toContainText('Нет необходимого')
  await expect(page.getByRole('heading',{name:user.display_name})).toHaveCount(0)
})

test('U-28 server balance and failure never use demo credit fallback',async({page},info)=>{
  await page.route('**/api/v1/credits',r=>r.fulfill({json:balance(40)}))
  await page.goto('/account/credits')
  await expect(page.getByTestId('own-available')).toHaveText('40')
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true)
  await page.screenshot({path:info.outputPath('server-credits.png'),fullPage:true})
  await page.route('**/api/v1/credits',r=>r.fulfill({status:503,json:{error:{code:'unavailable'}}}))
  await page.reload()
  await expect(page.locator('.credits-page').getByRole('alert')).toContainText('Демо-значение не подставляется')
  await expect(page.getByTestId('own-available')).toHaveCount(0)
})

test('catalog-only staff sees server prices without mutation controls',async({page},info)=>{
  const permissions=['catalog.read']
  await page.route('**/api/v1/auth/me',r=>r.fulfill({json:{account:{...actor,permissions},csrf_token:'catalog-csrf'}}))
  await page.route('**/api/v1/admin/catalog',r=>r.fulfill({json:catalog(permissions)}))
  await page.goto('/admin/catalog')
  await expect(page.getByRole('heading',{name:'Каталог моделей'})).toBeVisible()
  const visible=page.locator('.admin-catalog-table:visible, .admin-catalog-cards:visible')
  await expect(visible.getByText('Цена не задана')).toBeVisible()
  await expect(visible.getByText('0 ₽ / 1 млн токенов')).toBeVisible()
  await expect(visible.getByText('4,5 ₽ / изображение')).toBeVisible()
  await expect(page.getByRole('button',{name:'Настроить'})).toHaveCount(0)
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true)
  if(info.project.name==='laptop')await page.screenshot({path:info.outputPath('admin-catalog-desktop.png'),fullPage:true})
  await page.setViewportSize({width:320,height:640})
  const mobile=await page.evaluate(()=>({overflow:document.documentElement.scrollWidth>innerWidth,
    tableHidden:getComputedStyle(document.querySelector('.admin-catalog-table')!).display==='none',
    cards:document.querySelectorAll('.admin-catalog-card').length,
    headerGap:document.querySelector('.token-box')!.getBoundingClientRect().left-document.querySelector('.header-admin-link')!.getBoundingClientRect().right}))
  expect(mobile).toMatchObject({overflow:false,tableHidden:true,cards:2})
  expect(mobile.headerGap).toBeGreaterThanOrEqual(0)
  await page.screenshot({path:info.outputPath('admin-catalog-320.png'),fullPage:true})
})

test('catalog direct URL respects server denial',async({page})=>{
  await page.route('**/api/v1/auth/me',r=>r.fulfill({json:{account:{...actor,permissions:[]},csrf_token:'auth'}}))
  await page.route('**/api/v1/admin/catalog',r=>r.fulfill({status:403,json:{error:{code:'forbidden'}}}))
  await page.goto('/admin/catalog')
  await expect(page.getByRole('alert')).toContainText('Нет полномочия для каталога')
  await expect(page.getByRole('link',{name:'Admin'})).toHaveCount(0)
  await expect(page.locator('.admin-catalog-card')).toHaveCount(0)
})

test('catalog PATCH keeps operation id after uncertain response',async({page},info)=>{
  const permissions=['catalog.read','catalog.write','pricing.write']
  const view=catalog(permissions),sent:Record<string,any>[]=[]
  await page.route('**/api/v1/auth/me',r=>r.fulfill({json:{account:{...actor,permissions},csrf_token:'catalog-csrf'}}))
  await page.route('**/api/v1/admin/catalog',r=>r.fulfill({json:view}))
  await page.route('**/api/v1/admin/catalog/models/deepseek-flash',async r=>{
    expect(r.request().method()).toBe('PATCH')
    expect(r.request().headers()['x-csrf-token']).toBe('catalog-csrf')
    sent.push(r.request().postDataJSON())
    if(sent.length===1)return r.fulfill({status:503,json:{error:{code:'temporary'}}})
    return r.fulfill({json:{...view,revision:2,models:[{...view.models[0],price:sent[1].price},view.models[1]]}})
  })
  await page.goto('/admin/catalog')
  await page.getByRole('button',{name:'Настроить'}).first().click()
  await page.setViewportSize({width:320,height:640})
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true)
  await page.screenshot({path:info.outputPath('admin-catalog-form-320.png'),fullPage:true})
  await page.getByLabel('Вход, ₽ за 1 млн токенов').fill('1,25')
  await page.getByLabel('Выход, ₽ за 1 млн токенов').fill('2.50')
  await page.getByLabel('Причина изменения').fill('Новая отображаемая цена')
  await page.getByRole('button',{name:'Сохранить'}).click()
  await expect(page.getByRole('alert')).toContainText('Результат неизвестен')
  await page.getByRole('button',{name:'Сохранить'}).click()
  await expect(page.getByText('Версия каталога: 2')).toBeVisible()
  expect(sent).toHaveLength(2)
  expect(sent[0].operation_id).toBe(sent[1].operation_id)
  expect(sent[0]).toMatchObject({expected_revision:1,price:{currency:'RUB',input_kopeks_per_million:125,output_kopeks_per_million:250}})
})
