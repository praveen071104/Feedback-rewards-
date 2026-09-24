import { expect, test } from '@playwright/test'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const screenshots = fileURLToPath(new URL('../../docs/screenshots/', import.meta.url))
const appreciation = 'I was really struggling to get the pista cookies for the past few days considering everybody loves it. The stock runs out whenever I visit the store. Thankfully, Mr. Joe helped me with the timings when the product will be restocked and I was finally able to get it today for my niece who loves it.'

test('live reward recommendations and responsive screenshots', async ({ page }) => {
  const exceptions: string[] = []
  page.on('pageerror', error => exceptions.push(error.message))
  await page.goto('/')
  for (const [sample, sentiment, decision] of [
    ['Store improvement', 'Negative', 'Eligible'],
    ['Helpful service', 'Positive', 'Not eligible'],
    ['Mixed experience', 'Neutral', 'Not eligible'],
    ['Generic praise', 'Positive', 'Not eligible'],
  ]) {
    await page.getByLabel('Sample feedback').selectOption(sample)
    await expect(page.getByRole('heading', { name: 'Awaiting feedback analysis', exact: true })).toBeVisible()
    await page.getByRole('button', { name: 'Analyse feedback', exact: true }).click()
    await expect(page.getByRole('heading', { name: decision, exact: true })).toBeVisible()
    if (sample !== 'Generic praise') await expect(page.locator('.sentiment')).toHaveText(sentiment)
    await expect(page.getByRole('meter')).toHaveCount(2)
    await expect(page.locator('.feedback-quote blockquote')).toHaveText(await page.getByLabel('Customer feedback', { exact: true }).inputValue())
  }
  for (const feedback of ['Hi', 'Hello', 'Thank you very much', 'qwerty asdfgh zxcvbn']) {
    await page.getByLabel('Customer feedback', { exact: true }).fill(feedback)
    await page.getByRole('button', { name: 'Analyse feedback', exact: true }).click()
    await expect(page.getByRole('heading', { name: 'Not eligible', exact: true })).toBeVisible()
    await expect(page.locator('.genuine-label')).toHaveText('No')
    await expect(page.locator('.explanation').first()).toContainText(/No meaningful customer feedback|minor compliment/)
  }
  for (const feedback of [appreciation, `Hi! ${appreciation} Thank you!`]) {
    await page.getByLabel('Customer feedback', { exact: true }).fill(feedback)
    await page.getByRole('button', { name: 'Analyse feedback', exact: true }).click()
    await expect(page.getByRole('heading', { name: 'Not eligible', exact: true })).toBeVisible()
    await expect(page.locator('.genuine-label')).toHaveText('Yes')
    await expect(page.locator('.feedback-quote blockquote')).toHaveText(feedback)
  }
  for (const feedback of [
    'The cakes are really good but always sold out. Would be nice if it can be stocked frequently.',
    'The bakery items are fresh, but most popular products are already sold out by evening. It would help if stock is replenished more frequently.',
    'cakes sold out by 5pm',
    'cakes sold out. please restock before lunch',
    'cakes always soldout pls restock',
  ]) {
    await page.getByLabel('Customer feedback', { exact: true }).fill(feedback)
    await page.getByRole('button', { name: 'Analyse feedback', exact: true }).click()
    await expect(page.getByRole('heading', { name: 'Not eligible', exact: true })).toBeVisible()
    await expect(page.locator('.genuine-label')).toHaveText('Yes')
    await expect(page.getByRole('heading', { name: 'Minor complaint', exact: true })).toBeVisible()
    await expect(page.getByRole('region', { name: 'Complaint ticket' })).toContainText('Normal')
  }
  for (const feedback of ['cakes sold out', 'nice cakes but no stock', 'The bakery items are sold out.', 'pls restock bread']) {
    await page.getByLabel('Customer feedback', { exact: true }).fill(feedback)
    await page.getByRole('button', { name: 'Analyse feedback', exact: true }).click()
    await expect(page.getByRole('heading', { name: 'Not eligible', exact: true })).toBeVisible()
    await expect(page.locator('.genuine-label')).toHaveText('No')
    await expect(page.locator('.explanation').first()).toContainText(/More details are needed|minor complaint needs follow-up/)
  }
  await page.getByRole('button', { name: 'Clear feedback' }).click()
  await expect(page.getByRole('button', { name: 'Analyse feedback', exact: true })).toBeDisabled()
  await page.getByLabel('Customer feedback', { exact: true }).fill('123!')
  await expect(page.getByRole('button', { name: 'Analyse feedback', exact: true })).toBeDisabled()
  await page.getByLabel('Sample feedback').selectOption('Store improvement')
  await page.getByRole('button', { name: 'Analyse feedback', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Eligible', exact: true })).toBeVisible()
  for (const width of [320, 390, 768, 1440]) {
    await page.setViewportSize({ width, height: 1000 })
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
    const input = await page.locator('.input-section').boundingBox()
    const result = await page.locator('.result-section').boundingBox()
    expect(input).not.toBeNull()
    expect(result).not.toBeNull()
    if (width >= 768) expect(result!.x).toBeGreaterThan(input!.x)
    else expect(result!.y).toBeGreaterThan(input!.y)
  }
  await page.screenshot({ path: path.join(screenshots, 'desktop.png'), fullPage: true })
  await page.setViewportSize({ width: 390, height: 844 })
  await page.screenshot({ path: path.join(screenshots, 'mobile.png'), fullPage: true })
  expect(exceptions).toEqual([])
})

test('loading lock, server error, and successful retry', async ({ page }) => {
  await page.goto('/')
  let releaseRequest!: () => void
  const holdRequest = new Promise<void>(resolve => { releaseRequest = resolve })
  await page.route('**/api/predict', async route => {
    await holdRequest
    await route.fulfill({ status: 503, contentType: 'application/json', body: '{"detail":"Models unavailable"}' })
  })
  await page.getByRole('button', { name: 'Analyse feedback', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Analysing feedback...' })).toBeDisabled()
  await expect(page.getByLabel('Customer feedback', { exact: true })).toBeDisabled()
  releaseRequest()
  await expect(page.getByRole('alert')).toContainText('Models are unavailable')
  await page.unroute('**/api/predict')
  await page.getByRole('button', { name: 'Analyse feedback', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Eligible', exact: true })).toBeVisible()
})

test('insights track live results, filters, navigation and session lifecycle', async ({ page }) => {
  const exceptions: string[] = []
  page.on('pageerror', error => exceptions.push(error.message))
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.clock.install()
  await page.goto('/#insights')
  await expect(page.getByRole('heading', { name: 'No analyses yet' })).toBeVisible()
  await expect(page.getByTestId('analytics-total')).toHaveText('0')
  await expect(page.getByRole('button', { name: 'Clear session history' })).toBeDisabled()
  await page.getByRole('link', { name: 'Feedback', exact: true }).click()
  for (const sample of ['Store improvement', 'Helpful service']) {
    await page.getByLabel('Sample feedback').selectOption(sample)
    await page.getByRole('button', { name: 'Analyse feedback', exact: true }).click()
    await expect(page.getByRole('heading', { name: sample === 'Store improvement' ? 'Eligible' : 'Not eligible', exact: true })).toBeVisible()
  }
  await page.getByRole('link', { name: 'Insights', exact: true }).click()
  await expect(page.getByTestId('analytics-total')).toHaveText('2')
  await expect(page.getByRole('meter', { name: 'Positive share' })).toHaveAttribute('aria-valuenow', '50')
  await expect(page.getByRole('meter', { name: 'Negative share' })).toHaveAttribute('aria-valuenow', '50')
  await expect(page.getByRole('meter', { name: 'Neutral share' })).toHaveAttribute('aria-valuenow', '0')
  await expect(page.locator('.analytics tbody tr')).toHaveCount(2)
  await expect(page.getByRole('img', { name: /Feedback volume/ })).toHaveAttribute('aria-label', /2 analyses/)
  await page.getByLabel('Sentiment filter').selectOption('Negative')
  await expect(page.getByTestId('analytics-total')).toHaveText('1')
  await expect(page.locator('.analytics tbody')).toContainText('eye strain')
  await page.getByLabel('Sentiment filter').selectOption('Neutral')
  await expect(page.getByText('No feedback matches these filters.')).toBeVisible()
  await expect(page.getByTestId('analytics-total')).toHaveText('0')
  await page.getByLabel('Sentiment filter').selectOption('All')
  for (const width of [320, 390, 768, 1440]) {
    await page.setViewportSize({ width, height: 1000 })
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
    await expect(page.getByRole('heading', { name: 'Insight engine', exact: true })).toBeVisible()
    const metrics = await page.locator('.analytics-kpis').boundingBox()
    const charts = await page.locator('.analytics-charts').boundingBox()
    expect(charts!.y).toBeGreaterThanOrEqual(metrics!.y + metrics!.height)
  }
  await page.screenshot({ path: path.join(screenshots, 'analytics-desktop.png'), fullPage: true })
  await page.setViewportSize({ width: 390, height: 844 })
  await page.screenshot({ path: path.join(screenshots, 'analytics-mobile.png'), fullPage: true })
  await page.goBack()
  await expect(page.getByRole('heading', { name: 'Not eligible', exact: true })).toBeVisible()
  await page.goForward()
  await expect(page.getByTestId('analytics-total')).toHaveText('2')
  await page.getByLabel('Time range').selectOption('hour')
  await page.clock.fastForward(61 * 60000)
  await expect(page.getByTestId('analytics-total')).toHaveText('0')
  await page.getByLabel('Time range').selectOption('session')
  await expect(page.getByTestId('analytics-total')).toHaveText('2')
  page.once('dialog', dialog => dialog.dismiss())
  await page.getByRole('button', { name: 'Clear session history' }).click()
  await expect(page.getByTestId('analytics-total')).toHaveText('2')
  page.once('dialog', dialog => dialog.accept())
  await page.getByRole('button', { name: 'Clear session history' }).click()
  await expect(page.getByRole('heading', { name: 'No analyses yet' })).toBeVisible()
  await page.getByRole('link', { name: 'Feedback', exact: true }).click()
  await page.getByRole('button', { name: 'Analyse feedback', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Not eligible', exact: true })).toBeVisible()
  await page.getByRole('link', { name: 'Insights', exact: true }).click()
  await expect(page.getByTestId('analytics-total')).toHaveText('1')
  await page.reload()
  await expect(page.getByRole('heading', { name: 'No analyses yet' })).toBeVisible()
  expect(exceptions).toEqual([])
})

test('insights exclude failed requests and update when analysis finishes on another page', async ({ page }) => {
  await page.goto('/')
  await page.route('**/api/predict', route => route.fulfill({ status: 503, contentType: 'application/json', body: '{"detail":"Models unavailable"}' }))
  await page.getByRole('button', { name: 'Analyse feedback', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('Models are unavailable')
  await page.getByRole('link', { name: 'Insights', exact: true }).click()
  await expect(page.getByTestId('analytics-total')).toHaveText('0')
  await page.unroute('**/api/predict')
  await page.getByRole('link', { name: 'Feedback', exact: true }).click()
  let releaseRequest!: () => void
  const holdRequest = new Promise<void>(resolve => { releaseRequest = resolve })
  await page.route('**/api/predict', async route => {
    await holdRequest
    await route.continue()
  })
  await page.getByRole('button', { name: 'Analyse feedback', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Analysing feedback...' })).toBeDisabled()
  await page.getByRole('link', { name: 'Insights', exact: true }).click()
  await expect(page.getByTestId('analytics-total')).toHaveText('0')
  releaseRequest()
  await expect(page.getByTestId('analytics-total')).toHaveText('1')
  await expect(page.locator('.analytics tbody')).toContainText('eye strain')
})

test('compliments, pending review and persistent complaint tickets', async ({ page }) => {
  await page.goto('/')
  await page.getByLabel('Sample feedback').selectOption('Baby clothes compliment')
  await page.getByRole('button', { name: 'Analyse feedback', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Not eligible', exact: true })).toBeVisible()
  await expect(page.locator('.customer-response')).toContainText('Thank you')
  await expect(page.getByRole('region', { name: 'Complaint ticket' })).toHaveCount(0)

  await page.getByLabel('Sample feedback').selectOption('Needs review')
  const pendingResponse = page.waitForResponse('**/api/predict')
  await page.getByRole('button', { name: 'Analyse feedback', exact: true }).click()
  const pending = await (await pendingResponse).json()
  await expect(page.getByRole('heading', { name: 'Pending review', exact: true })).toBeVisible()
  await expect(page.locator('.customer-response')).toContainText("We're sorry")
  await expect(page.getByRole('region', { name: 'Complaint ticket' })).toContainText('Priority review')
  await expect(page.getByRole('region', { name: 'Complaint ticket' })).toContainText(pending.ticket.id)
  for (const width of [320, 390, 768, 1440]) {
    await page.setViewportSize({ width, height: 1000 })
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
  }
  await page.getByRole('link', { name: 'Insights', exact: true }).click()
  await expect(page.locator('.analytics tbody')).toContainText('Pending review')
  await page.reload()
  const stored = await page.request.get(`/api/tickets/${pending.ticket.id}`)
  expect(stored.ok()).toBe(true)
  expect(await stored.json()).toEqual(pending.ticket)

  await page.getByRole('link', { name: 'Feedback', exact: true }).click()
  await page.getByLabel('Customer feedback', { exact: true }).fill('qwerty asdfgh zxcvbn')
  await page.getByRole('button', { name: 'Analyse feedback', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Ignored', exact: true })).toBeVisible()
  await expect(page.locator('.customer-response')).toHaveCount(0)
  await expect(page.getByRole('region', { name: 'Complaint ticket' })).toHaveCount(0)
  await page.getByRole('link', { name: 'Insights', exact: true }).click()
  await expect(page.getByTestId('analytics-total')).toHaveText('0')
})

test('retry reuses a ticket when its first confirmation is lost', async ({ page }) => {
  await page.goto('/')
  await page.getByLabel('Sample feedback').selectOption('Payment complaint')
  let openedTicket: { id: string } | undefined
  const submissionIds: string[] = []
  await page.route('**/api/predict', async route => {
    submissionIds.push(route.request().postDataJSON().submissionId)
    const response = await route.fetch()
    const result = await response.json()
    if (!openedTicket) {
      openedTicket = result.ticket
      await route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'Ticket storage unavailable. Please retry.' }) })
    } else {
      expect(result.ticket.id).toBe(openedTicket.id)
      await route.fulfill({ response })
    }
  })
  await page.getByRole('button', { name: 'Analyse feedback', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('Ticket storage is unavailable')
  await expect(page.getByRole('heading', { name: 'Ticket opened', exact: true })).toHaveCount(0)
  await page.getByRole('button', { name: 'Analyse feedback', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Eligible', exact: true })).toBeVisible()
  await expect(page.getByRole('region', { name: 'Complaint ticket' })).toContainText(openedTicket!.id)
  expect(submissionIds).toHaveLength(2)
  expect(submissionIds[0]).toBe(submissionIds[1])
})

test('closed loop sample outcomes, filters and responsive layouts', async ({ page }) => {
  const exceptions: string[] = []
  page.on('pageerror', error => exceptions.push(error.message))
  await page.goto('/#closed-loop')
  await expect(page.getByRole('heading', { name: 'Closed Loop', exact: true })).toBeVisible()
  await expect(page.getByRole('link', { name: 'Closed Loop', exact: true })).toHaveAttribute('aria-current', 'page')
  await expect(page.getByText('Sample cases · Demo only')).toBeVisible()
  await expect(page.locator('.loop-case')).toHaveCount(7)
  await expect(page.locator('.loop-ownership')).toContainText('M&S Marble Arch - London')
  await expect(page.locator('#loop-store option')).toHaveText(['All stores', 'M&S Marble Arch - London', 'M&S Stratford City - London', 'M&S Bluewater - Greenhithe, Kent'])
  await expect(page.getByRole('heading', { name: 'We did', exact: true })).toBeVisible()
  await expect(page.locator('.loop-done')).toContainText('Replaced the faulty latch')
  await expect(page.getByRole('region', { name: 'Customer update' })).toContainText('Simulated')
  await expect(page.getByRole('region', { name: 'Action history' })).toContainText('Issue resolved and loop closed')
  await expect(page.getByRole('region', { name: 'Six-category policy' }).locator('tbody tr')).toHaveCount(6)
  for (const width of [320, 390, 768, 1440]) {
    await page.setViewportSize({ width, height: 1000 })
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
    const list = await page.locator('.loop-case-list').boundingBox()
    const detail = await page.locator('.loop-detail').boundingBox()
    if (width <= 700) expect(detail!.y).toBeGreaterThanOrEqual(list!.y + list!.height)
    else expect(detail!.x).toBeGreaterThanOrEqual(list!.x + list!.width)
    const stages = await page.locator('.loop-stages').boundingBox()
    const outcome = await page.locator('.loop-outcome').boundingBox()
    expect(outcome!.y).toBeGreaterThanOrEqual(stages!.y + stages!.height)
  }
  await page.screenshot({ path: path.join(screenshots, 'closed-loop-desktop.png'), fullPage: true })
  await page.setViewportSize({ width: 390, height: 844 })
  await page.screenshot({ path: path.join(screenshots, 'closed-loop-mobile.png'), fullPage: true })
  await page.getByLabel('Store', { exact: true }).selectOption('Bluewater')
  await expect(page.locator('.loop-case')).toHaveCount(2)
  await expect(page.locator('.loop-ownership')).toContainText('M&S Bluewater - Greenhithe, Kent')
  await page.getByRole('button', { name: /Shelf prices made clearer/ }).click()
  await expect(page.locator('.loop-ownership')).toContainText('High tier')
  await expect(page.locator('.loop-person')).toContainText('Loyal customer')
  await page.getByLabel('Case status').selectOption('Open')
  await expect(page.getByRole('heading', { name: 'No matching cases' })).toBeVisible()
  await page.getByRole('button', { name: 'Clear filters', exact: true }).click()
  await page.getByRole('searchbox', { name: 'Search cases' }).fill('CL-1044')
  await expect(page.locator('.loop-case')).toHaveCount(1)
  await expect(page.locator('.loop-detail')).toContainText('No ticket opened yet')
  await expect(page.getByRole('button', { name: /Record resolution/ })).toHaveCount(0)
  await page.getByRole('searchbox', { name: 'Search cases' }).fill('Baby clothes')
  await expect(page.locator('.loop-detail')).toContainText('congratulations on your newborn')
  await expect(page.locator('.loop-ownership')).toContainText('Not required')
  await page.getByRole('link', { name: 'Insights', exact: true }).click()
  await expect(page.getByTestId('analytics-total')).toHaveText('0')
  await page.goBack()
  await expect(page.getByRole('heading', { name: 'Closed Loop', exact: true })).toBeVisible()
  expect(exceptions).toEqual([])
})

test('closed loop demo records a resolution without calling live services', async ({ page }) => {
  const apiRequests: string[] = []
  page.on('request', request => { if (request.url().includes('/api/')) apiRequests.push(request.url()) })
  await page.goto('/#closed-loop')
  await page.getByRole('button', { name: /Empty hand-soap dispenser/ }).click()
  await page.getByRole('button', { name: 'Start work (demo)' }).click()
  await expect(page.locator('.loop-detail-heading')).toContainText('In progress')
  await expect(page.getByRole('button', { name: 'Record resolution (demo)' })).toBeDisabled()
  await page.getByLabel('Completed action').fill('             ')
  await expect(page.getByRole('button', { name: 'Record resolution (demo)' })).toBeDisabled()
  const action = 'Refilled the soap dispenser and tested the pump. All customer washroom dispensers checked.'
  await page.getByLabel('Completed action').fill(action)
  await page.getByRole('button', { name: 'Record resolution (demo)' }).click()
  await expect(page.getByRole('status')).toContainText('resolution and simulated customer update recorded')
  await expect(page.locator('.loop-detail-heading')).toContainText('Resolved')
  await expect(page.locator('.loop-done')).toContainText(action)
  await expect(page.getByRole('region', { name: 'Customer update' })).toContainText(action)
  await expect(page.getByRole('region', { name: 'Action history' })).toContainText('loop closed')
  await page.getByRole('link', { name: 'Feedback', exact: true }).click()
  await page.getByRole('link', { name: 'Closed Loop', exact: true }).click()
  await expect(page.locator('.loop-done')).toContainText(action)
  expect(apiRequests).toEqual([])
  await page.reload()
  await page.getByRole('button', { name: /Empty hand-soap dispenser/ }).click()
  await expect(page.locator('.loop-detail-heading')).toContainText('Open')
})

test('new incentive recommendations and minor complaint detail request', async ({ page }) => {
  await page.goto('/')
  await page.getByLabel('Sample feedback').selectOption('Baby clothes compliment')
  await page.getByRole('button', { name: 'Analyse feedback', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Not eligible', exact: true })).toBeVisible()
  await page.getByRole('checkbox', { name: 'Loyal customer (POC profile)' }).check()
  await expect(page.getByRole('heading', { name: 'Awaiting feedback analysis', exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Analyse feedback', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Eligible', exact: true })).toBeVisible()
  await expect(page.locator('.explanation')).toContainText(['Minor compliment', 'High tier', 'Customer response'])
  await page.getByRole('checkbox', { name: 'Loyal customer (POC profile)' }).uncheck()
  await page.getByLabel('Customer feedback', { exact: true }).fill('The colleague went above and beyond, finding my missing order and arranging delivery to my home.')
  await page.getByRole('button', { name: 'Analyse feedback', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Major compliment', exact: true })).toBeVisible()
  await expect(page.getByText('Tier-based · Amount undecided · Not issued')).toBeVisible()
  await page.getByLabel('Customer feedback', { exact: true }).fill('cakes sold out')
  await page.getByRole('button', { name: 'Analyse feedback', exact: true }).click()
  await expect(page.locator('.customer-response')).toContainText('Please share')
  await expect(page.getByRole('region', { name: 'Complaint ticket' })).toHaveCount(0)
})