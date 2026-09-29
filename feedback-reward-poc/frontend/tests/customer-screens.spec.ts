import { expect, test } from '@playwright/test'

test.beforeEach(async ({ page }) => {
  await page.routeWebSocket('**/api/colleague/events', socket => socket.close())
  await page.route('**/api/colleague/notifications', route => route.fulfill({
    json: { unread_count: 0, revision: 0, items: [] },
  }))
  await page.route('**/api/colleague/feedback-cases?*', route => route.fulfill({
    json: { items: [], total: 0, page: 1, page_size: 10 },
  }))
  await page.route('**/api/colleague/insights', route => route.fulfill({
    json: { total: 0, statuses: {}, decisions: {}, sentiments: {}, average_rating: null, unread_count: 0 },
  }))
  await page.route('**/api/feedback', route => route.fulfill({ json: { items: [], nextCursor: null } }))
})

test('two main screens retain staff sections and customer drafts', async ({ page }) => {
  await page.goto('/')
  const screens = page.getByRole('navigation', { name: 'Screen navigation' })
  const staff = page.getByRole('navigation', { name: 'Staff navigation' })
  await expect(screens.getByRole('link')).toHaveText(['Customer', 'Staff'])
  await expect(screens.getByRole('link', { name: 'Customer', exact: true })).toHaveAttribute('aria-current', 'page')
  await expect(staff).toHaveCount(0)
  await expect(page.getByTestId('notification-count')).toHaveCount(0)
  await page.getByLabel('Customer Name').fill('Draft Customer')
  await page.getByLabel('Sparks ID (optional)').fill('SPARKS123')
  await screens.getByRole('link', { name: 'Staff', exact: true }).click()
  await expect(screens.getByRole('link', { name: 'Staff', exact: true })).toHaveAttribute('aria-current', 'page')
  await expect(page.getByRole('heading', { name: 'Feedback analysis', exact: true })).toBeVisible()
  await expect(page.getByLabel('Customer Name')).not.toBeVisible()
  await expect(page.getByTestId('notification-count')).toHaveText('0')
  for (const section of ['Insights', 'Feedback Resolution Hub', 'Feedback Analysis']) {
    await staff.getByRole('link', { name: section, exact: true }).click()
    await expect(staff.getByRole('link', { name: section, exact: true })).toHaveAttribute('aria-current', 'page')
    await expect(screens.getByRole('link', { name: 'Staff', exact: true })).toHaveAttribute('aria-current', 'page')
    await page.reload()
    await expect(staff.getByRole('link', { name: section, exact: true })).toHaveAttribute('aria-current', 'page')
  }
  await screens.getByRole('link', { name: 'Customer', exact: true }).click()
  await page.getByLabel('Customer Name').fill('Draft Customer')
  await page.getByLabel('Sparks ID (optional)').fill('SPARKS123')
  await screens.getByRole('link', { name: 'Staff', exact: true }).click()
  await screens.getByRole('link', { name: 'Customer', exact: true }).click()
  await expect(page.getByLabel('Customer Name')).toHaveValue('Draft Customer')
  await expect(page.getByLabel('Sparks ID (optional)')).toHaveValue('SPARKS123')
  for (const width of [320, 390, 768, 1440]) {
    await page.setViewportSize({ width, height: 900 })
    for (const screen of ['Staff', 'Customer']) {
      await screens.getByRole('link', { name: screen, exact: true }).click()
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
    }
  }
})

for (const sparksId of ['', '   ', '  SPARKS123  ']) {
  test(`optional Sparks ID submits ${JSON.stringify(sparksId)}`, async ({ page }) => {
    await page.route('**/api/customer-feedback', async route => {
      const payload = route.request().postDataJSON()
      expect(payload.sparks_id).toBe(sparksId.trim() || null)
      expect(payload.is_sparks_customer).toBe(Boolean(sparksId.trim()))
      await route.fulfill({ json: { case_id: payload.submission_id, status: 'submitted' } })
    })
    await page.goto('/')
    await expect(page.getByRole('radio', { name: /^(Yes|No)$/ })).toHaveCount(0)
    const sparks = page.getByLabel('Sparks ID (optional)')
    await expect(sparks).toBeVisible()
    await expect(sparks).not.toHaveAttribute('required')
    await page.getByLabel('Customer Name').fill('Demo Customer')
    await page.getByLabel('Email address', { exact: true }).fill('demo@example.com')
    await page.getByLabel('Feedback (required)', { exact: true }).fill('The colleague helped me find the right size yesterday.')
    await page.getByRole('radio', { name: '5 stars: Very Good', exact: true }).check()
    await sparks.fill(sparksId)
    await page.getByRole('button', { name: 'Submit Feedback', exact: true }).click()
    await expect(page.getByRole('status')).toContainText('Feedback submitted successfully.')
    await expect(sparks).toBeVisible()
    await expect(sparks).toHaveValue('')
  })
}
